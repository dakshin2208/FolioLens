"""Read-only market data for the UI's ticker tape.

Returns the latest two closes per instrument, so the change shown is a real day-on-day move from the
prices table, never a made-up number. Public market data only: no user data is involved.
"""

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.market_data.models import Price
from app.portfolio.models import Instrument

router = APIRouter(prefix="/market", tags=["market"])

TICKER_LIMIT = 30


@router.get("/ticker")
def ticker(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    rn = func.row_number().over(partition_by=Price.instrument_id, order_by=Price.date.desc()).label("rn")
    latest = select(Price.instrument_id, Price.date, Price.close, Price.source, rn).subquery()
    rows = db.execute(
        select(latest, Instrument.name, Instrument.symbol, Instrument.type)
        .join(Instrument, Instrument.id == latest.c.instrument_id)
        .where(latest.c.rn <= 2)
        .order_by(Instrument.type, Instrument.name, latest.c.rn)
    ).all()

    by_id: dict[Any, list[Any]] = {}
    for r in rows:
        by_id.setdefault(r.instrument_id, []).append(r)

    out: list[dict[str, Any]] = []
    for pts in by_id.values():
        if len(pts) < 2:
            continue
        last, prev = pts[0], pts[1]
        if not prev.close:
            continue
        out.append(
            {
                "symbol": last.symbol or _short(last.name),
                "name": last.name,
                "type": str(last.type),
                "date": last.date.isoformat(),
                "close": float(last.close),
                "prev_close": float(prev.close),
                "change": float(last.close / prev.close - 1),
                "source": last.source,
            }
        )
    return out[:TICKER_LIMIT]


def _short(name: str) -> str:
    """'Demo Bluechip Equity Fund' -> 'BLUECHIP EQ' style label for funds without a symbol."""
    skip = {"demo", "fund", "the", "ltd", "limited", "plan", "direct", "growth", "-"}
    words = [w for w in name.replace("-", " ").split() if w.lower() not in skip]
    return " ".join(words[:2]).upper()[:18] or name[:18].upper()
