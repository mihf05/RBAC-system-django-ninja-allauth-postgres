"""
RBAC API endpoints for managing roles, resources, users, stats, and activity logs.
All endpoints require admin authentication.
"""
import math
from ninja import Router, Query
from ninja.errors import HttpError
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.db.models import Q, Count
from django.utils import timezone
from datetime import timedelta

from .models import Role, Resource, Permission, UserRoleAssignment, Invitation, ActivityLog
from .permissions import require_admin, require_auth
from .schemas import (
    RoleCreateSchema, RoleUpdateSchema, RoleResponseSchema, RoleListSchema,
    SetPermissionsSchema, PermissionResponseSchema,
    ResourceCreateSchema, ResourceUpdateSchema, ResourceResponseSchema,
    UserListSchema, UserRoleBadgeSchema, AssignRoleSchema,
    InviteUserSchema, InvitationResponseSchema,
    OverviewStatsSchema, ChartDataPointSchema,
    ActivityLogSchema, MessageSchema,
)

User = get_user_model()

# ══════════════════════════════════════════════════════════════════════
# ROLES API
# ══════════════════════════════════════════════════════════════════════
roles_router = Router()


def _build_role_response(role):
    """Build a full role response with permissions."""
    permissions = []
    for perm in role.permissions.select_related('resource').all():
        permissions.append({
            'id': perm.id,
            'resource_id': perm.resource_id,
            'resource_name': perm.resource.name,
            'can_read': perm.can_read,
            'can_write': perm.can_write,
            'can_update': perm.can_update,
            'can_delete': perm.can_delete,
            # Pass capability flags to frontend
            'has_read': perm.resource.has_read,
            'has_write': perm.resource.has_write,
            'has_update': perm.resource.has_update,
            'has_delete': perm.resource.has_delete,
        })
    return {
        'id': role.id,
        'name': role.name,
        'description': role.description,
        'is_active': role.is_active,
        'is_system': role.is_system,
        'user_count': role.user_count,
        'created_at': role.created_at,
        'updated_at': role.updated_at,
        'permissions': permissions,
    }


@roles_router.get("/", response=list[RoleListSchema])
def list_roles(request, search: str = "", active_only: bool = False):
    """List all roles with optional search and filtering."""
    require_admin(request)

    qs = Role.objects.all()
    if search:
        qs = qs.filter(Q(name__icontains=search) | Q(description__icontains=search))
    if active_only:
        qs = qs.filter(is_active=True)

    results = []
    for role in qs:
        results.append({
            'id': role.id,
            'name': role.name,
            'description': role.description,
            'is_active': role.is_active,
            'is_system': role.is_system,
            'user_count': role.user_count,
            'created_at': role.created_at,
        })
    return results


@roles_router.post("/", response={201: RoleResponseSchema, 400: MessageSchema})
def create_role(request, payload: RoleCreateSchema):
    """Create a new role."""
    admin_user = require_admin(request)

    if Role.objects.filter(name__iexact=payload.name.strip()).exists():
        raise HttpError(400, f"A role named '{payload.name}' already exists")

    role = Role.objects.create(
        name=payload.name.strip(),
        description=payload.description,
        is_active=payload.is_active,
        created_by=admin_user,
    )

    # Create default permission entries for all active resources
    resources = Resource.objects.filter(is_active=True)
    for resource in resources:
        Permission.objects.create(role=role, resource=resource)

    ActivityLog.objects.create(
        user=admin_user,
        action_type='create_role',
        description=f'Created role: {role.name}',
        role_affected=role.name,
        ip_address=request.META.get('REMOTE_ADDR'),
    )

    return 201, _build_role_response(role)


@roles_router.get("/{role_id}/", response={200: RoleResponseSchema, 404: MessageSchema})
def get_role(request, role_id: int):
    """Get a role's details including its full permission matrix."""
    require_admin(request)

    try:
        role = Role.objects.get(id=role_id)
    except Role.DoesNotExist:
        raise HttpError(404, "Role not found")

    return 200, _build_role_response(role)


