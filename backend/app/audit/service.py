import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.audit.models import AuditLog


def record_audit(
    db: Session,
    actor_id: uuid.UUID | None,
    action: str,
    resource_type: str,
    resource_id: uuid.UUID | str | None = None,
    meta: dict[str, Any] | None = None,
) -> None:
    db.add(
        AuditLog(
            actor_id=actor_id,
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id else None,
            meta=meta or {},
        )
    )
