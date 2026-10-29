"""Estimated capital-gains tax if part of a holding were sold today (India, FY 2026-27 rules).

This is an *estimate* to help an advisor weigh an option, not a tax computation. It uses:

- FIFO lots: the units bought first are treated as sold first (the method Indian tax rules use
  for mutual fund units and demat shares).
- Equity-oriented holdings (stocks, equity funds, equity ETFs):
    held 12 months or less -> short-term gain, taxed at 20%
    held more than 12 months -> long-term gain, taxed at 12.5% above a yearly exemption of
    Rs 1.25 lakh per person (the exemption is shared by all long-term gains in the year).
- Debt, gold, hybrid and other funds: the rules depend on the fund type and purchase date
  (many are taxed at the investor's slab rate), so only the gain is shown, never a guessed rate.

Not covered: exit loads, securities transaction tax, surcharge and cess, grandfathered
pre-2018 units, and set-off of losses from elsewhere. The result says so in `notes`.
"""

from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from app.analytics.types import LedgerTxn, signed_units

TAX_RULES = "India FY 2026-27 (estimate)"
EQUITY_STCG_RATE = 0.20
EQUITY_LTCG_RATE = 0.125
EQUITY_LTCG_EXEMPTION = 125_000.0
EQUITY_LONG_TERM_DAYS = 365  # "more than 12 months"
UNIT_EPSILON = 1e-6


@dataclass
class Lot:
    bought: date
    units: float
    cost_per_unit: float


@dataclass
class SaleEstimate:
    units: float
    proceeds: float
    cost: float
    short_term_gain: float
    long_term_gain: float
    equity_rules: bool
    tax_if_exemption_unused: float | None
    tax_if_exemption_used: float | None
    notes: list[str] = field(default_factory=list)

    @property
    def gain(self) -> float:
        return self.short_term_gain + self.long_term_gain

    def to_dict(self) -> dict[str, Any]:
        return {
            "units": self.units,
            "proceeds": self.proceeds,
            "cost": self.cost,
            "gain": self.gain,
            "short_term_gain": self.short_term_gain,
            "long_term_gain": self.long_term_gain,
            "equity_rules": self.equity_rules,
            "tax_if_exemption_unused": self.tax_if_exemption_unused,
            "tax_if_exemption_used": self.tax_if_exemption_used,
            "rules": TAX_RULES,
            "notes": self.notes,
        }


def fifo_lots(transactions: list[LedgerTxn], as_of: date | None = None) -> dict[str, list[Lot]]:
    """Open lots per instrument after replaying the ledger first-in, first-out."""
    lots: dict[str, deque[Lot]] = defaultdict(deque)
    for t in sorted(transactions, key=lambda x: (x.date, 0 if signed_units(x) > 0 else 1)):
        if as_of and t.date > as_of:
            continue
        delta = signed_units(t)
        if delta > 0:
            lots[t.instrument_id].append(Lot(t.date, delta, t.amount / delta if delta else 0.0))
        elif delta < 0:
            remaining = -delta
            queue = lots[t.instrument_id]
            while remaining > UNIT_EPSILON and queue:
                lot = queue[0]
                take = min(lot.units, remaining)
                lot.units -= take
                remaining -= take
                if lot.units <= UNIT_EPSILON:
                    queue.popleft()
    return {i: list(q) for i, q in lots.items() if q}


def is_equity_oriented(asset_class: str) -> bool:
    return asset_class == "equity"


def estimate_sale(
    lots: list[Lot], units: float, price: float, sale_date: date, asset_class: str
) -> SaleEstimate:
    """Estimate gains and tax if `units` were sold at `price` on `sale_date` (FIFO)."""
    remaining = min(units, sum(lot.units for lot in lots))
    sold = remaining
    cost = short_gain = long_gain = 0.0
    for lot in lots:
        if remaining <= UNIT_EPSILON:
            break
        take = min(lot.units, remaining)
        remaining -= take
        lot_cost = take * lot.cost_per_unit
        gain = take * price - lot_cost
        cost += lot_cost
        if (sale_date - lot.bought).days > EQUITY_LONG_TERM_DAYS:
            long_gain += gain
        else:
            short_gain += gain

    proceeds = sold * price
    equity = is_equity_oriented(asset_class)
    notes: list[str] = []
    tax_unused = tax_used = None
    if equity:
        stcg_tax = max(short_gain, 0.0) * EQUITY_STCG_RATE
        # Losses in one bucket can reduce gains in the other; keep it simple and conservative:
        # a net loss means no tax on this sale.
        net_long = long_gain + min(short_gain, 0.0)
        tax_unused = stcg_tax + max(net_long - EQUITY_LTCG_EXEMPTION, 0.0) * EQUITY_LTCG_RATE
        tax_used = stcg_tax + max(net_long, 0.0) * EQUITY_LTCG_RATE
        notes.append(
            "Equity rules: 20% on gains from units held 12 months or less; 12.5% on longer-held "
            "gains above the Rs 1.25 lakh yearly exemption."
        )
    else:
        notes.append(
            "This is not an equity fund, so the tax depends on the fund type and purchase date "
            "(often the client's slab rate). Only the gain is shown."
        )
    notes.append("Estimate only: excludes exit load, surcharge, cess and gains elsewhere in the year.")
    return SaleEstimate(
        units=sold,
        proceeds=proceeds,
        cost=cost,
        short_term_gain=short_gain,
        long_term_gain=long_gain,
        equity_rules=equity,
        tax_if_exemption_unused=tax_unused,
        tax_if_exemption_used=tax_used,
        notes=notes,
    )


def combine(estimates: list[SaleEstimate]) -> SaleEstimate | None:
    """One estimate for several sales made in the same year (the exemption is used once)."""
    if not estimates:
        return None
    equity = all(e.equity_rules for e in estimates)
    short = sum(e.short_term_gain for e in estimates)
    long = sum(e.long_term_gain for e in estimates)
    tax_unused = tax_used = None
    if equity:
        stcg_tax = sum(max(e.short_term_gain, 0.0) for e in estimates) * EQUITY_STCG_RATE
        net_long = long + min(short, 0.0)
        tax_unused = stcg_tax + max(net_long - EQUITY_LTCG_EXEMPTION, 0.0) * EQUITY_LTCG_RATE
        tax_used = stcg_tax + max(net_long, 0.0) * EQUITY_LTCG_RATE
    notes = list(dict.fromkeys(n for e in estimates for n in e.notes))
    return SaleEstimate(
        units=sum(e.units for e in estimates),
        proceeds=sum(e.proceeds for e in estimates),
        cost=sum(e.cost for e in estimates),
        short_term_gain=short,
        long_term_gain=long,
        equity_rules=equity,
        tax_if_exemption_unused=tax_unused,
        tax_if_exemption_used=tax_used,
        notes=notes,
    )
