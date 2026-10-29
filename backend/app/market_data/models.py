import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Price(Base):
    """Daily close price or NAV for an instrument (also used for benchmark indices)."""

    __tablename__ = "prices"

    instrument_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("instruments.id", ondelete="CASCADE"), primary_key=True
    )
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    close: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    source: Mapped[str] = mapped_column(String(40))


class FundConstituent(Base):
    """A fund's holding of a stock, from the AMC's monthly portfolio disclosure."""

    __tablename__ = "fund_constituents"

    fund_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("instruments.id", ondelete="CASCADE"), primary_key=True
    )
    stock_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("instruments.id", ondelete="CASCADE"), primary_key=True
    )
    as_of: Mapped[date] = mapped_column(Date, primary_key=True)
    weight: Mapped[Decimal] = mapped_column(Numeric(9, 6))  # fraction of fund NAV, 0..1
    source: Mapped[str] = mapped_column(String(80))
