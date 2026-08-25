from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, func
from pydantic import BaseModel, EmailStr
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from backend.app.database import get_db
from backend.app.models.auth import User, Role, Permission
from backend.app.services.auth_service import AuthService
from backend.app.services.audit_service import AuditService
from backend.app.dependencies.auth import get_current_user

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


class LoginRequest(BaseModel):
    identifier: str  # Can be email OR user_id
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
    clean_identifier = payload.identifier.strip()
    client_ip = request.client.host if request.client else "unknown"

    # Query user by email OR user_id (case-insensitive)
    query = select(User).where(
        or_(
            func.lower(User.email) == clean_identifier.lower(),
            func.lower(User.user_id) == clean_identifier.lower()
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

    if not AuthService.verify_password(payload.password, user.password_hash):
        await AuditService.log(
            session=db,
            action="LOGIN_FAILED",
            module="auth",
            user_id=user.user_id,
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
            user_id=user.user_id,
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

    # Collect permissions
    perms = [p.permission_code for p in user.role.permissions] if user.role and user.role.permissions else []

    # Generate JWT Token
    token_payload = {
        "sub": user.id,
        "user_id": user.user_id,
        "email": user.email,
        "role": user.role_id
    }
    access_token = AuthService.create_access_token(token_payload)

    await AuditService.log(
        session=db,
        action="LOGIN_SUCCESS",
        module="auth",
        user_id=user.user_id,
        new_value=f"Successful login as {user.role_id}",
        ip_address=client_ip
    )
    await db.commit()

    return {
        "access_token": access_token,
        "token_type": "Bearer",
        "user": {
            "id": user.id,
            "user_id": user.user_id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role_id,
            "is_active": user.is_active,
            "must_change_password": user.must_change_password,
            "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
            "permissions": perms
        }
    }


@router.get("/me")
async def get_me(current_user: User = Depends(get_current_user)) -> Dict[str, Any]:
    """Returns the authenticated user profile and permissions from the database."""
    perms = [p.permission_code for p in current_user.role.permissions] if current_user.role and current_user.role.permissions else []
    return {
        "id": current_user.id,
        "user_id": current_user.user_id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "role": current_user.role_id,
        "is_active": current_user.is_active,
        "must_change_password": current_user.must_change_password,
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
    if not AuthService.verify_password(payload.current_password, current_user.password_hash):
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
        user_id=current_user.user_id,
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