@roles_router.put("/{role_id}/", response={200: RoleResponseSchema, 400: MessageSchema, 404: MessageSchema})
def update_role(request, role_id: int, payload: RoleUpdateSchema):
    """Update a role's name, description, or status."""
    admin_user = require_admin(request)

    try:
        role = Role.objects.get(id=role_id)
    except Role.DoesNotExist:
        raise HttpError(404, "Role not found")

    if payload.name is not None:
        # Check uniqueness excluding current role
        if Role.objects.filter(name__iexact=payload.name.strip()).exclude(id=role_id).exists():
            raise HttpError(400, f"A role named '{payload.name}' already exists")
        role.name = payload.name.strip()

    if payload.description is not None:
        role.description = payload.description
    if payload.is_active is not None:
        role.is_active = payload.is_active

    role.save()

    ActivityLog.objects.create(
        user=admin_user,
        action_type='edit_role',
        description=f'Updated role: {role.name}',
        role_affected=role.name,
        ip_address=request.META.get('REMOTE_ADDR'),
    )

    return 200, _build_role_response(role)


@roles_router.delete("/{role_id}/", response={200: MessageSchema, 400: MessageSchema, 404: MessageSchema})
def delete_role(request, role_id: int):
    """Delete a role (system roles cannot be deleted)."""
    admin_user = require_admin(request)

    try:
        role = Role.objects.get(id=role_id)
    except Role.DoesNotExist:
        raise HttpError(404, "Role not found")

    if role.is_system:
        raise HttpError(400, "System roles cannot be deleted")

    role_name = role.name
    role.delete()

    ActivityLog.objects.create(
        user=admin_user,
        action_type='delete_role',
        description=f'Deleted role: {role_name}',
        role_affected=role_name,
        ip_address=request.META.get('REMOTE_ADDR'),
    )

    return 200, {"message": f"Role '{role_name}' has been deleted"}


@roles_router.post("/{role_id}/permissions/", response={200: RoleResponseSchema, 400: MessageSchema, 404: MessageSchema})
def set_permissions(request, role_id: int, payload: SetPermissionsSchema):
    """Set the full permissions matrix for a role."""
    admin_user = require_admin(request)

    try:
        role = Role.objects.get(id=role_id)
    except Role.DoesNotExist:
        raise HttpError(404, "Role not found")

    # Validate all resource IDs exist
    resource_ids = [p.resource_id for p in payload.permissions]
    existing_ids = set(Resource.objects.filter(id__in=resource_ids).values_list('id', flat=True))
    invalid_ids = set(resource_ids) - existing_ids
    if invalid_ids:
        raise HttpError(400, f"Invalid resource IDs: {list(invalid_ids)}")

    # Update or create permission entries
    for perm_data in payload.permissions:
        Permission.objects.update_or_create(
            role=role,
            resource_id=perm_data.resource_id,
            defaults={
                'can_read': perm_data.can_read,
                'can_write': perm_data.can_write,
                'can_update': perm_data.can_update,
                'can_delete': perm_data.can_delete,
            },
        )

    ActivityLog.objects.create(
        user=admin_user,
        action_type='edit_permission',
        description=f'Updated permissions for role: {role.name}',
        role_affected=role.name,
        ip_address=request.META.get('REMOTE_ADDR'),
    )

    return 200, _build_role_response(role)


# ══════════════════════════════════════════════════════════════════════
# RESOURCES API
# ══════════════════════════════════════════════════════════════════════
resources_router = Router()


@resources_router.get("/", response=list[ResourceResponseSchema])
def list_resources(request, search: str = ""):
    """List all resources."""
    require_admin(request)

    qs = Resource.objects.all()
    if search:
        qs = qs.filter(Q(name__icontains=search) | Q(description__icontains=search))

    return [
        {
            'id': r.id,
            'name': r.name,
            'description': r.description,
            'is_active': r.is_active,
            'has_read': r.has_read,
            'has_write': r.has_write,
            'has_update': r.has_update,
            'has_delete': r.has_delete,
            'created_at': r.created_at,
        }
        for r in qs
    ]


@resources_router.post("/", response={201: ResourceResponseSchema, 400: MessageSchema})
def create_resource(request, payload: ResourceCreateSchema):
    """Create a new resource."""
    admin_user = require_admin(request)

    if Resource.objects.filter(name__iexact=payload.name.strip()).exists():
        raise HttpError(400, f"A resource named '{payload.name}' already exists")

    resource = Resource.objects.create(
        name=payload.name.strip(),
        description=payload.description,
        has_read=payload.has_read,
        has_write=payload.has_write,
        has_update=payload.has_update,
        has_delete=payload.has_delete,
    )

    # Create default permission entries for all existing roles
    roles = Role.objects.all()
    for role in roles:
        Permission.objects.get_or_create(role=role, resource=resource)

    ActivityLog.objects.create(
        user=admin_user,
        action_type='create_resource',
        description=f'Created resource: {resource.name}',
        resource_affected=resource.name,
        ip_address=request.META.get('REMOTE_ADDR'),
    )

    return 201, {
        'id': resource.id,
        'name': resource.name,
        'description': resource.description,
        'is_active': resource.is_active,
        'has_read': resource.has_read,
        'has_write': resource.has_write,
        'has_update': resource.has_update,
        'has_delete': resource.has_delete,
        'created_at': resource.created_at,
    }


