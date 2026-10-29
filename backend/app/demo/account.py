"""Creates a ready-to-use local demo account with an analysed client portfolio.

For local development and demos only. It refuses to run in production.
"""

import hashlib

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.models import Consent
from app.config import CONSENT_TEXT_VERSION, get_settings
from app.demo.data import DEMO_PLAN
from app.identity.models import User
from app.identity.security import hash_password
from app.market_data.demo_seed import demo_transactions_csv
from app.planning.models import ClientPlan
from app.portfolio.ingest import process_upload
from app.portfolio.models import FileType, Portfolio, Upload, UploadStatus
from app.reports.service import refresh_report
from app.storage.base import get_storage

DEMO_EMAIL = "demo@foliolens.app"
DEMO_PASSWORD = "foliolens-demo-2026"  # noqa: S105 - local demo account only
CLIENT = "Sample Client (synthetic)"


def seed_demo_account(db: Session) -> dict[str, str]:
    if get_settings().is_production:
        raise RuntimeError("The demo account is for local use only")
    user = db.scalar(select(User).where(User.email == DEMO_EMAIL))
    if user is None:
        user = User(email=DEMO_EMAIL, password_hash=hash_password(DEMO_PASSWORD))
        db.add(user)
        db.flush()
    portfolio = db.scalar(
        select(Portfolio).where(Portfolio.owner_id == user.id, Portfolio.client_name == CLIENT)
    )
    if portfolio is None:
        portfolio = Portfolio(owner_id=user.id, name="Core portfolio", client_name=CLIENT)
        db.add(portfolio)
        db.flush()
        data = demo_transactions_csv().encode()
        upload = Upload(
            portfolio_id=portfolio.id,
            filename="demo_transactions.csv",
            file_type=FileType.GENERIC_CSV,
            file_sha256=hashlib.sha256(data).hexdigest(),
        )
        db.add(upload)
        db.flush()
        upload.storage_key = f"{portfolio.id}/{upload.id}"
        get_storage().put(upload.storage_key, data)
        db.add(Consent(user_id=user.id, portfolio_id=portfolio.id, consent_text_version=CONSENT_TEXT_VERSION))
        db.commit()
        upload = process_upload(db, upload.id)
        if upload.status != UploadStatus.COMPLETED:
            raise RuntimeError(f"Demo upload ended as {upload.status}: {upload.error}")
    if db.get(ClientPlan, portfolio.id) is None:
        db.add(
            ClientPlan(
                portfolio_id=portfolio.id,
                risk_answers=dict(DEMO_PLAN.risk_answers),
                goals=[
                    {
                        "id": g.id,
                        "name": g.name,
                        "target_amount": g.target_amount,
                        "target_date": g.target_date.isoformat(),
                        "monthly_sip": g.monthly_sip,
                        "share_of_portfolio": g.share_of_portfolio,
                    }
                    for g in DEMO_PLAN.goals
                ],
            )
        )
    db.commit()
    snap = refresh_report(db, portfolio.id)  # always rebuild, so AI settings take effect
    findings = snap.report.get("findings", [])
    ai = sum(1 for f in findings if f.get("explanation_source") == "llm")
    return {
        "email": DEMO_EMAIL,
        "password": DEMO_PASSWORD,
        "client": CLIENT,
        "report": snap.report.get("status", "?"),
        "ai_explanations": f"{ai} of {len(findings)}",
    }
