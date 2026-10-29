import enum
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, utcnow


class InstrumentType(enum.StrEnum):
    MUTUAL_FUND = "mutual_fund"
    STOCK = "stock"
    ETF = "etf"
    INDEX = "index"


class AssetClass(enum.StrEnum):
    EQUITY = "equity"
    DEBT = "debt"
    HYBRID = "hybrid"
    GOLD = "gold"
    CASH = "cash"
    OTHER = "other"


class TxnType(enum.StrEnum):
    BUY = "buy"
    SELL = "sell"
    DIVIDEND_PAYOUT = "dividend_payout"
    DIVIDEND_REINVEST = "dividend_reinvest"
    SWITCH_IN = "switch_in"
    SWITCH_OUT = "switch_out"


class UploadStatus(enum.StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    NEEDS_REVIEW = "needs_review"
    COMPLETED = "completed"
    FAILED = "failed"


class FileType(enum.StrEnum):
    CAS_PDF = "cas_pdf"
    ZERODHA_TRADEBOOK = "zerodha_tradebook"
    GENERIC_CSV = "generic_csv"


def _enum(e: type[enum.Enum]) -> Enum:
    return Enum(e, native_enum=False, length=32, values_callable=lambda x: [m.value for m in x])


class Portfolio(Base):
    """One client portfolio owned by an advisor's account."""

    __tablename__ = "portfolios"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    client_name: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    uploads: Mapped[list["Upload"]] = relationship(
        back_populates="portfolio", cascade="all, delete-orphan", passive_deletes=True
    )


class Instrument(Base):
    """Master list of securities. Filled by market-data loaders, not by uploads."""

    __tablename__ = "instruments"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    type: Mapped[InstrumentType] = mapped_column(_enum(InstrumentType))
    isin: Mapped[str | None] = mapped_column(String(12), unique=True, index=True)
    symbol: Mapped[str | None] = mapped_column(String(40), index=True)
    amfi_code: Mapped[str | None] = mapped_column(String(12), index=True)
    name: Mapped[str] = mapped_column(String(255))
    asset_class: Mapped[AssetClass] = mapped_column(_enum(AssetClass), default=AssetClass.OTHER)
    category: Mapped[str | None] = mapped_column(String(120))
    sector: Mapped[str | None] = mapped_column(String(80))
    market_cap: Mapped[str | None] = mapped_column(String(16))  # large / mid / small
    is_liquid: Mapped[bool] = mapped_column(default=False)


class Upload(Base):
    __tablename__ = "uploads"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("portfolios.id", ondelete="CASCADE"), index=True
    )
    filename: Mapped[str] = mapped_column(String(255))
    file_type: Mapped[FileType] = mapped_column(_enum(FileType))
    file_sha256: Mapped[str] = mapped_column(String(64))
    storage_key: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[UploadStatus] = mapped_column(_enum(UploadStatus), default=UploadStatus.QUEUED)
    error: Mapped[str | None] = mapped_column(String(1000))
    # Structured review items: unmatched instruments, reconciliation variances, etc.
    review: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    parsed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    portfolio: Mapped[Portfolio] = relationship(back_populates="uploads")


class Transaction(Base):
    """The ledger. Holdings are always derived from these rows."""

    __tablename__ = "transactions"
    __table_args__ = (UniqueConstraint("portfolio_id", "source_ref", name="uq_txn_source"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("portfolios.id", ondelete="CASCADE"), index=True
    )
    upload_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("uploads.id", ondelete="SET NULL"), index=True
    )
    instrument_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("instruments.id"), index=True)
    raw_identifier: Mapped[str] = mapped_column(String(64))  # ISIN or symbol as in the file
    raw_name: Mapped[str | None] = mapped_column(String(255))
    date: Mapped[date] = mapped_column(Date, index=True)
    type: Mapped[TxnType] = mapped_column(_enum(TxnType))
    units: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    price: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 2))
    source_ref: Mapped[str] = mapped_column(String(64))  # dedupe key; makes jobs idempotent