@resources_router.put("/{resource_id}/", response={200: ResourceResponseSchema, 400: MessageSchema, 404: MessageSchema})
def update_resource(request, resource_id: int, payload: ResourceUpdateSchema):
    """Update a resource."""
    admin_user = require_admin(request)

    try:
        resource = Resource.objects.get(id=resource_id)
    except Resource.DoesNotExist:
        raise HttpError(404, "Resource not found")

    if payload.name is not None:
        if Resource.objects.filter(name__iexact=payload.name.strip()).exclude(id=resource_id).exists():
            raise HttpError(400, f"A resource named '{payload.name}' already exists")
        resource.name = payload.name.strip()

    if payload.description is not None:
        resource.description = payload.description
    if payload.is_active is not None:
        resource.is_active = payload.is_active
    if payload.has_read is not None:
        resource.has_read = payload.has_read
    if payload.has_write is not None:
        resource.has_write = payload.has_write
    if payload.has_update is not None:
        resource.has_update = payload.has_update
    if payload.has_delete is not None:
        resource.has_delete = payload.has_delete

    resource.save()

    ActivityLog.objects.create(
        user=admin_user,
        action_type='edit_resource',
        description=f'Updated resource: {resource.name}',
        resource_affected=resource.name,
        ip_address=request.META.get('REMOTE_ADDR'),
    )

    return 200, {
        'id': resource.id,
        'name': resource.name,
        'description': resource.description,
        'is_active': resource.is_active,
        'has_read': resource.has_read,
        'has_write': resource.has_write,
        'has_update': resource.has_update,
        'has_delete': resource.has_delete,
        'created_at': resource.created_at,
    }


@resources_router.delete("/{resource_id}/", response={200: MessageSchema, 404: MessageSchema})
def delete_resource(request, resource_id: int):
    """Delete a resource and its associated permissions."""
    admin_user = require_admin(request)

    try:
        resource = Resource.objects.get(id=resource_id)
    except Resource.DoesNotExist:
        raise HttpError(404, "Resource not found")

    resource_name = resource.name
    resource.delete()

    ActivityLog.objects.create(
        user=admin_user,
        action_type='delete_resource',
        description=f'Deleted resource: {resource_name}',
        resource_affected=resource_name,
        ip_address=request.META.get('REMOTE_ADDR'),
    )

    return 200, {"message": f"Resource '{resource_name}' has been deleted"}


# ══════════════════════════════════════════════════════════════════════
# USERS API
# ══════════════════════════════════════════════════════════════════════
users_router = Router()


def _build_user_response(user):
    """Build user response with roles."""
    roles = [
        {'id': a.role.id, 'name': a.role.name}
        for a in user.role_assignments.select_related('role').filter(role__is_active=True)
    ]
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


@users_router.get("/", response=list[UserListSchema])
def list_users(
    request,
    search: str = "",
    role: str = "",
    status: str = "",
    page: int = 1,
    page_size: int = 20,
):
    """List all users with search, filter, and pagination."""
    require_admin(request)

    qs = User.objects.prefetch_related('role_assignments__role').all()

    if search:
        qs = qs.filter(
            Q(email__icontains=search) |
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search) |
            Q(username__icontains=search)
        )

    if status == 'active':
        qs = qs.filter(is_active=True)
    elif status == 'inactive':
        qs = qs.filter(is_active=False)

    if role:
        qs = qs.filter(role_assignments__role__name__iexact=role)

    qs = qs.distinct()

    # Pagination
    start = (page - 1) * page_size
    end = start + page_size
    users = qs[start:end]

    return [_build_user_response(u) for u in users]


@users_router.get("/{user_id}/", response={200: UserListSchema, 404: MessageSchema})
def get_user(request, user_id: int):
    """Get detailed user info."""
    require_admin(request)

    try:
        user = User.objects.prefetch_related('role_assignments__role').get(id=user_id)
    except User.DoesNotExist:
        raise HttpError(404, "User not found")

    return 200, _build_user_response(user)


