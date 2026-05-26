from django.contrib import admin
from .models import Role, Resource, Permission, UserRoleAssignment, Invitation, ActivityLog


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active', 'is_system', 'user_count', 'created_at')
    list_filter = ('is_active', 'is_system')
    search_fields = ('name', 'description')


@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name',)


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ('role', 'resource', 'can_read', 'can_write', 'can_update', 'can_delete')
    list_filter = ('role', 'resource', 'can_read', 'can_write', 'can_update', 'can_delete')


@admin.register(UserRoleAssignment)
class UserRoleAssignmentAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'assigned_at', 'assigned_by')
    list_filter = ('role',)
    search_fields = ('user__email', 'role__name')


@admin.register(Invitation)
class InvitationAdmin(admin.ModelAdmin):
    list_display = ('email', 'status', 'created_at', 'expires_at')
    list_filter = ('status',)
    search_fields = ('email',)


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'action_type', 'description', 'created_at')
    list_filter = ('action_type',)
    search_fields = ('description', 'user__email')
    readonly_fields = ('user', 'action_type', 'description', 'resource_affected', 'role_affected', 'ip_address', 'created_at')
