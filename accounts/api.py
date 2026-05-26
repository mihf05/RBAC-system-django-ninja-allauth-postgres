"""
Authentication API endpoints.
Handles registration, login, token refresh, logout, and profile retrieval.
"""
from ninja import Router
from ninja.errors import HttpError
from django.contrib.auth import authenticate, get_user_model
from django.db import IntegrityError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError

from .schemas import (
    RegisterSchema,
    LoginSchema,
    TokenRefreshSchema,
    AuthResponseSchema,
    UserResponseSchema,
    TokenResponseSchema,
    MessageSchema,
    ErrorSchema,
)

User = get_user_model()
router = Router()


def get_user_response(user) -> dict:
    """Build user response dict with roles."""
    from rbac.models import UserRoleAssignment
    roles = list(
        UserRoleAssignment.objects.filter(user=user, role__is_active=True)
        .values_list('role__name', flat=True)
    )
    return {
        'id': user.id,
        'email': user.email,
        'username': user.username or '',
        'first_name': user.first_name or '',
        'last_name': user.last_name or '',
        'full_name': user.full_name,
        'initials': user.initials,
        'is_active': user.is_active,
        'is_staff': user.is_staff,
        'date_joined': user.date_joined,
        'avatar': user.avatar or '',
        'roles': roles,
    }


def get_tokens_for_user(user) -> dict:
    """Generate JWT tokens for a user."""
    refresh = RefreshToken.for_user(user)
    return {
        'access': str(refresh.access_token),
        'refresh': str(refresh),
    }


@router.post("/register/", response={201: AuthResponseSchema, 400: ErrorSchema, 422: ErrorSchema})
def register(request, payload: RegisterSchema):
    """Register a new user account with full validation."""
    # Check password confirmation match
    if payload.password != payload.password_confirm:
        raise HttpError(400, "Passwords do not match")

    # Check if email already exists
    if User.objects.filter(email=payload.email).exists():
        raise HttpError(400, "A user with this email already exists")

    # Generate username from email if not provided
    username = payload.username or payload.email.split('@')[0]

    # Ensure username is unique
    base_username = username
    counter = 1
    while User.objects.filter(username=username).exists():
        username = f"{base_username}{counter}"
        counter += 1

    try:
        user = User.objects.create_user(
            email=payload.email,
            password=payload.password,
            username=username,
            first_name=payload.first_name,
            last_name=payload.last_name,
        )
    except IntegrityError:
        raise HttpError(400, "Failed to create user. Please try again.")

    tokens = get_tokens_for_user(user)
    user_data = get_user_response(user)

    # Log activity
    from rbac.models import ActivityLog
    ActivityLog.objects.create(
        user=user,
        action_type='register',
        description=f'New user registered: {user.email}',
        resource_affected='User',
    )

    return 201, {
        'access': tokens['access'],
        'refresh': tokens['refresh'],
        'user': user_data,
    }


@router.post("/login/", response={200: AuthResponseSchema, 400: ErrorSchema, 401: ErrorSchema})
def login(request, payload: LoginSchema):
    """Authenticate user and return JWT tokens."""
    user = authenticate(request, username=payload.email, password=payload.password)

    if user is None:
        raise HttpError(401, "Invalid email or password")

    if not user.is_active:
        raise HttpError(401, "This account has been deactivated")

    tokens = get_tokens_for_user(user)
    user_data = get_user_response(user)

    # Log activity
    from rbac.models import ActivityLog
    ActivityLog.objects.create(
        user=user,
        action_type='login',
        description=f'User logged in: {user.email}',
        resource_affected='Auth',
        ip_address=request.META.get('REMOTE_ADDR'),
    )

    return 200, {
        'access': tokens['access'],
        'refresh': tokens['refresh'],
        'user': user_data,
    }


@router.post("/token/refresh/", response={200: TokenResponseSchema, 401: ErrorSchema})
def refresh_token(request, payload: TokenRefreshSchema):
    """Refresh an access token using a valid refresh token."""
    try:
        old_refresh = RefreshToken(payload.refresh)
        # Blacklist the old token
        old_refresh.blacklist()
        # Create new tokens for the user
        user = User.objects.get(id=old_refresh['user_id'])
        tokens = get_tokens_for_user(user)
        return 200, tokens
    except TokenError:
        raise HttpError(401, "Invalid or expired refresh token")
    except User.DoesNotExist:
        raise HttpError(401, "User not found")


@router.post("/logout/", response={200: MessageSchema, 401: ErrorSchema})
def logout(request, payload: TokenRefreshSchema):
    """Logout user by blacklisting their refresh token."""
    try:
        token = RefreshToken(payload.refresh)
        token.blacklist()

        return 200, {"message": "Successfully logged out"}
    except TokenError:
        raise HttpError(401, "Invalid token")


@router.get("/me/", response={200: UserResponseSchema, 401: ErrorSchema})
def get_current_user(request):
    """Get the currently authenticated user's profile."""
    from rbac.permissions import get_user_from_token

    user = get_user_from_token(request)
    if not user:
        raise HttpError(401, "Authentication required")

    return 200, get_user_response(user)