@users_router.post("/{user_id}/assign-role/", response={200: UserListSchema, 400: MessageSchema, 404: MessageSchema})
def assign_role(request, user_id: int, payload: AssignRoleSchema):
    """Assign a role to a user."""
    admin_user = require_admin(request)

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        raise HttpError(404, "User not found")

    try:
        role = Role.objects.get(id=payload.role_id, is_active=True)
    except Role.DoesNotExist:
        raise HttpError(404, "Role not found or inactive")

    if UserRoleAssignment.objects.filter(user=user, role=role).exists():
        raise HttpError(400, f"User already has the '{role.name}' role")

    UserRoleAssignment.objects.create(
        user=user,
        role=role,
        assigned_by=admin_user,
    )

    ActivityLog.objects.create(
        user=admin_user,
        action_type='assign_user',
        description=f'Assigned role "{role.name}" to {user.email}',
        resource_affected=user.email,
        role_affected=role.name,
        ip_address=request.META.get('REMOTE_ADDR'),
    )

    return 200, _build_user_response(user)


@users_router.post("/{user_id}/revoke-role/", response={200: UserListSchema, 400: MessageSchema, 404: MessageSchema})
def revoke_role(request, user_id: int, payload: AssignRoleSchema):
    """Revoke a role from a user."""
    admin_user = require_admin(request)

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        raise HttpError(404, "User not found")

    try:
        role = Role.objects.get(id=payload.role_id)
    except Role.DoesNotExist:
        raise HttpError(404, "Role not found")

    assignment = UserRoleAssignment.objects.filter(user=user, role=role).first()
    if not assignment:
        raise HttpError(400, f"User does not have the '{role.name}' role")

    assignment.delete()

    ActivityLog.objects.create(
        user=admin_user,
        action_type='revoke_role',
        description=f'Revoked role "{role.name}" from {user.email}',
        resource_affected=user.email,
        role_affected=role.name,
        ip_address=request.META.get('REMOTE_ADDR'),
    )

    return 200, _build_user_response(user)


@users_router.post("/{user_id}/deactivate/", response={200: UserListSchema, 400: MessageSchema, 404: MessageSchema})
def deactivate_user(request, user_id: int):
    """Deactivate a user account."""
    admin_user = require_admin(request)

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        raise HttpError(404, "User not found")

    if user.id == admin_user.id:
        raise HttpError(400, "You cannot deactivate your own account")

    if not user.is_active:
        raise HttpError(400, "User is already deactivated")

    user.is_active = False
    user.save()

    ActivityLog.objects.create(
        user=admin_user,
        action_type='deactivate_user',
        description=f'Deactivated user: {user.email}',
        resource_affected=user.email,
        ip_address=request.META.get('REMOTE_ADDR'),
    )

    return 200, _build_user_response(user)


@users_router.post("/{user_id}/activate/", response={200: UserListSchema, 400: MessageSchema, 404: MessageSchema})
def activate_user(request, user_id: int):
    """Activate a user account."""
    admin_user = require_admin(request)

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        raise HttpError(404, "User not found")

    if user.is_active:
        raise HttpError(400, "User is already active")

    user.is_active = True
    user.save()

    ActivityLog.objects.create(
        user=admin_user,
        action_type='activate_user',
        description=f'Activated user: {user.email}',
        resource_affected=user.email,
        ip_address=request.META.get('REMOTE_ADDR'),
    )

    return 200, _build_user_response(user)


@users_router.post("/invite/", response={201: InvitationResponseSchema, 400: MessageSchema})
def invite_user(request, payload: InviteUserSchema):
    """Invite a new user with pre-assigned roles."""
    admin_user = require_admin(request)

    # Check if user already exists
    if User.objects.filter(email=payload.email).exists():
        raise HttpError(400, "A user with this email already exists")

    # Check for existing pending invitation
    existing = Invitation.objects.filter(
        email=payload.email,
        status='pending',
        expires_at__gt=timezone.now(),
    ).first()
    if existing:
        raise HttpError(400, "An active invitation already exists for this email")

    # Validate role IDs
    roles = []
    if payload.role_ids:
        roles = list(Role.objects.filter(id__in=payload.role_ids, is_active=True))
        if len(roles) != len(payload.role_ids):
            raise HttpError(400, "One or more role IDs are invalid or inactive")

    invitation = Invitation.objects.create(
        email=payload.email,
        invited_by=admin_user,
        expires_at=timezone.now() + timedelta(days=7),
    )
    if roles:
        invitation.roles.set(roles)

    ActivityLog.objects.create(
        user=admin_user,
        action_type='invite_user',
        description=f'Invited {payload.email} with roles: {", ".join(r.name for r in roles) or "None"}',
        resource_affected=payload.email,
        ip_address=request.META.get('REMOTE_ADDR'),
    )

    return 201, {
        'id': invitation.id,
        'email': invitation.email,
        'status': invitation.status,
        'created_at': invitation.created_at,
        'expires_at': invitation.expires_at,
        'roles': [{'id': r.id, 'name': r.name} for r in roles],
    }


