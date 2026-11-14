import logging
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import AuditLog
from typing import Optional
from uuid import UUID

logger = logging.getLogger(__name__)

async def log_audit(
    db: AsyncSession,
    action_type: str,
    user_id: Optional[UUID] = None,
    resource: Optional[str] = None,
    ip_address: Optional[str] = None,
    dependent_id: Optional[UUID] = None
):
    try:
        audit_entry = AuditLog(
            user_id=user_id,
            dependent_id=dependent_id,
            action_type=action_type,
            resource=resource,
            ip_address=ip_address
        )
        db.add(audit_entry)
        await db.commit()
    except Exception as e:
        logger.warning(f"Failed to record audit log ({action_type}): {e}")
        try:
            await db.rollback()
        except Exception:
            pass

