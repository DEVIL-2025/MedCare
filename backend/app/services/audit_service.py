import uuid
from datetime import datetime, timezone
from typing import Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.auth import AuditLog


class AuditService:
    """
    Persistent Audit Trail Service.
    Records authentication events, user management mutations, and critical business actions to PostgreSQL.
    """

    @staticmethod
    async def log(
        session: AsyncSession,
        action: str,
        module: str,
        user_id: Optional[str] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        old_value: Optional[str] = None,
        new_value: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> AuditLog:
        """Appends an immutable audit log record."""
        audit_id = f"AUD-{int(datetime.now(timezone.utc).timestamp())}-{uuid.uuid4().hex[:6].upper()}"
        log_entry = AuditLog(
            id=audit_id,
            user_id=user_id or "system",
            action=action,
            module=module,
            entity_type=entity_type,
            entity_id=entity_id,
            old_value=str(old_value) if old_value is not None else None,
            new_value=str(new_value) if new_value is not None else None,
            ip_address=ip_address,
            created_at=datetime.now(timezone.utc).replace(tzinfo=None)
        )
        session.add(log_entry)
        await session.flush()
        return log_entry