@users_router.get("/invitations/list/", response=list[InvitationResponseSchema])
def list_invitations(request):
    """List all invitations."""
    require_admin(request)

    invitations = Invitation.objects.prefetch_related('roles').all()[:50]
    results = []
    for inv in invitations:
        results.append({
            'id': inv.id,
            'email': inv.email,
            'status': inv.status,
            'created_at': inv.created_at,
            'expires_at': inv.expires_at,
            'roles': [{'id': r.id, 'name': r.name} for r in inv.roles.all()],
        })
    return results


# ══════════════════════════════════════════════════════════════════════
# STATS API
# ══════════════════════════════════════════════════════════════════════
stats_router = Router()


@stats_router.get("/overview/", response=OverviewStatsSchema)
def get_overview_stats(request):
    """Get dashboard overview statistics."""
    require_admin(request)

    return {
        'total_users': User.objects.count(),
        'total_roles': Role.objects.count(),
        'active_roles': Role.objects.filter(is_active=True).count(),
        'pending_invites': Invitation.objects.filter(
            status='pending',
            expires_at__gt=timezone.now(),
        ).count(),
    }


@stats_router.get("/users-per-role/", response=list[ChartDataPointSchema])
def get_users_per_role(request):
    """Get user count per role for bar chart."""
    require_admin(request)

    colors = ['#2563eb', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4', '#ec4899', '#14b8a6']
    roles = Role.objects.filter(is_active=True).annotate(
        num_users=Count('assignments', filter=Q(assignments__user__is_active=True))
    )

    results = []
    for i, role in enumerate(roles):
        results.append({
            'label': role.name,
            'value': role.num_users,
            'color': colors[i % len(colors)],
        })
    return results


@stats_router.get("/roles-by-status/", response=list[ChartDataPointSchema])
def get_roles_by_status(request):
    """Get roles grouped by active/inactive status for pie chart."""
    require_admin(request)

    active = Role.objects.filter(is_active=True).count()
    inactive = Role.objects.filter(is_active=False).count()

    return [
        {'label': 'Active', 'value': active, 'color': '#10b981'},
        {'label': 'Inactive', 'value': inactive, 'color': '#ef4444'},
    ]


# ══════════════════════════════════════════════════════════════════════
# ACTIVITY LOG API
# ══════════════════════════════════════════════════════════════════════
activity_router = Router()


@activity_router.get("/", response=list[ActivityLogSchema])
def list_activity(
    request,
    search: str = "",
    action_type: str = "",
    page: int = 1,
    page_size: int = 25,
):
    """Get paginated activity log with search and filter."""
    user = require_auth(request)

    # Allow if the user is an Admin, OR has explicit read permission on "Audit Logs"
    is_admin = False
    if user.is_staff or user.is_superuser:
        is_admin = True
    else:
        from rbac.models import UserRoleAssignment
        is_admin = UserRoleAssignment.objects.filter(
            user=user,
            role__name='Admin',
            role__is_active=True,
        ).exists()

    if not is_admin:
        from .permissions import check_permission
        if not check_permission(user, "Audit Logs", "read"):
            raise HttpError(403, "You do not have permission to read 'Audit Logs'")

    qs = ActivityLog.objects.select_related('user').all()

    if search:
        qs = qs.filter(
            Q(description__icontains=search) |
            Q(user__email__icontains=search) |
            Q(resource_affected__icontains=search) |
            Q(role_affected__icontains=search)
        )

    if action_type:
        qs = qs.filter(action_type=action_type)

    start = (page - 1) * page_size
    end = start + page_size
    logs = qs[start:end]

    results = []
    for log in logs:
        results.append({
            'id': log.id,
            'user_email': log.user.email if log.user else 'System',
            'user_name': log.user.full_name if log.user else 'System',
            'action_type': log.action_type,
            'action_display': log.get_action_type_display(),
            'description': log.description,
            'resource_affected': log.resource_affected,
            'role_affected': log.role_affected,
            'ip_address': log.ip_address,
            'created_at': log.created_at,
        })
    return results
