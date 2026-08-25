from sqlalchemy import Column, String, Boolean, DateTime, Text, ForeignKey, Integer
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from backend.app.database import Base


class Role(Base):
    __tablename__ = "roles"

    id = Column(String(50), primary_key=True, index=True)  # "ADMIN", "MANAGER"
    name = Column(String(50), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    permissions = relationship("Permission", secondary="role_permissions", back_populates="roles", lazy="selectin")
    users = relationship("User", back_populates="role", lazy="selectin")


class Permission(Base):
    __tablename__ = "permissions"

    id = Column(String(80), primary_key=True, index=True)  # e.g. "inventory.view"
    permission_code = Column(String(80), unique=True, nullable=False, index=True)
    module = Column(String(50), nullable=False, index=True)  # dashboard, inventory, forecast, replenishment, alerts, warehouses, reports, users, audit, system
    action = Column(String(50), nullable=False)
    description = Column(Text, nullable=True)

    roles = relationship("Role", secondary="role_permissions", back_populates="permissions")


class RolePermission(Base):
    __tablename__ = "role_permissions"

    role_id = Column(String(50), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)
    permission_id = Column(String(80), ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True)


class User(Base):
    __tablename__ = "users"

    id = Column(String(50), primary_key=True, index=True)
    user_id = Column(String(50), unique=True, nullable=False, index=True)  # Username identifier
    email = Column(String(120), unique=True, nullable=False, index=True)
    full_name = Column(String(120), nullable=False)
    password_hash = Column(String(255), nullable=False)
    role_id = Column(String(50), ForeignKey("roles.id"), nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    must_change_password = Column(Boolean, default=False, nullable=False)
    last_login_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    created_by = Column(String(50), nullable=True)

    role = relationship("Role", back_populates="users", lazy="selectin")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String(50), primary_key=True, index=True)
    user_id = Column(String(50), nullable=True, index=True)
    action = Column(String(80), nullable=False, index=True)
    module = Column(String(50), nullable=False, index=True)
    entity_type = Column(String(50), nullable=True)
    entity_id = Column(String(100), nullable=True)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    ip_address = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), index=True)
