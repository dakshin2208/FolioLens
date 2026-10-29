import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PortfolioCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    client_name: str = Field(min_length=1, max_length=120)


class PortfolioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    client_name: str
    created_at: datetime


class PortfolioSummary(PortfolioOut):
    current_value: float | None = None
    xirr: float | None = None
    findings: int | None = None
    valuation_date: date | None = None
    last_upload_status: str | None = None


class UploadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    portfolio_id: uuid.UUID
    filename: str
    file_type: str
    status: str
    error: str | None
    review: dict[str, Any]
    created_at: datetime
    parsed_at: datetime | None


class Mapping(BaseModel):
    raw_identifier: str
    instrument_id: uuid.UUID


class ReviewRequest(BaseModel):
    mappings: list[Mapping] = []
    acknowledge_reconciliation: bool = False


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    instrument_id: uuid.UUID | None
    raw_identifier: str
    raw_name: str | None
    date: date
    type: str
    units: Decimal
    price: Decimal | None
    amount: Decimal


class InstrumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: str
    isin: str | None
    symbol: str | None
    name: str
    asset_class: str
    category: str | None
