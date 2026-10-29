"""What helped and what hurt: each holding's share of the portfolio's profit, and how each
equity holding did against the benchmark index with the *same* cash flows.

Profit of one holding (lifetime, in rupees):

    profit = current value + money taken out (sales, switch-outs, dividends paid)
             - money put in (purchases, switch-ins)

Benchmark comparison uses the public market equivalent (PME) idea: replay the holding's own
purchases and sales into the index on the same dates, then compare the two XIRRs. This is a
fair, like-for-like comparison because both sides had exactly the same money at the same time.
"""

from datetime import date
from typing import Any

from app.analytics.holdings import holding_cashflows
from app.analytics.types import InstrumentInfo, LedgerTxn
from app.analytics.xirr import XirrError, xirr


def _price_on_or_before(prices: dict[date, float], d: date, sorted_dates: list[date]) -> float | None:
    # sorted_dates is ascending; walk back from the last date not after d
    lo, hi = 0, len(sorted_dates) - 1
    best = None
    while lo <= hi:
        mid = (lo + hi) // 2
        if sorted_dates[mid] <= d:
            best = sorted_dates[mid]
            lo = mid + 1
        else:
            hi = mid - 1
    return prices[best] if best is not None else None


def index_equivalent_xirr(
    flows: list[tuple[date, float]], index_prices: dict[date, float], valuation_date: date
) -> float | None:
    """XIRR the index would have earned with the same dated cash flows (None if undefined)."""
    if not flows or not index_prices:
        return None
    dates = sorted(index_prices)
    units = 0.0
    for d, amount in flows:
        p = _price_on_or_before(index_prices, d, dates)
        if p is None or p <= 0:
            return None
        units += -amount / p  # money in (negative) buys units; money out sells them
    end = _price_on_or_before(index_prices, valuation_date, dates)
    if end is None:
        return None
    terminal = units * end
    if terminal <= 0:
        return None
    try:
        return xirr([*flows, (valuation_date, terminal)])
    except XirrError:
        return None


def contributions(
    transactions: list[LedgerTxn],
    values: dict[str, float],
    instruments: dict[str, InstrumentInfo],
    valuation_date: date,
    index_prices: dict[date, float],
    holding_xirr: dict[str, float | None],
    compare_with_index: bool,
) -> dict[str, Any]:
    ids = sorted({t.instrument_id for t in transactions if t.date <= valuation_date})
    items: list[dict[str, Any]] = []
    for iid in ids:
        info = instruments[iid]
        flows = [(d, a) for d, a in holding_cashflows(transactions, iid) if d <= valuation_date]
        value = values.get(iid, 0.0)
        profit = sum(a for _, a in flows) + value
        put_in = -sum(a for _, a in flows if a < 0)
        idx = (
            index_equivalent_xirr(flows, index_prices, valuation_date)
            if compare_with_index and info.asset_class == "equity"
            else None
        )
        own = holding_xirr.get(iid)
        items.append(
            {
                "instrument_id": iid,
                "name": info.name,
                "asset_class": info.asset_class,
                "type": info.type,
                "value": value,
                "held": iid in values,
                "money_in": put_in,
                "profit": profit,
                "xirr": own,
                "index_xirr": idx,
                "vs_index": (own - idx) if own is not None and idx is not None else None,
            }
        )
    total_profit = sum(i["profit"] for i in items)
    for i in items:
        i["share_of_profit"] = i["profit"] / total_profit if total_profit > 0 else None
    items.sort(key=lambda i: -i["profit"])
    helped = [i["instrument_id"] for i in items if i["profit"] > 0][:3]
    lagging = sorted(
        (i for i in items if i["vs_index"] is not None and i["vs_index"] < 0),
        key=lambda i: i["vs_index"],
    )
    losing = [i for i in items if i["profit"] < 0]
    hurt: list[str] = []
    for i in [*losing, *lagging]:
        if i["instrument_id"] not in hurt:
            hurt.append(i["instrument_id"])
    return {
        "total_profit": total_profit,
        "items": items,
        "helped": helped,
        "hurt": hurt[:3],
        "method": (
            "Profit = current value + money taken out (sales, switch-outs, dividends paid) "
            "- money put in. Index comparison replays each holding's own purchases and sales into "
            "the benchmark index on the same dates and compares the two annual returns (XIRR)."
        ),
    }
