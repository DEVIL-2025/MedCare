from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, func, desc
from pydantic import BaseModel, EmailStr
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import uuid

from backend.app.database import get_db
from backend.app.models.auth import User, Role, Permission, AuditLog
from backend.app.services.auth_service import AuthService
from backend.app.services.audit_service import AuditService
from backend.app.dependencies.auth import require_admin, get_current_user
from backend.app.utils.timezone import get_utc_now, format_ist_datetime

router = APIRouter(tags=["User Management"])


class UserCreateRequest(BaseModel):
    user_id: str
    email: EmailStr
    full_name: str
    role_id: str  # "ADMIN" or "MANAGER"
    temporary_password: Optional[str] = None


class UserUpdateRequest(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    role_id: Optional[str] = None
    is_active: Optional[bool] = None


@router.get("/api/users")
async def list_users(
    search: Optional[str] = None,
    role: Optional[str] = None,
    current_admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
) -> List[Dict[str, Any]]:
    """Lists all users from PostgreSQL (Admin Only)."""
    query = select(User).order_by(User.created_at.desc())
    
    if search:
        s = f"%{search.lower()}%"
        query = query.where(
            or_(
                func.lower(User.user_id).like(s),
                func.lower(User.email).like(s),
                func.lower(User.full_name).like(s)
            )
        )
    if role and role != "All":
        query = query.where(User.role_id == role)

    res = await db.execute(query)
    users = res.scalars().all()

    return [
        {
            "id": u.id,
            "user_id": u.user_id,
            "email": u.email,
            "full_name": u.full_name,
            "role": u.role_id,
            "role_name": u.role.name if u.role else u.role_id,
            "is_active": u.is_active,
            "must_change_password": u.must_change_password,
            "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
            "last_login_formatted": format_ist_datetime(u.last_login_at) if u.last_login_at else "Never",
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "created_at_formatted": format_ist_datetime(u.created_at),
            "created_by": u.created_by
        }
        for u in users
    ]


@router.post("/api/users")
async def create_user(
    payload: UserCreateRequest,
    request: Request,
    current_admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Creates a new user with a secure temporary password (Admin Only)."""
    clean_user_id = payload.user_id.strip()
    clean_email = payload.email.strip().lower()
    clean_role = payload.role_id.strip().upper()

    # Check for existing user_id or email
    existing = await db.execute(
        select(User).where(
            or_(
                func.lower(User.user_id) == clean_user_id.lower(),
                func.lower(User.email) == clean_email
            )
        )
    )
    if existing.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User with ID '{clean_user_id}' or Email '{clean_email}' already exists."
        )

    # Validate role
    role_res = await db.execute(select(Role).where(Role.id == clean_role))
    role_obj = role_res.scalars().first()
    if not role_obj:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role '{clean_role}'. Allowed roles are 'ADMIN', 'MANAGER'."
        )

    temp_password = payload.temporary_password or AuthService.generate_temporary_password(12)
    pwd_hash = AuthService.hash_password(temp_password)

    user_pk = f"USR-{uuid.uuid4().hex[:8].upper()}"
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)

    new_user = User(
        id=user_pk,
        user_id=clean_user_id,
        email=clean_email,
        full_name=payload.full_name.strip(),
        password_hash=pwd_hash,
        role_id=clean_role,
        is_active=True,
        must_change_password=True,
        created_at=now_utc,
        updated_at=now_utc,
        created_by=current_admin.user_id
    )
    db.add(new_user)

    client_ip = request.client.host if request.client else "unknown"
    await AuditService.log(
        session=db,
        action="USER_CREATED",
        module="users",
        user_id=current_admin.user_id,
        entity_type="User",
        entity_id=clean_user_id,
        new_value=f"Created user {clean_user_id} with role {clean_role}",
        ip_address=client_ip
    )
    await db.commit()

    return {
        "success": True,
        "message": f"User '{clean_user_id}' created successfully.",
        "user": {
            "id": new_user.id,
            "user_id": new_user.user_id,
            "email": new_user.email,
            "full_name": new_user.full_name,
            "role": new_user.role_id,
            "is_active": new_user.is_active,
            "must_change_password": new_user.must_change_password,
            "temporary_password": temp_password
        }
    }


@router.put("/api/users/{user_pk}")
async def update_user(
    user_pk: str,
    payload: UserUpdateRequest,
    request: Request,
    current_admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Updates user information, role assignment, or active status (Admin Only)."""
    res = await db.execute(select(User).where(User.id == user_pk))
    target_user = res.scalars().first()
    if not target_user:
        raise HTTPException(status_code=404, detail=f"User '{user_pk}' not found.")

    # Guard against admin locking themselves out
    if target_user.id == current_admin.id and payload.is_active is False:
        raise HTTPException(status_code=400, detail="Administrators cannot deactivate their own active account.")

    old_state = f"Name: {target_user.full_name}, Email: {target_user.email}, Role: {target_user.role_id}, Active: {target_user.is_active}"

    if payload.full_name is not None:
        target_user.full_name = payload.full_name.strip()
    if payload.email is not None:
        clean_email = payload.email.strip().lower()
        # Check uniqueness if changed
        if clean_email != target_user.email.lower():
            dup = await db.execute(select(User).where(func.lower(User.email) == clean_email, User.id != target_user.id))
            if dup.scalars().first():
                raise HTTPException(status_code=400, detail=f"Email '{clean_email}' is already in use by another user.")
            target_user.email = clean_email
    if payload.role_id is not None:
        clean_role = payload.role_id.strip().upper()
        role_res = await db.execute(select(Role).where(Role.id == clean_role))
        if not role_res.scalars().first():
            raise HTTPException(status_code=400, detail=f"Invalid role '{clean_role}'.")
        target_user.role_id = clean_role
    if payload.is_active is not None:
        target_user.is_active = payload.is_active

    target_user.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

    new_state = f"Name: {target_user.full_name}, Email: {target_user.email}, Role: {target_user.role_id}, Active: {target_user.is_active}"

    client_ip = request.client.host if request.client else "unknown"
    await AuditService.log(
        session=db,
        action="USER_UPDATED",
        module="users",
        user_id=current_admin.user_id,
        entity_type="User",
        entity_id=target_user.user_id,
        old_value=old_state,
        new_value=new_state,
        ip_address=client_ip
    )
    await db.commit()

    return {
        "success": True,
        "message": f"User '{target_user.user_id}' updated successfully.",
        "user": {
            "id": target_user.id,
            "user_id": target_user.user_id,
            "email": target_user.email,
            "full_name": target_user.full_name,
            "role": target_user.role_id,
            "is_active": target_user.is_active
        }
    }


@router.post("/api/users/{user_pk}/reset-password")
async def reset_user_password(
    user_pk: str,
    request: Request,
    current_admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Generates a new secure temporary password for a user and enforces password change on next login (Admin Only)."""
    res = await db.execute(select(User).where(User.id == user_pk))
    target_user = res.scalars().first()
    if not target_user:
        raise HTTPException(status_code=404, detail=f"User '{user_pk}' not found.")

    temp_password = AuthService.generate_temporary_password(12)
    target_user.password_hash = AuthService.hash_password(temp_password)
    target_user.must_change_password = True
    target_user.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

    client_ip = request.client.host if request.client else "unknown"
    await AuditService.log(
        session=db,
        action="PASSWORD_RESET",
        module="users",
        user_id=current_admin.user_id,
        entity_type="User",
        entity_id=target_user.user_id,
        new_value=f"Password reset triggered by {current_admin.user_id}",
        ip_address=client_ip
    )
    await db.commit()

    return {
        "success": True,
        "message": f"Password for user '{target_user.user_id}' has been reset successfully.",
        "user_id": target_user.user_id,
        "temporary_password": temp_password
    }


@router.post("/api/users/{user_pk}/toggle-status")
async def toggle_user_status(
    user_pk: str,
    request: Request,
    current_admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Toggles user active/deactivated status (Admin Only)."""
    res = await db.execute(select(User).where(User.id == user_pk))
    target_user = res.scalars().first()
    if not target_user:
        raise HTTPException(status_code=404, detail=f"User '{user_pk}' not found.")

    if target_user.id == current_admin.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate own administrator account.")

    target_user.is_active = not target_user.is_active
    target_user.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

    action_label = "USER_ACTIVATED" if target_user.is_active else "USER_DEACTIVATED"
    client_ip = request.client.host if request.client else "unknown"
    await AuditService.log(
        session=db,
        action=action_label,
        module="users",
        user_id=current_admin.user_id,
        entity_type="User",
        entity_id=target_user.user_id,
        new_value=f"Status changed to {'Active' if target_user.is_active else 'Inactive'}",
        ip_address=client_ip
    )
    await db.commit()

    return {
        "success": True,
        "user_id": target_user.user_id,
        "is_active": target_user.is_active,
        "message": f"User '{target_user.user_id}' is now {'Active' if target_user.is_active else 'Deactivated'}."
    }


@router.get("/api/users/roles")
async def list_roles(
    current_admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
) -> List[Dict[str, Any]]:
    """Returns available roles and their permission summary (Admin Only)."""
    res = await db.execute(select(Role).order_by(Role.name.asc()))
    roles = res.scalars().all()
    return [
        {
            "id": r.id,
            "name": r.name,
            "description": r.description,
            "permission_count": len(r.permissions) if r.permissions else 0
        }
        for r in roles
    ]


@router.get("/api/audit-logs")
async def list_audit_logs(
    module: Optional[str] = None,
    action: Optional[str] = None,
    user_id: Optional[str] = None,
    limit: int = Query(50, ge=1, le=500),
    current_admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Returns persistent audit trail records from PostgreSQL (Admin Only)."""
    query = select(AuditLog).order_by(desc(AuditLog.created_at))
    
    if module and module != "All":
        query = query.where(AuditLog.module == module)
    if action and action != "All":
        query = query.where(AuditLog.action == action)
    if user_id:
        query = query.where(func.lower(AuditLog.user_id) == user_id.lower())

    res = await db.execute(query.limit(limit))
    logs = res.scalars().all()

    return {
        "total": len(logs),
        "logs": [
            {
                "id": l.id,
                "user_id": l.user_id,
                "action": l.action,
                "module": l.module,
                "entity_type": l.entity_type,
                "entity_id": l.entity_id,
                "old_value": l.old_value,
                "new_value": l.new_value,
                "ip_address": l.ip_address,
                "timestamp": format_ist_datetime(l.created_at),
                "formattedTime": format_ist_datetime(l.created_at),
                "created_at": l.created_at.isoformat() if l.created_at else None
            }
            for l in logs
        ]
    }
