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


def sync_code_resources():
    """
    Automatically synchronize features/resources defined in Python code with the database.
    Inspects all registered Ninja API routers and path operations dynamically,
    determining CRUD capabilities on-the-fly and mapping them to roles automatically.
    """
    from rbac.models import Resource, Role, Permission
    from rbac_project.api import api

    # Human-readable names and descriptions for core routers
    prefix_map = {
        '/roles/': ('Roles', 'Role definition and permission matrix management'),
        '/resources/': ('Features & APIs', 'Configure dynamic features and test RBAC permissions'),
        '/users/': ('Users', 'User management, role assignment, and invitations'),
        '/activity/': ('Activity Log', 'System-wide activity log viewer'),
    }

    detected_resources = []

    # 1. Always include Dashboard as a core static page resource
    detected_resources.append({
        'name': 'Dashboard',
        'description': 'System overview analytics dashboard access',
        'has_read': True, 'has_write': False, 'has_update': False, 'has_delete': False
    })

    # 2. Dynamically scan all routers added to the NinjaAPI instance
    for prefix, router in api._routers:
        # Ignore empty prefixes, auth router, statistics, or testing routes
        if not prefix or prefix in ['/auth/', '/stats/', '/test/']:
            continue

        if prefix in prefix_map:
            name, desc = prefix_map[prefix]
        else:
            # Auto-format prefix to human readable name, e.g., '/user-profiles/' -> 'User Profiles'
            name = prefix.strip('/').replace('-', ' ').replace('_', ' ').title()
            desc = f"Auto-detected system endpoint at {prefix}"

        # Analyze HTTP methods across all operations to extract precise CRUD support
        has_read = False
        has_write = False
        has_update = False
        has_delete = False

        for path, path_op in router.path_operations.items():
            for op in path_op.operations:
                for method in op.methods:
                    m = method.upper()
                    if m == 'GET':
                        has_read = True
                    elif m == 'POST':
                        has_write = True
                    elif m in ['PUT', 'PATCH']:
                        has_update = True
                    elif m == 'DELETE':
                        has_delete = True

        detected_resources.append({
            'name': name,
            'description': desc,
            'has_read': has_read or True,
            'has_write': has_write,
            'has_update': has_update,
            'has_delete': has_delete,
        })

    # 3. Synchronize detected resources and capabilities with database
    all_roles = list(Role.objects.all())
    for r_data in detected_resources:
        resource, created = Resource.objects.get_or_create(
            name=r_data['name'],
            defaults={
                'description': r_data['description'],
                'has_read': r_data['has_read'],
                'has_write': r_data['has_write'],
                'has_update': r_data['has_update'],
                'has_delete': r_data['has_delete'],
            }
        )
        if not created:
            # Auto-sync capabilities if endpoints added/removed operations in code
            resource.has_read = r_data['has_read']
            resource.has_write = r_data['has_write']
            resource.has_update = r_data['has_update']
            resource.has_delete = r_data['has_delete']
            resource.save()

        # 4. Map default permissions for all roles
        for role in all_roles:
            if role.name == 'Admin':
                Permission.objects.get_or_create(
                    role=role,
                    resource=resource,
                    defaults={
                        'can_read': r_data['has_read'],
                        'can_write': r_data['has_write'],
                        'can_update': r_data['has_update'],
                        'can_delete': r_data['has_delete'],
                    }
                )
            elif role.name == 'Contributor' and r_data['name'] == 'Dashboard':
                Permission.objects.get_or_create(
                    role=role,
                    resource=resource,
                    defaults={
                        'can_read': True,
                        'can_write': False,
                        'can_update': False,
                        'can_delete': False,
                    }
                )
            else:
                Permission.objects.get_or_create(
                    role=role,
                    resource=resource,
                    defaults={
                        'can_read': False,
                        'can_write': False,
                        'can_update': False,
                        'can_delete': False,
                    }
                )
