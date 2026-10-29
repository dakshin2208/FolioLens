import io

import pytest
from sqlalchemy import select

from app.demo.data import build_demo_input
from app.market_data.demo_seed import demo_isin, demo_transactions_csv
from app.portfolio import ingest
from app.portfolio.models import Upload
from app.portfolio.parsers.base import ParsedStatement, ParsedTxn
from app.reports.engine import build_report
from tests.conftest import auth_headers

API = "/api/v1"


def _portfolio(client, headers):
    return client.post(
        f"{API}/portfolios", json={"name": "Core", "client_name": "Client"}, headers=headers
    ).json()["id"]


def _upload(client, headers, pid, data: bytes, file_type="generic_csv", consent="true", **extra):
    files = {"file": ("statement.csv", io.BytesIO(data), "text/csv")}
    form = {"file_type": file_type, "consent": consent, **extra}
    return client.post(f"{API}/portfolios/{pid}/uploads", files=files, data=form, headers=headers)


def test_csv_upload_produces_the_same_report_as_the_engine(client, db):
    h = auth_headers(client)
    pid = _portfolio(client, h)
    r = _upload(client, h, pid, demo_transactions_csv().encode())
    assert r.status_code == 202
    up = r.json()
    assert up["status"] == "completed", up
    assert up["review"]["unmatched"] == []

    report = client.get(f"{API}/portfolios/{pid}/report", headers=h).json()
    assert report["status"] == "ok"
    expected = build_report(build_demo_input())
    assert report["overview"]["current_value"] == pytest.approx(
        expected["overview"]["current_value"], abs=1.0
    )  # within Rs 1 (D-10)
    assert report["overview"]["xirr"] == pytest.approx(expected["overview"]["xirr"], abs=1e-4)
    assert all(f["explanation"] for f in report["findings"])

    # The raw file is deleted after a successful parse (D-09)
    stored = db.scalar(select(Upload).where(Upload.id == up["id"]))
    assert stored.storage_key is None

    summary = client.get(f"{API}/portfolios", headers=h).json()[0]
    assert summary["current_value"] == pytest.approx(report["overview"]["current_value"])


def test_reuploading_the_same_statement_does_not_double_count(client):
    h = auth_headers(client)
    pid = _portfolio(client, h)
    data = demo_transactions_csv().encode()
    first = _upload(client, h, pid, data).json()
    second = _upload(client, h, pid, data).json()
    assert second["review"]["inserted"] == 0
    assert second["review"]["duplicates"] == first["review"]["inserted"]


def test_unknown_instrument_goes_to_review_then_mapping_completes(client):
    h = auth_headers(client)
    pid = _portfolio(client, h)
    csv = (
        "date,isin,symbol,name,type,units,price,amount\n"
        "2024-01-05,ZZ0000000001,,Demo Bluechip Equity Fnd,buy,100,100,10000\n"
    )
    up = _upload(client, h, pid, csv.encode()).json()
    assert up["status"] == "needs_review"
    [item] = up["review"]["unmatched"]
    assert item["raw_identifier"] == "ZZ0000000001"
    assert item["suggestion"]["name"] == "Demo Bluechip Equity Fund"

    found = client.get(f"{API}/instruments", params={"q": "Bluechip"}, headers=h).json()
    target = next(i for i in found if i["isin"] == demo_isin("mf-bluechip"))
    r = client.post(
        f"{API}/uploads/{up['id']}/review",
        headers=h,
        json={"mappings": [{"raw_identifier": "ZZ0000000001", "instrument_id": target["id"]}]},
    )
    assert r.json()["status"] == "completed"
    assert client.get(f"{API}/portfolios/{pid}/holdings", headers=h).json()["holdings"]


@pytest.mark.parametrize(
    "kwargs,code",
    [
        ({"consent": "false"}, 400),
        ({"file_type": "cas_pdf", "password": "x"}, 400),  # CSV content declared as PDF
    ],
)
def test_upload_validation(client, kwargs, code):
    h = auth_headers(client)
    pid = _portfolio(client, h)
    assert _upload(client, h, pid, b"date,type\n", **kwargs).status_code == code


def test_bad_csv_fails_with_a_readable_error(client):
    h = auth_headers(client)
    pid = _portfolio(client, h)
    up = _upload(client, h, pid, b"date,isin,type,units,amount\nnot-a-date,X,buy,1,1\n").json()
    assert up["status"] == "failed"
    assert "unrecognised date" in up["error"]


def test_cas_reconciliation_mismatch_requires_acknowledgement(client, monkeypatch):
    from datetime import date
    from decimal import Decimal

    isin = demo_isin("mf-bluechip")

    def fake_parse(file_type, data, password):
        return ParsedStatement(
            "cas_pdf",
            [
                ParsedTxn(
                    isin,
                    "Demo Bluechip Equity Fund",
                    date(2024, 1, 5),
                    "buy",
                    Decimal("100"),
                    Decimal("100"),
                    Decimal("10000"),
                )
            ],
            closing_units={isin: Decimal("150")},  # statement says 150 units, ledger has 100
            scheme_names={isin: "Demo Bluechip Equity Fund"},
        )

    monkeypatch.setattr(ingest, "parse_file", fake_parse)
    h = auth_headers(client)
    pid = _portfolio(client, h)
    files = {"file": ("cas.pdf", io.BytesIO(b"%PDF-1.4 fake"), "application/pdf")}
    up = client.post(
        f"{API}/portfolios/{pid}/uploads",
        files=files,
        headers=h,
        data={"file_type": "cas_pdf", "consent": "true", "password": "pw"},
    ).json()
    assert up["status"] == "needs_review"
    [rec] = up["review"]["reconciliation"]
    assert rec["variance"] == pytest.approx(-50) and not rec["ok"]

    r = client.post(
        f"{API}/uploads/{up['id']}/review", headers=h, json={"acknowledge_reconciliation": True}
    ).json()
    assert r["status"] == "completed"


def test_delete_portfolio_removes_everything(client):
    h = auth_headers(client)
    pid = _portfolio(client, h)
    _upload(client, h, pid, demo_transactions_csv().encode())
    assert client.delete(f"{API}/portfolios/{pid}", headers=h).status_code == 204
    assert client.get(f"{API}/portfolios/{pid}", headers=h).status_code == 404
