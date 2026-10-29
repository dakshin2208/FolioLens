"""Background jobs. Uploads return immediately; parsing and analytics run in a worker.

The CAS password is never stored in the database or in the job's arguments. It is kept in
Redis under a short-lived key that the worker reads once and deletes.
"""

import uuid

from redis import Redis
from rq import Queue, Retry

from app.config import get_settings
from app.db import SessionLocal
from app.portfolio.ingest import process_upload
from app.portfolio.models import UploadStatus
from app.reports.service import refresh_report

QUEUE_NAME = "foliolens"
PASSWORD_TTL_SECONDS = 600


def _redis() -> Redis:
    return Redis.from_url(get_settings().redis_url)


def _pw_key(upload_id: uuid.UUID) -> str:
    return f"foliolens:cas-password:{upload_id}"


def process_upload_job(upload_id: str, password: str | None = None) -> str:
    uid = uuid.UUID(upload_id)
    r = None
    if password is None and not get_settings().run_jobs_inline:
        r = _redis()
        raw = r.get(_pw_key(uid))
        password = raw.decode() if isinstance(raw, bytes) else raw
    with SessionLocal() as db:
        upload = process_upload(db, uid, password)
        # Delete the password only once the file has been processed, so a retry after a
        # crash can still open the PDF. The key also expires on its own after 10 minutes.
        if r is not None:
            r.delete(_pw_key(uid))
        if upload.status == UploadStatus.COMPLETED:
            refresh_report(db, upload.portfolio_id)
        return upload.status.value


def refresh_report_job(portfolio_id: str) -> None:
    with SessionLocal() as db:
        refresh_report(db, uuid.UUID(portfolio_id))


def enqueue_process_upload(upload_id: uuid.UUID, password: str | None) -> None:
    if get_settings().run_jobs_inline:
        process_upload_job(str(upload_id), password)
        return
    r = _redis()
    if password:
        r.setex(_pw_key(upload_id), PASSWORD_TTL_SECONDS, password)
    Queue(QUEUE_NAME, connection=r).enqueue(
        process_upload_job,
        str(upload_id),
        job_id=f"upload-{upload_id}",
        retry=Retry(max=2, interval=[10, 30]),
        result_ttl=3600,
        failure_ttl=86400,
    )


def enqueue_refresh(portfolio_id: uuid.UUID) -> None:
    if get_settings().run_jobs_inline:
        refresh_report_job(str(portfolio_id))
        return
    Queue(QUEUE_NAME, connection=_redis()).enqueue(refresh_report_job, str(portfolio_id))
