import pytest

from app.demo.data import build_demo_input
from app.reports.engine import build_report


@pytest.fixture(scope="module")
def report():
    return build_report(build_demo_input())


def test_values_reconcile(report):
    total = report["overview"]["current_value"]
    assert sum(h["value"] for h in report["holdings"]) == pytest.approx(total)
    assert sum(h["weight"] for h in report["holdings"]) == pytest.approx(1.0)
    assert sum(a["weight"] for a in report["allocation"]["asset_class"]) == pytest.approx(1.0)


def test_report_is_deterministic(report):
    again = build_report(build_demo_input())
    assert again["overview"] == report["overview"]
    assert again["risk"] == report["risk"]


def test_stale_fund_is_excluded_with_a_reason(report):
    excluded = report["allocation"]["lookthrough"]["excluded"]
    assert [e["name"] for e in excluded] == ["Demo Midcap Opportunities Fund"]
    assert any("Midcap" in q["message"] for q in report["data_quality"])


def test_every_finding_carries_evidence(report):
    types = {f["type"] for f in report["findings"]}
    assert {"fund_overlap", "single_stock_concentration", "sector_concentration"} <= types
    for f in report["findings"]:
        assert f["calc_version"] and f["data_date"]
        assert f["measured_value"] is not None


def test_risk_metrics_present_with_method(report):
    r = report["risk"]
    assert r["available"]
    assert r["max_drawdown"] < 0
    assert r["var_95_1d"] > 0
    assert "Time-weighted" in r["method"]["returns"]


def test_demo_is_identical_across_processes():
    """Guards against hidden randomness such as set ordering, which changes per process."""
    import os
    import subprocess
    import sys

    code = (
        "from app.demo.data import build_demo_input; from app.reports.engine import build_report;"
        "print(round(build_report(build_demo_input())['overview']['current_value'], 2))"
    )
    outs = {
        subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            check=True,
            env={**os.environ, "PYTHONHASHSEED": seed},
        ).stdout
        for seed in ("1", "2")
    }
    assert len(outs) == 1


def test_unpriced_holding_is_excluded_not_valued_at_zero():
    from datetime import date

    from app.analytics.types import InstrumentInfo, LedgerTxn, PortfolioInput

    inp = PortfolioInput(
        instruments={
            "a": InstrumentInfo("a", "Fund A", "mutual_fund", "equity"),
            "b": InstrumentInfo("b", "Stock B", "stock", "equity"),
        },
        transactions=[
            LedgerTxn("a", date(2024, 1, 1), "buy", 100, 1000),
            LedgerTxn("b", date(2024, 1, 1), "buy", 10, 500),
        ],
        prices={"a": {date(2024, 1, 1): 10.0, date(2025, 1, 1): 15.0}, "b": {}},
    )
    r = build_report(inp)
    assert r["overview"]["current_value"] == pytest.approx(1500)
    assert r["overview"]["xirr"] == pytest.approx(0.5, abs=0.01)  # Fund A alone: +50% in a year
    assert any("No price for Stock B" in q["message"] for q in r["data_quality"])
