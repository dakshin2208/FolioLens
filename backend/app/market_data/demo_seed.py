"""Loads the synthetic demo universe into the database, so the full upload -> report flow
can be tried locally without any real market data. All ISINs start with 'XX' (not a real
country code) so they can never be confused with real securities."""

import csv
import io
from decimal import Decimal

from sqlalchemy.orm import Session

from app.demo.data import BENCHMARK_ID, BENCHMARK_NAME, build_demo_input
from app.market_data.loaders import _upsert_instruments, _upsert_prices
from app.market_data.models import FundConstituent
from app.portfolio.models import AssetClass, InstrumentType

SOURCE = "Synthetic demo data"


def demo_isin(instrument_id: str) -> str:
    return ("XXDEMO" + instrument_id.upper().replace("-", ""))[:12].ljust(12, "0")


def seed_demo(db: Session) -> dict[str, int]:
    inp = build_demo_input()
    rows = []
    for iid, info in inp.instruments.items():
        rows.append(
            {
                "type": InstrumentType(info.type),
                "isin": demo_isin(iid),
                "symbol": iid.upper(),
                "name": info.name,
                "asset_class": AssetClass(info.asset_class),
                "category": info.category,
                "sector": info.sector,
                "market_cap": info.market_cap,
                "is_liquid": info.is_liquid,
            }
        )
    rows.append(
        {
            "type": InstrumentType.INDEX,
            "isin": demo_isin(BENCHMARK_ID),
            "symbol": "SYNTH-TRI",
            "name": BENCHMARK_NAME,
            "asset_class": AssetClass.EQUITY,
            "category": None,
            "sector": None,
            "market_cap": None,
            "is_liquid": False,
        }
    )
    ids = _upsert_instruments(db, rows)

    price_rows = []
    for iid, series in inp.prices.items():
        for d, v in series.items():
            price_rows.append(
                {"instrument_id": ids[demo_isin(iid)], "date": d, "close": Decimal(str(v)), "source": SOURCE}
            )
    for d, v in inp.benchmark_prices.items():
        price_rows.append(
            {
                "instrument_id": ids[demo_isin(BENCHMARK_ID)],
                "date": d,
                "close": Decimal(str(v)),
                "source": SOURCE,
            }
        )
    _upsert_prices(db, price_rows)

    for fid, cons in inp.constituents.items():
        for sid, w in cons.weights.items():
            db.merge(
                FundConstituent(
                    fund_id=ids[demo_isin(fid)],
                    stock_id=ids[demo_isin(sid)],
                    as_of=cons.as_of,
                    weight=Decimal(str(w)),
                    source=SOURCE,
                )
            )
    db.commit()
    return {"instruments": len(rows), "prices": len(price_rows)}


def demo_transactions_csv() -> str:
    """The demo ledger in FolioLens's generic CSV format, for trying the upload flow."""
    inp = build_demo_input()
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["date", "isin", "symbol", "name", "type", "units", "price", "amount"])
    for t in inp.transactions:
        info = inp.instruments[t.instrument_id]
        price = round(t.amount / t.units, 4) if t.units else ""
        w.writerow(
            [
                t.date.isoformat(),
                demo_isin(t.instrument_id),
                t.instrument_id.upper(),
                info.name,
                t.type,
                t.units,
                price,
                f"{t.amount:.2f}",
            ]
        )
    return out.getvalue()
