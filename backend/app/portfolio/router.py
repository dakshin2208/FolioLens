import hashlib
import uuid
from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from app.audit.models import Consent
from app.audit.service import record_audit
from app.config import CONSENT_TEXT_VERSION, get_settings
from app.db import get_db
from app.identity.deps import get_current_user
from app.identity.models import User
from app.jobs.queue import enqueue_process_upload, enqueue_refresh
from app.portfolio.ingest import build_review, review_status
from app.portfolio.models import FileType, Instrument, Portfolio, Transaction, Upload, UploadStatus
from app.portfolio.schemas import (
    InstrumentOut,
    PortfolioCreate,
    PortfolioOut,
    PortfolioSummary,
    ReviewRequest,
    TransactionOut,
    UploadOut,
)
from app.reports.service import latest_snapshot, refresh_report
from app.storage.base import get_storage

router = APIRouter(tags=["portfolios"])

PDF_MAGIC = b"%PDF-"
CONSENT_TEXT = (
    "I confirm that I have the client's authorisation to upload and process this statement "
    "for the purpose of a portfolio review."
)


def get_owned_portfolio(
    portfolio_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Portfolio:
    """Return the portfolio only if the current user owns it. Another user's portfolio
    gets the same 404 as a missing one, so ids cannot be probed."""
    p = db.get(Portfolio, portfolio_id)
    if p is None or p.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Portfolio not found")
    return p


def get_owned_upload(
    upload_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Upload:
    u = db.get(Upload, upload_id)
    if u is None or u.portfolio.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Upload not found")
    return u


# ---- Portfolios --------------------------------------------------------------------------


@router.get("/portfolios", response_model=list[PortfolioSummary])
def list_portfolios(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    out = []
    for p in db.scalars(
        select(Portfolio).where(Portfolio.owner_id == user.id).order_by(Portfolio.created_at.desc())
    ):
        s = PortfolioSummary.model_validate(p)
        snap = latest_snapshot(db, p.id)
        if snap and snap.report.get("status") == "ok":
            s.current_value = snap.report["overview"]["current_value"]
            s.xirr = snap.report["overview"]["xirr"]
            s.findings = len(snap.report["findings"])
            s.valuation_date = snap.valuation_date
        last = db.scalar(
            select(Upload).where(Upload.portfolio_id == p.id).order_by(Upload.created_at.desc()).limit(1)
        )
        s.last_upload_status = last.status.value if last else None
        out.append(s)
    return out


@router.post("/portfolios", response_model=PortfolioOut, status_code=status.HTTP_201_CREATED)
def create_portfolio(
    body: PortfolioCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Portfolio:
    p = Portfolio(owner_id=user.id, name=body.name.strip(), client_name=body.client_name.strip())
    db.add(p)
    db.flush()
    record_audit(db, user.id, "portfolio.create", "portfolio", p.id)
    db.commit()
    return p


@router.get("/portfolios/{portfolio_id}", response_model=PortfolioOut)
def get_portfolio(p: Portfolio = Depends(get_owned_portfolio)) -> Portfolio:
    return p


@router.delete("/portfolios/{portfolio_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_portfolio(
    p: Portfolio = Depends(get_owned_portfolio),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """Deletes the portfolio with all its transactions, uploads, files and reports."""
    storage = get_storage()
    for u in p.uploads:
        if u.storage_key:
            storage.delete(u.storage_key)
    record_audit(db, user.id, "portfolio.delete", "portfolio", p.id)
    db.delete(p)
    db.commit()


# ---- Uploads -----------------------------------------------------------------------------


@router.get("/consent-text")
def consent_text() -> dict[str, str]:
    return {"version": CONSENT_TEXT_VERSION, "text": CONSENT_TEXT}


@router.post(
    "/portfolios/{portfolio_id}/uploads", response_model=UploadOut, status_code=status.HTTP_202_ACCEPTED
)
async def create_upload(
    file: UploadFile = File(...),
    file_type: FileType = Form(...),
    consent: bool = Form(...),
    password: str | None = Form(default=None),
    p: Portfolio = Depends(get_owned_portfolio),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Upload:
    if not consent:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Confirm you are authorised to process this client's statement"
        )
    max_bytes = get_settings().max_upload_mb * 1024 * 1024
    data = await file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise HTTPException(
            status.HTTP_413_CONTENT_TOO_LARGE, f"File is larger than {get_settings().max_upload_mb} MB"
        )
    if not data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The file is empty")
    is_pdf = data.startswith(PDF_MAGIC)
    if (file_type == FileType.CAS_PDF) != is_pdf:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "File content does not match the selected statement type"
        )
    if file_type == FileType.CAS_PDF and not password:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The CAS PDF password is required")

    upload = Upload(
        portfolio_id=p.id,
        filename=(file.filename or "statement")[:255],
        file_type=file_type,
        file_sha256=hashlib.sha256(data).hexdigest(),
    )
    db.add(upload)
    db.flush()
    upload.storage_key = f"{p.id}/{upload.id}"
    get_storage().put(upload.storage_key, data)
    db.add(Consent(user_id=user.id, portfolio_id=p.id, consent_text_version=CONSENT_TEXT_VERSION))
    record_audit(
        db,
        user.id,
        "upload.create",
        "upload",
        upload.id,
        {"file_type": file_type.value, "consent_version": CONSENT_TEXT_VERSION},
    )
    db.commit()

    enqueue_process_upload(upload.id, password)
    db.refresh(upload)
    return upload


@router.get("/portfolios/{portfolio_id}/uploads", response_model=list[UploadOut])
def list_uploads(p: Portfolio = Depends(get_owned_portfolio), db: Session = Depends(get_db)):
    return db.scalars(
        select(Upload).where(Upload.portfolio_id == p.id).order_by(Upload.created_at.desc())
    ).all()


@router.get("/uploads/{upload_id}", response_model=UploadOut)
def get_upload(u: Upload = Depends(get_owned_upload)) -> Upload:
    return u


@router.post("/uploads/{upload_id}/review", response_model=UploadOut)
def review_upload(
    body: ReviewRequest,
    u: Upload = Depends(get_owned_upload),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Upload:
    if u.status not in (UploadStatus.NEEDS_REVIEW, UploadStatus.COMPLETED):
        raise HTTPException(status.HTTP_409_CONFLICT, f"Upload is {u.status.value}")
    for m in body.mappings:
        if db.get(Instrument, m.instrument_id) is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unknown instrument {m.instrument_id}")
        db.execute(
            update(Transaction)
            .where(
                Transaction.portfolio_id == u.portfolio_id,
                Transaction.raw_identifier == m.raw_identifier,
            )
            .values(instrument_id=m.instrument_id)
        )
    previous = dict(u.review or {})
    if body.acknowledge_reconciliation:
        previous["reconciliation_acknowledged"] = True
    u.review = previous
    review = build_review(db, u)
    for k in ("inserted", "duplicates", "warnings", "format"):
        if k in previous:
            review[k] = previous[k]
    u.review = review
    u.status = review_status(review)
    record_audit(
        db,
        user.id,
        "upload.review",
        "upload",
        u.id,
        {"mappings": len(body.mappings), "ack": body.acknowledge_reconciliation},
    )
    db.commit()
    if u.status == UploadStatus.COMPLETED:
        enqueue_refresh(u.portfolio_id)
    return u


# ---- Ledger and instruments ----------------------------------------------------------------


@router.get("/portfolios/{portfolio_id}/transactions", response_model=list[TransactionOut])
def list_transactions(
    p: Portfolio = Depends(get_owned_portfolio),
    db: Session = Depends(get_db),
    limit: int = Query(500, le=5000),
    offset: int = Query(0, ge=0),
):
    return db.scalars(
        select(Transaction)
        .where(Transaction.portfolio_id == p.id)
        .order_by(Transaction.date.desc(), Transaction.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()


@router.get("/instruments", response_model=list[InstrumentOut])
def search_instruments(
    q: str = Query(min_length=2, max_length=60),
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    pattern = f"%{q}%"
    return db.scalars(
        select(Instrument)
        .where(
            or_(
                Instrument.name.ilike(pattern),
                Instrument.isin.ilike(pattern),
                Instrument.symbol.ilike(pattern),
            )
        )
        .order_by(Instrument.name)
        .limit(20)
    ).all()


# ---- Reports -----------------------------------------------------------------------------

SECTIONS = {
    "report": None,
    "holdings": ("overview", "holdings"),
    "allocation": ("allocation", "overlap"),
    "performance": ("performance",),
    "risk": ("risk",),
    "insights": ("findings", "data_quality"),
}


def _report_or_404(db: Session, p: Portfolio) -> dict[str, Any]:
    snap = latest_snapshot(db, p.id)
    if snap is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No report yet. Upload a statement first.")
    return {"snapshot_id": str(snap.id), "created_at": snap.created_at.isoformat(), **snap.report}


@router.get("/portfolios/{portfolio_id}/{section}")
def get_report_section(
    section: str, p: Portfolio = Depends(get_owned_portfolio), db: Session = Depends(get_db)
) -> dict[str, Any]:
    if section not in SECTIONS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    report = _report_or_404(db, p)
    keys = SECTIONS[section]
    if keys is None or report.get("status") != "ok":
        return report
    return {"meta": report["meta"], **{k: report[k] for k in keys}}


@router.post("/portfolios/{portfolio_id}/report/refresh")
def refresh(p: Portfolio = Depends(get_owned_portfolio), db: Session = Depends(get_db)):
    snap = refresh_report(db, p.id)
    return {"snapshot_id": str(snap.id), "status": snap.report.get("status")}
