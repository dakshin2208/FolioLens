"""Derive holdings, cost and cash flows from the transaction ledger."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from app.analytics.types import LedgerTxn, signed_units

UNIT_EPSILON = 1e-6


@dataclass
class Holding:
    instrument_id: str
    units: float
    cost: float  # average-cost basis of the units still held
    first_date: date


def build_holdings(transactions: list[LedgerTxn], as_of: date | None = None) -> dict[str, Holding]:
    """Rebuild current holdings using the average-cost method.

    - buy / switch_in / dividend_reinvest add units and cost
    - sell / switch_out remove units and a proportional share of cost
    - dividend_payout changes neither units nor cost
    """
    units: dict[str, float] = defaultdict(float)
    cost: dict[str, float] = defaultdict(float)
    first: dict[str, date] = {}
    for t in sorted(transactions, key=lambda x: (x.date, 0 if signed_units(x) > 0 else 1)):
        if as_of and t.date > as_of:
            continue
        delta = signed_units(t)
        first.setdefault(t.instrument_id, t.date)
        if delta > 0:
            units[t.instrument_id] += delta
            cost[t.instrument_id] += t.amount
        elif delta < 0:
            held = units[t.instrument_id]
            if held <= UNIT_EPSILON:
                raise ValueError(f"Sell of {t.instrument_id} on {t.date} with no units held")
            fraction = min(-delta / held, 1.0)
            cost[t.instrument_id] -= cost[t.instrument_id] * fraction
            units[t.instrument_id] = held + delta
    return {i: Holding(i, units[i], max(cost[i], 0.0), first[i]) for i in units if units[i] > UNIT_EPSILON}


def units_by_instrument(transactions: list[LedgerTxn]) -> dict[str, float]:
    totals: dict[str, float] = defaultdict(float)
    for t in transactions:
        totals[t.instrument_id] += signed_units(t)
    return dict(totals)


def portfolio_cashflows(transactions: list[LedgerTxn]) -> list[tuple[date, float]]:
    """External cash flows from the investor's point of view (for portfolio XIRR).

    Switches and dividend reinvestments stay inside the portfolio, so they are not
    external flows. Counting them would double count money.
    """
    flows: list[tuple[date, float]] = []
    for t in transactions:
        if t.type == "buy":
            flows.append((t.date, -t.amount))
        elif t.type in ("sell", "dividend_payout"):
            flows.append((t.date, t.amount))
    return flows


def holding_cashflows(transactions: list[LedgerTxn], instrument_id: str) -> list[tuple[date, float]]:
    """Cash flows for one holding's XIRR. Here switches do count: money moved in or out."""
    flows: list[tuple[date, float]] = []
    for t in transactions:
        if t.instrument_id != instrument_id:
            continue
        if t.type in ("buy", "switch_in"):
            flows.append((t.date, -t.amount))
        elif t.type in ("sell", "switch_out", "dividend_payout"):
            flows.append((t.date, t.amount))
    return flows
