"""Every statement format is converted into this one neutral shape.

Domain code depends on these types only, never on a parser library's own output, so a
parser can be replaced without touching the ledger, analytics or API.
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal


class ParseError(ValueError):
    """The file could not be read as the declared format. Message is safe to show users."""


@dataclass
class ParsedTxn:
    raw_identifier: str  # ISIN when available, otherwise the symbol
    raw_name: str | None
    date: date
    type: str  # buy / sell / dividend_payout / dividend_reinvest / switch_in / switch_out
    units: Decimal  # positive
    price: Decimal | None
    amount: Decimal  # positive rupees
    symbol: str | None = None
    external_ref: str | None = None  # e.g. broker trade id


@dataclass
class ParsedStatement:
    format: str
    transactions: list[ParsedTxn]
    closing_units: dict[str, Decimal] = field(default_factory=dict)  # ISIN -> units
    scheme_names: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    statement_period: tuple[date, date] | None = None
