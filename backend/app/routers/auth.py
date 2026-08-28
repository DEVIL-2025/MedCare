from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, func
from sqlalchemy.orm import selectinload
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from backend.app.database import get_db
from backend.app.models.auth import User, Role
from backend.app.services.auth_service import AuthService
from backend.app.services.audit_service import AuditService
from backend.app.dependencies.auth import get_current_user

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


class LoginRequest(BaseModel):
    identifier: Optional[str] = None  # Can be email OR user_id
    email: Optional[str] = None
    username: Optional[str] = None
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class UserProfileResponse(BaseModel):
    id: str
    user_id: str
    email: str
    full_name: str
    role: str
    is_active: bool
    must_change_password: bool
    last_login_at: Optional[str] = None
    permissions: List[str]


@router.post("/login")
async def login(
    payload: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Authenticates a user via Email or User ID and Password.
    Returns JWT access token with user profile, role, and permission capabilities.
    """
    raw_ident = payload.identifier or payload.email or payload.username or ""
    clean_identifier = raw_ident.strip()
    if not clean_identifier:
        raise HTTPException(status_code=400, detail="Email, username, or user ID is required.")
    client_ip = request.client.host if request.client else "unknown"

    # Query user by email OR user_id (case-insensitive) with eager-loaded role and permissions
    query = (
        select(User)
        .options(selectinload(User.role).selectinload(Role.permissions))
        .where(
            or_(
                func.lower(User.email) == clean_identifier.lower(),
                func.lower(User.user_id) == clean_identifier.lower()
            )
        )
    )
    res = await db.execute(query)
    user = res.scalars().first()

    if not user:
        await AuditService.log(
            session=db,
            action="LOGIN_FAILED",
            module="auth",
            user_id=clean_identifier,
            new_value=f"Failed login attempt for unknown user: {clean_identifier}",
            ip_address=client_ip
        )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Email/User ID or Password."
        )

    stored_hash = str(user.password_hash or "")
    current_uid = str(user.user_id or clean_identifier)

    if not AuthService.verify_password(payload.password, stored_hash):
        await AuditService.log(
            session=db,
            action="LOGIN_FAILED",
            module="auth",
            user_id=current_uid,
            new_value="Incorrect password provided",
            ip_address=client_ip
        )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Email/User ID or Password."
        )

    if not user.is_active:
        await AuditService.log(
            session=db,
            action="LOGIN_FAILED",
            module="auth",
            user_id=current_uid,
            new_value="Login attempted on deactivated account",
            ip_address=client_ip
        )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been deactivated. Please contact an administrator."
        )

    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    user.last_login_at = now_utc

    # Collect permissions defensively
    user_role = getattr(user, "role", None)
    role_perms = getattr(user_role, "permissions", []) if user_role else []
    perms = [p.permission_code for p in role_perms if hasattr(p, "permission_code")]

    user_id_val = str(getattr(user, "id", "") or "")
    username_val = str(getattr(user, "user_id", "") or "")
    email_val = str(getattr(user, "email", "") or "")
    full_name_val = str(getattr(user, "full_name", "") or "")
    role_id_val = str(getattr(user, "role_id", "") or "")
    is_active_val = bool(getattr(user, "is_active", True))
    must_change_pwd_val = bool(getattr(user, "must_change_password", False))

    # Generate JWT Token
    token_payload = {
        "sub": user_id_val,
        "user_id": username_val,
        "email": email_val,
        "role": role_id_val
    }
    access_token = AuthService.create_access_token(token_payload)

    await AuditService.log(
        session=db,
        action="LOGIN_SUCCESS",
        module="auth",
        user_id=username_val,
        new_value=f"Successful login as {role_id_val}",
        ip_address=client_ip
    )
    await db.commit()

    return {
        "access_token": access_token,
        "token_type": "Bearer",
        "user": {
            "id": user_id_val,
            "user_id": username_val,
            "email": email_val,
            "full_name": full_name_val,
            "role": role_id_val,
            "is_active": is_active_val,
            "must_change_password": must_change_pwd_val,
            "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
            "permissions": perms
        }
    }


@router.get("/me")
async def get_me(current_user: User = Depends(get_current_user)) -> Dict[str, Any]:
    """Returns the authenticated user profile and permissions from the database."""
    user_role = getattr(current_user, "role", None)
    role_perms = getattr(user_role, "permissions", []) if user_role else []
    perms = [p.permission_code for p in role_perms if hasattr(p, "permission_code")]
    
    return {
        "id": str(getattr(current_user, "id", "") or ""),
        "user_id": str(getattr(current_user, "user_id", "") or ""),
        "email": str(getattr(current_user, "email", "") or ""),
        "full_name": str(getattr(current_user, "full_name", "") or ""),
        "role": str(getattr(current_user, "role_id", "") or ""),
        "is_active": bool(getattr(current_user, "is_active", True)),
        "must_change_password": bool(getattr(current_user, "must_change_password", False)),
        "last_login_at": current_user.last_login_at.isoformat() if current_user.last_login_at else None,
        "permissions": perms
    }


@router.post("/change-password")
async def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Allows authenticated user to change their password and clears the must_change_password requirement."""
    stored_user_pwd = str(current_user.password_hash or "")
    if not AuthService.verify_password(payload.current_password, stored_user_pwd):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password verification failed."
        )

    if len(payload.new_password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be at least 6 characters in length."
        )

    current_user.password_hash = AuthService.hash_password(payload.new_password)
    current_user.must_change_password = False
    current_user.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

    client_ip = request.client.host if request.client else "unknown"
    await AuditService.log(
        session=db,
        action="PASSWORD_CHANGED",
        module="auth",
        user_id=str(current_user.user_id or ""),
        new_value="Password changed by user",
        ip_address=client_ip
    )
    await db.commit()

    return {
        "success": True,
        "message": "Password updated successfully."
    }


@router.post("/logout")
async def logout(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Logs user logout in audit trail."""
    client_ip = request.client.host if request.client else "unknown"
    await AuditService.log(
        session=db,
        action="LOGOUT",
        module="auth",
        user_id=current_user.user_id,
        new_value="User logged out",
        ip_address=client_ip
    )
    await db.commit()
    return {
        "success": True,
        "message": "Logged out successfully."
    }
