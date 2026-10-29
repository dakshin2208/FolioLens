"""Plain data types used by the analytics engine.

The engine never imports the database, API or LLM code. Everything it needs is passed in
through these types, which makes every formula easy to unit-test.
"""

from dataclasses import dataclass, field
from datetime import date

from app.analytics.planning import PlanInput


@dataclass(frozen=True)
class InstrumentInfo:
    id: str
    name: str
    type: str  # mutual_fund / stock / etf / index
    asset_class: str  # equity / debt / hybrid / gold / cash / other
    isin: str | None = None
    sector: str | None = None
    market_cap: str | None = None  # large / mid / small
    is_liquid: bool = False
    category: str | None = None


@dataclass(frozen=True)
class LedgerTxn:
    instrument_id: str
    date: date
    type: str  # buy / sell / dividend_payout / dividend_reinvest / switch_in / switch_out
    units: float  # always positive; direction comes from `type`
    amount: float  # always positive rupees


@dataclass(frozen=True)
class Constituents:
    as_of: date
    weights: dict[str, float]  # stock instrument id -> fraction of fund NAV


@dataclass
class PortfolioInput:
    instruments: dict[str, InstrumentInfo]
    transactions: list[LedgerTxn]
    prices: dict[str, dict[date, float]]  # instrument id -> {date: close}
    constituents: dict[str, Constituents] = field(default_factory=dict)  # fund id -> data
    benchmark_name: str | None = None
    benchmark_prices: dict[date, float] = field(default_factory=dict)
    valuation_date: date | None = None
    data_sources: list[str] = field(default_factory=list)
    plan: PlanInput | None = None  # the client's risk answers and goals, if the advisor added them


UNIT_IN = {"buy", "dividend_reinvest", "switch_in"}
UNIT_OUT = {"sell", "switch_out"}


def signed_units(txn: LedgerTxn) -> float:
    if txn.type in UNIT_IN:
        return txn.units
    if txn.type in UNIT_OUT:
        return -txn.units
    return 0.0
