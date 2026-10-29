"""Turns an uploaded file into ledger rows: parse -> match -> insert -> reconcile.

Safe to run twice: each row has a deterministic `source_ref`, and duplicates are skipped
by a unique constraint, so a retried job never double-counts a transaction.
"""

import hashlib
import logging
import uuid
from collections import Counter, defaultdict
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db import utcnow
from app.portfolio.matching import match_identifier, suggest
from app.portfolio.models import FileType, Transaction, Upload, UploadStatus
from app.portfolio.parsers.base import ParsedStatement, ParseError
from app.portfolio.parsers.cas import parse_cas
from app.portfolio.parsers.csv_formats import parse_generic_csv, parse_zerodha_tradebook
from app.storage.base import get_storage

log = logging.getLogger(__name__)
UNIT_TOLERANCE = Decimal("0.001")


def parse_file(file_type: FileType, data: bytes, password: str | None) -> ParsedStatement:
    if file_type == FileType.CAS_PDF:
        if not password:
            raise ParseError("A password is required to open the CAS PDF")
        return parse_cas(data, password)
    if file_type == FileType.ZERODHA_TRADEBOOK:
        return parse_zerodha_tradebook(data)
    return parse_generic_csv(data)


def _source_ref(parts: tuple[object, ...], occurrence: int) -> str:
    raw = "|".join(str(p) for p in parts) + f"|{occurrence}"
    return hashlib.sha256(raw.encode()).hexdigest()


def process_upload(db: Session, upload_id: uuid.UUID, password: str | None = None) -> Upload:
    upload = db.get(Upload, upload_id)
    if upload is None:
        raise ValueError(f"Upload {upload_id} not found")
    if upload.status in (UploadStatus.COMPLETED, UploadStatus.NEEDS_REVIEW):
        return upload  # already processed; retries are no-ops
    upload.status = UploadStatus.PROCESSING
    db.commit()

    storage = get_storage()
    try:
        if not upload.storage_key:
            raise ParseError("The uploaded file is no longer available; upload it again")
        statement = parse_file(upload.file_type, storage.get(upload.storage_key), password)
    except ParseError as e:
        upload.status, upload.error = UploadStatus.FAILED, str(e)[:1000]
        db.commit()
        return upload
    except Exception:
        log.exception("Unexpected parser failure for upload %s", upload_id)
        upload.status, upload.error = UploadStatus.FAILED, "The file could not be processed"
        db.commit()
        return upload

    inserted, duplicates = _insert_transactions(db, upload, statement)
    review = build_review(db, upload, statement.closing_units, statement.scheme_names)
    review.update(
        {
            "inserted": inserted,
            "duplicates": duplicates,
            "warnings": statement.warnings,
            "format": statement.format,
        }
    )
    upload.review = review
    upload.parsed_at = utcnow()
    upload.status = review_status(review)

    # Raw statements are deleted as soon as they are parsed (D-09).
    storage.delete(upload.storage_key)
    upload.storage_key = None
    db.commit()
    return upload


def _insert_transactions(db: Session, upload: Upload, statement: ParsedStatement) -> tuple[int, int]:
    seen: Counter[tuple[object, ...]] = Counter()
    rows = []
    match_cache: dict[str, uuid.UUID | None] = {}
    for t in statement.transactions:
        key = (t.raw_identifier, t.date, t.type, t.units, t.amount, t.external_ref)
        seen[key] += 1
        if t.raw_identifier not in match_cache:
            inst = match_identifier(db, t.raw_identifier, t.symbol)
            match_cache[t.raw_identifier] = inst.id if inst else None
        rows.append(
            {
                "portfolio_id": upload.portfolio_id,
                "upload_id": upload.id,
                "instrument_id": match_cache[t.raw_identifier],
                "raw_identifier": t.raw_identifier[:64],
                "raw_name": (t.raw_name or "")[:255] or None,
                "date": t.date,
                "type": t.type,
                "units": t.units,
                "price": t.price,
                "amount": t.amount,
                "source_ref": _source_ref(key, seen[key]),
            }
        )
    if not rows:
        return 0, 0
    stmt = (
        insert(Transaction)
        .values(rows)
        .on_conflict_do_nothing(constraint="uq_txn_source")
        .returning(Transaction.id)
    )
    inserted = len(db.execute(stmt).all())
    return inserted, len(rows) - inserted


def build_review(
    db: Session,
    upload: Upload,
    closing_units: dict[str, Decimal] | None = None,
    scheme_names: dict[str, str] | None = None,
) -> dict[str, object]:
    """Unmatched identifiers and unit reconciliation for everything in this portfolio."""
    txns = db.scalars(select(Transaction).where(Transaction.portfolio_id == upload.portfolio_id)).all()

    unmatched: dict[str, dict[str, object]] = {}
    for t in txns:
        if t.instrument_id is None:
            u = unmatched.setdefault(
                t.raw_identifier, {"raw_identifier": t.raw_identifier, "raw_name": t.raw_name, "count": 0}
            )
            u["count"] = int(u["count"]) + 1  # type: ignore[call-overload]
    for u in unmatched.values():
        s = suggest(db, u["raw_name"])  # type: ignore[arg-type]
        u["suggestion"] = s.__dict__ if s else None

    reconciliation = []
    closing = (
        closing_units
        if closing_units is not None
        else {k: Decimal(str(v)) for k, v in (upload.review or {}).get("closing_units", {}).items()}
    )
    if closing:
        ledger: dict[str, Decimal] = defaultdict(Decimal)
        for t in txns:
            sign = (
                1
                if t.type in ("buy", "dividend_reinvest", "switch_in")
                else -1
                if t.type in ("sell", "switch_out")
                else 0
            )
            ledger[t.raw_identifier] += sign * t.units
        names = scheme_names or (upload.review or {}).get("scheme_names", {})
        for isin, stmt_units in closing.items():
            variance = ledger[isin] - stmt_units
            reconciliation.append(
                {
                    "identifier": isin,
                    "name": names.get(isin, isin),
                    "ledger_units": float(ledger[isin]),
                    "statement_units": float(stmt_units),
                    "variance": float(variance),
                    "ok": abs(variance) <= UNIT_TOLERANCE,
                }
            )
    return {
        "unmatched": list(unmatched.values()),
        "reconciliation": reconciliation,
        "reconciliation_acknowledged": (upload.review or {}).get("reconciliation_acknowledged", False),
        "closing_units": {k: str(v) for k, v in closing.items()},
        "scheme_names": dict(scheme_names or (upload.review or {}).get("scheme_names", {})),
    }


def review_status(review: dict[str, object]) -> UploadStatus:
    recon_bad = any(not r["ok"] for r in review["reconciliation"])  # type: ignore[attr-defined,index]
    if review["unmatched"] or (recon_bad and not review.get("reconciliation_acknowledged")):
        return UploadStatus.NEEDS_REVIEW
    return UploadStatus.COMPLETED
