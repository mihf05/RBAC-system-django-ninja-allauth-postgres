"""
Pydantic schemas for RBAC API endpoints.
"""
from ninja import Schema
from pydantic import field_validator
from typing import Optional, List
from datetime import datetime


# ── Role Schemas ──────────────────────────────────────────────────────

class RoleCreateSchema(Schema):
    """Schema for creating a new role."""
    name: str
    description: str = ""
    is_active: bool = True

    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        v = v.strip()
        if not v:
            raise ValueError('Role name is required')
        if len(v) > 100:
            raise ValueError('Role name must be 100 characters or fewer')
        if len(v) < 2:
            raise ValueError('Role name must be at least 2 characters')
        return v


class RoleUpdateSchema(Schema):
    """Schema for updating a role."""
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None

    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        if v is not None:
            v = v.strip()
            if not v:
                raise ValueError('Role name cannot be empty')
            if len(v) > 100:
                raise ValueError('Role name must be 100 characters or fewer')
            if len(v) < 2:
                raise ValueError('Role name must be at least 2 characters')
        return v


class PermissionSchema(Schema):
    """Schema for a single permission entry."""
    resource_id: int
    can_read: bool = False
    can_write: bool = False
    can_update: bool = False
    can_delete: bool = False


class PermissionResponseSchema(Schema):
    """Response schema for a permission entry."""
    id: int
    resource_id: int
    resource_name: str
    can_read: bool
    can_write: bool
    can_update: bool
    can_delete: bool
    # Operation capabilities of the resource itself
    has_read: bool
    has_write: bool
    has_update: bool
    has_delete: bool


class RoleResponseSchema(Schema):
    """Response schema for role data."""
    id: int
    name: str
    description: str
    is_active: bool
    is_system: bool
    user_count: int
    created_at: datetime
    updated_at: datetime
    permissions: List[PermissionResponseSchema] = []


class RoleListSchema(Schema):
    """Brief role schema for lists."""
    id: int
    name: str
    description: str
    is_active: bool
    is_system: bool
    user_count: int
    created_at: datetime


class SetPermissionsSchema(Schema):
    """Schema for setting the full permissions matrix for a role."""
    permissions: List[PermissionSchema]


# ── Resource Schemas ──────────────────────────────────────────────────

class ResourceCreateSchema(Schema):
    """Schema for creating a new resource."""
    name: str
    description: str = ""
    has_read: bool = True
    has_write: bool = True
    has_update: bool = True
    has_delete: bool = True

    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        v = v.strip()
        if not v:
            raise ValueError('Resource name is required')
        if len(v) > 100:
            raise ValueError('Resource name must be 100 characters or fewer')
        if len(v) < 2:
            raise ValueError('Resource name must be at least 2 characters')
        return v


class ResourceUpdateSchema(Schema):
    """Schema for updating a resource."""
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    has_read: Optional[bool] = None
    has_write: Optional[bool] = None
    has_update: Optional[bool] = None
    has_delete: Optional[bool] = None

    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        if v is not None:
            v = v.strip()
            if not v:
                raise ValueError('Resource name cannot be empty')
            if len(v) > 100:
                raise ValueError('Resource name must be 100 characters or fewer')
        return v


class ResourceResponseSchema(Schema):
    """Response schema for resource data."""
    id: int
    name: str
    description: str
    is_active: bool
    has_read: bool
    has_write: bool
    has_update: bool
    has_delete: bool
    created_at: datetime


# ── User Management Schemas ───────────────────────────────────────────

class UserRoleBadgeSchema(Schema):
    """Brief role info for user listings."""
    id: int
    name: str


class UserListSchema(Schema):
    """User schema for the user directory."""
    id: int
    email: str
    username: str
    first_name: str
    last_name: str
    full_name: str
    initials: str
    is_active: bool
    is_staff: bool
    date_joined: datetime
    avatar: str
    roles: List[UserRoleBadgeSchema] = []


class AssignRoleSchema(Schema):
    """Schema for assigning a role to a user."""
    role_id: int

    @field_validator('role_id')
    @classmethod
    def validate_role_id(cls, v):
        if v <= 0:
            raise ValueError('Invalid role ID')
        return v


class InviteUserSchema(Schema):
    """Schema for inviting a new user."""
    email: str
    role_ids: List[int] = []

    @field_validator('email')
    @classmethod
    def validate_email(cls, v):
        import re
        v = v.strip().lower()
        if not v:
            raise ValueError('Email is required')
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(pattern, v):
            raise ValueError('Please enter a valid email address')
        return v


class InvitationResponseSchema(Schema):
    """Response schema for invitation data."""
    id: int
    email: str
    status: str
    created_at: datetime
    expires_at: datetime
    roles: List[UserRoleBadgeSchema] = []


# ── Stats Schemas ─────────────────────────────────────────────────────

class OverviewStatsSchema(Schema):
    """Dashboard overview statistics."""
    total_users: int
    total_roles: int
    active_roles: int
    pending_invites: int


class ChartDataPointSchema(Schema):
    """Single data point for charts."""
    label: str
    value: int
    color: str = ""


# ── Activity Log Schemas ──────────────────────────────────────────────

class ActivityLogSchema(Schema):
    """Response schema for activity log entries."""
    id: int
    user_email: str
    user_name: str
    action_type: str
    action_display: str
    description: str
    resource_affected: str
    role_affected: str
    ip_address: Optional[str] = None
    created_at: datetime


# ── Generic Schemas ───────────────────────────────────────────────────

class MessageSchema(Schema):
    """Generic message response."""
    message: str


class PaginatedResponseSchema(Schema):
    """Wrapper for paginated responses."""
    count: int
    page: int
    page_size: int
    total_pages: int
    results: list


# ── Article Schemas for Testing ───────────────────────────────────────

class ArticleCreateSchema(Schema):
    """Schema for creating a new article."""
    title: str
    content: str = ""


class ArticleResponseSchema(Schema):
    """Response schema for article data."""
    id: int
    title: str
    content: str
    author_email: str
    created_at: datetime
