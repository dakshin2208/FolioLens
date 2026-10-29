import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, utcnow


class ClientPlan(Base):
    """The client's risk-profile answers and financial goals: one row per portfolio.

    Stored as JSON because both are small, always read and written together, and validated by
    Pydantic on the way in (`app/planning/schemas.py`).
    """

    __tablename__ = "client_plans"

    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("portfolios.id", ondelete="CASCADE"), primary_key=True
    )
    risk_answers: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    goals: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
