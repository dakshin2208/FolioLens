"""Imports every model so SQLAlchemy metadata (and Alembic) can see all tables."""

from app.audit.models import AuditLog, Consent
from app.identity.models import User
from app.market_data.models import FundConstituent, Price
from app.planning.models import ClientPlan
from app.portfolio.models import Instrument, Portfolio, Transaction, Upload
from app.reports.models import AnalyticsSnapshot

__all__ = [
    "AnalyticsSnapshot",
    "AuditLog",
    "ClientPlan",
    "Consent",
    "FundConstituent",
    "Instrument",
    "Portfolio",
    "Price",
    "Transaction",
    "Upload",
    "User",
]
