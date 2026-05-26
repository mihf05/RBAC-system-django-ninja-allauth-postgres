"""
Pydantic schemas for authentication API.
All validation happens here on the backend.
"""
import re
from ninja import Schema
from pydantic import field_validator, EmailStr
from typing import Optional, List
from datetime import datetime


class RegisterSchema(Schema):
    """Schema for user registration with full backend validation."""
    email: str
    password: str
    password_confirm: str
    first_name: str = ""
    last_name: str = ""
    username: str = ""

    @field_validator('email')
    @classmethod
    def validate_email(cls, v):
        v = v.strip().lower()
        if not v:
            raise ValueError('Email is required')
        # Basic email pattern validation
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(pattern, v):
            raise ValueError('Please enter a valid email address')
        return v

    @field_validator('password')
    @classmethod
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not re.search(r'[0-9]', v):
            raise ValueError('Password must contain at least one digit')
        return v

    @field_validator('first_name', 'last_name')
    @classmethod
    def validate_names(cls, v):
        if v and len(v) > 150:
            raise ValueError('Name must be 150 characters or fewer')
        return v.strip()


class LoginSchema(Schema):
    """Schema for user login."""
    email: str
    password: str

    @field_validator('email')
    @classmethod
    def validate_email(cls, v):
        v = v.strip().lower()
        if not v:
            raise ValueError('Email is required')
        return v

    @field_validator('password')
    @classmethod
    def validate_password(cls, v):
        if not v:
            raise ValueError('Password is required')
        return v


class TokenRefreshSchema(Schema):
    """Schema for token refresh."""
    refresh: str

    @field_validator('refresh')
    @classmethod
    def validate_refresh(cls, v):
        if not v or not v.strip():
            raise ValueError('Refresh token is required')
        return v.strip()


class TokenResponseSchema(Schema):
    """Response schema for JWT tokens."""
    access: str
    refresh: str


class UserResponseSchema(Schema):
    """Response schema for user data."""
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
    roles: List[str] = []


class AuthResponseSchema(Schema):
    """Combined auth response with tokens and user data."""
    access: str
    refresh: str
    user: UserResponseSchema


class MessageSchema(Schema):
    """Generic message response."""
    message: str


class ErrorSchema(Schema):
    """Error response schema."""
    detail: str
    errors: Optional[dict] = None
