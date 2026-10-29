"""Deletes raw files of uploads that failed more than 24 hours ago (D-09).

Run on a schedule, e.g. hourly: `python -m app.jobs.cleanup`
"""

from datetime import timedelta

from sqlalchemy import select

from app.db import SessionLocal, utcnow
from app.portfolio.models import Upload, UploadStatus
from app.storage.base import get_storage

FAILED_RETENTION = timedelta(hours=24)


def cleanup_failed_uploads() -> int:
    storage = get_storage()
    removed = 0
    with SessionLocal() as db:
        stale = db.scalars(
            select(Upload).where(
                Upload.status == UploadStatus.FAILED,
                Upload.storage_key.is_not(None),
                Upload.created_at < utcnow() - FAILED_RETENTION,
            )
        ).all()
        for u in stale:
            storage.delete(u.storage_key or "")
            u.storage_key = None
            removed += 1
        db.commit()
    return removed


if __name__ == "__main__":
    print(f"Removed {cleanup_failed_uploads()} failed upload files")
