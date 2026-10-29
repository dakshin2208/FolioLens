"""Allocation, mutual fund look-through, fund overlap and concentration."""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date

from app.analytics.types import Constituents, InstrumentInfo

MAX_CONSTITUENT_AGE_DAYS = 92  # PRD D-05: constituents no older than three months
MIN_LOOKTHROUGH_COVERAGE = 0.80
LOOKTHROUGH_ASSET_CLASSES = {"equity", "hybrid"}


def asset_allocation(values: dict[str, float], instruments: dict[str, InstrumentInfo]) -> dict[str, float]:
    total = sum(values.values())
    out: dict[str, float] = defaultdict(float)
    if total <= 0:
        return {}
    for i, v in values.items():
        out[instruments[i].asset_class] += v / total
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


@dataclass
class LookThrough:
    stock_values: dict[str, float]  # stock id -> rupees (direct + via funds)
    direct_values: dict[str, float]
    covered_fund_value: float
    eligible_fund_value: float
    coverage: float  # covered / eligible fund value (1.0 if no eligible funds)
    is_reliable: bool
    excluded_funds: list[dict[str, str]] = field(default_factory=list)
    residual_in_funds: float = 0.0  # cash and holdings not disclosed as stocks
    data_dates: dict[str, str] = field(default_factory=dict)


def look_through(
    values: dict[str, float],
    instruments: dict[str, InstrumentInfo],
    constituents: dict[str, Constituents],
    valuation_date: date,
) -> LookThrough:
    """Combine direct stock holdings with stocks held indirectly through funds:

        E_s = sum_f (value_f x weight_{f,s}) + direct_s

    Funds without recent constituent data are excluded and reported, never guessed.
    """
    stock_values: dict[str, float] = defaultdict(float)
    direct: dict[str, float] = {}
    covered = eligible = residual = 0.0
    excluded: list[dict[str, str]] = []
    dates: dict[str, str] = {}

    for iid, value in values.items():
        info = instruments[iid]
        if info.type == "stock":
            stock_values[iid] += value
            direct[iid] = value
            continue
        if info.type not in ("mutual_fund", "etf") or info.asset_class not in LOOKTHROUGH_ASSET_CLASSES:
            continue
        eligible += value
        data = constituents.get(iid)
        if data is None:
            excluded.append({"instrument_id": iid, "name": info.name, "reason": "no constituent data"})
            continue
        age = (valuation_date - data.as_of).days
        if age > MAX_CONSTITUENT_AGE_DAYS:
            excluded.append(
                {
                    "instrument_id": iid,
                    "name": info.name,
                    "reason": f"constituent data is {age} days old ({data.as_of})",
                }
            )
            continue
        covered += value
        dates[iid] = data.as_of.isoformat()
        disclosed = 0.0
        for stock_id, w in data.weights.items():
            stock_values[stock_id] += value * w
            disclosed += w
        residual += value * max(1.0 - disclosed, 0.0)

    coverage = covered / eligible if eligible > 0 else 1.0
    return LookThrough(
        stock_values=dict(stock_values),
        direct_values=direct,
        covered_fund_value=covered,
        eligible_fund_value=eligible,
        coverage=coverage,
        is_reliable=coverage >= MIN_LOOKTHROUGH_COVERAGE,
        excluded_funds=excluded,
        residual_in_funds=residual,
        data_dates=dates,
    )


def group_exposure(
    stock_values: dict[str, float], instruments: dict[str, InstrumentInfo], attr: str
) -> dict[str, float]:
    """Sum stock exposure by an attribute such as sector or market_cap (in rupees)."""
    out: dict[str, float] = defaultdict(float)
    for sid, v in stock_values.items():
        info = instruments.get(sid)
        key = getattr(info, attr, None) if info else None
        out[key or "Unclassified"] += v
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


def fund_overlap(a: Constituents, b: Constituents) -> float:
    """Overlap(A, B) = sum over shared stocks of min(weight in A, weight in B)."""
    shared = a.weights.keys() & b.weights.keys()
    return float(sum(min(a.weights[s], b.weights[s]) for s in shared))


def herfindahl(weights: list[float]) -> float:
    """HHI = sum of squared weights. 1/HHI is the 'effective number' of holdings."""
    total = sum(weights)
    if total <= 0:
        return 0.0
    return float(sum((w / total) ** 2 for w in weights))
