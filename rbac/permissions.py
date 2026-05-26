"""
Permission utilities for JWT token extraction and admin checks.
"""
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import TokenError

User = get_user_model()


def get_user_from_token(request):
    """
    Extract and validate the user from the Authorization header JWT token.
    Returns the User object or None if invalid/missing.
    """
    auth_header = request.META.get('HTTP_AUTHORIZATION', '')
    if not auth_header.startswith('Bearer '):
        return None

    token_str = auth_header[7:]  # Remove 'Bearer ' prefix

    try:
        token = AccessToken(token_str)
        user_id = token.get('user_id')
        if user_id is None:
            return None
        user = User.objects.get(id=user_id, is_active=True)
        return user
    except (TokenError, User.DoesNotExist):
        return None


def require_auth(request):
    """
    Get authenticated user or raise 401.
    Use in API endpoints: user = require_auth(request)
    """
    from ninja.errors import HttpError
    user = get_user_from_token(request)
    if not user:
        raise HttpError(401, "Authentication required. Please provide a valid access token.")
    return user


def require_admin(request):
    """
    Get authenticated admin user or raise 403.
    An admin is a user with is_staff=True OR has the 'Admin' role assigned.
    """
    from ninja.errors import HttpError
    from rbac.models import UserRoleAssignment

    user = require_auth(request)

    # Staff/superuser always has admin access
    if user.is_staff or user.is_superuser:
        return user

    # Check if user has Admin role
    has_admin_role = UserRoleAssignment.objects.filter(
        user=user,
        role__name='Admin',
        role__is_active=True,
    ).exists()

    if not has_admin_role:
        raise HttpError(403, "Admin access required")

    return user


def check_permission(user, resource_name: str, action: str) -> bool:
    """
    Check if a user has a specific permission on a resource.
    action should be one of: 'read', 'write', 'update', 'delete'
    """
    from rbac.models import Permission, UserRoleAssignment

    # Superusers have all permissions
    if user.is_superuser:
        return True

    # Get all active roles for the user
    role_ids = UserRoleAssignment.objects.filter(
        user=user,
        role__is_active=True,
    ).values_list('role_id', flat=True)

    if not role_ids:
        return False

    # Check permissions across all assigned roles
    action_field = f'can_{action}'
    return Permission.objects.filter(
        role_id__in=role_ids,
        resource__name=resource_name,
        resource__is_active=True,
        **{action_field: True},
    ).exists()


def require_permission(request, resource_name: str, action: str):
    """
    Ensure the authenticated user has a specific permission on a resource.
    Raises 403 if they do not have access.
    """
    from ninja.errors import HttpError
    user = require_auth(request)
    if not check_permission(user, resource_name, action):
        raise HttpError(403, f"You do not have permission to {action} '{resource_name}'")
    return user
