from fastapi import Depends, HTTPException, status, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import Optional, Set

from backend.app.database import get_db
from backend.app.models.auth import User, Role
from backend.app.services.auth_service import AuthService


async def get_current_user(
    request: Request,
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Extracts and validates JWT Bearer token from the Authorization header.
    Returns the authenticated User instance with permissions set attached.
    """
    if not authorization:
        # Check query param token for websocket or direct links if provided
        token_param = request.query_params.get("token")
        if token_param:
            authorization = f"Bearer {token_param}"

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please log in.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization.split(" ")[1].strip()
    payload = AuthService.decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication session. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_pk = payload.get("sub")
    if not user_pk:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session token payload.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    query = (
        select(User)
        .options(selectinload(User.role).selectinload(Role.permissions))
        .where(User.id == user_pk)
    )
    res = await db.execute(query)
    user = res.scalars().first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account associated with this session no longer exists.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not bool(getattr(user, "is_active", True)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been deactivated. Please contact an administrator.",
        )

    # Attach set of permission codes for fast lookup
    perms: Set[str] = set()
    user_role = getattr(user, "role", None)
    if user_role and getattr(user_role, "permissions", None):
        perms = {
            p.permission_code
            for p in user_role.permissions
            if getattr(p, "permission_code", None)
        }
    
    # Attach dynamically
    setattr(user, "permission_codes", perms)
    return user


async def get_optional_user(
    request: Request,
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db)
) -> Optional[User]:
    """Gracefully extracts current user if token is provided, otherwise returns None."""
    try:
        if authorization or request.query_params.get("token"):
            return await get_current_user(request, authorization, db)
    except HTTPException:
        pass
    return None


def require_permission(permission_code: str):
    """Factory creating a FastAPI dependency that verifies the user possesses a specific permission code."""
    async def permission_checker(current_user: User = Depends(get_current_user)) -> User:
        user_role_id = str(getattr(current_user, "role_id", "") or "")
        if user_role_id.upper() == "ADMIN":
            return current_user
        
        perms = getattr(current_user, "permission_codes", set())
        if permission_code not in perms:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access Denied: Insufficient permissions. Required: '{permission_code}'.",
            )
        return current_user

    return permission_checker


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """FastAPI dependency that restricts endpoint access strictly to ADMIN users."""
    user_role_id = str(getattr(current_user, "role_id", "") or "")
    if user_role_id.upper() != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access Denied: Administrator privileges required.",
        )
    return current_user
