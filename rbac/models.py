"""
Core RBAC models: Role, Resource, Permission, UserRoleAssignment, Invitation, ActivityLog.
"""
import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta


class Role(models.Model):
    """Represents a role in the RBAC system (e.g., Admin, Editor, Viewer)."""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, default='')
    is_active = models.BooleanField(default=True)
    is_system = models.BooleanField(
        default=False,
        help_text='System roles cannot be deleted'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_roles',
    )

    class Meta:
        ordering = ['name']
        verbose_name = 'Role'
        verbose_name_plural = 'Roles'

    def __str__(self):
        return self.name

    @property
    def user_count(self):
        return self.assignments.filter(user__is_active=True).count()


class Resource(models.Model):
    """Represents a protected resource in the system (e.g., Articles, Reports)."""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, default='')
    is_active = models.BooleanField(default=True)
    
    # Operation capabilities dynamically defined per resource
    has_read = models.BooleanField(default=True)
    has_write = models.BooleanField(default=True)
    has_update = models.BooleanField(default=True)
    has_delete = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Resource'
        verbose_name_plural = 'Resources'

    def __str__(self):
        return self.name


class Permission(models.Model):
    """
    Permission matrix entry: maps a Role to a Resource with granular access rights.
    Each entry specifies Read, Write, Update, Delete permissions.
    """
    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name='permissions',
    )
    resource = models.ForeignKey(
        Resource,
        on_delete=models.CASCADE,
        related_name='permissions',
    )
    can_read = models.BooleanField(default=False)
    can_write = models.BooleanField(default=False)
    can_update = models.BooleanField(default=False)
    can_delete = models.BooleanField(default=False)

    class Meta:
        unique_together = ('role', 'resource')
        ordering = ['role__name', 'resource__name']
        verbose_name = 'Permission'
        verbose_name_plural = 'Permissions'

    def __str__(self):
        perms = []
        if self.can_read:
            perms.append('R')
        if self.can_write:
            perms.append('W')
        if self.can_update:
            perms.append('U')
        if self.can_delete:
            perms.append('D')
        return f"{self.role.name} -> {self.resource.name}: {'|'.join(perms) or 'None'}"


class UserRoleAssignment(models.Model):
    """Assigns a role to a user. A user can have multiple roles."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='role_assignments',
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name='assignments',
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='role_assignments_made',
    )

    class Meta:
        unique_together = ('user', 'role')
        ordering = ['-assigned_at']
        verbose_name = 'User Role Assignment'
        verbose_name_plural = 'User Role Assignments'

    def __str__(self):
        return f"{self.user.email} -> {self.role.name}"


class Invitation(models.Model):
    """Tracks user invitations with role pre-assignment."""

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        ACCEPTED = 'accepted', 'Accepted'
        EXPIRED = 'expired', 'Expired'

    email = models.EmailField()
    roles = models.ManyToManyField(Role, blank=True, related_name='invitations')
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='invitations_sent',
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Invitation'
        verbose_name_plural = 'Invitations'

    def __str__(self):
        return f"Invitation: {self.email} ({self.status})"

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(days=7)
        super().save(*args, **kwargs)

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at


class ActivityLog(models.Model):
    """Audit log for tracking admin actions in the RBAC system."""

    class ActionType(models.TextChoices):
        CREATE_ROLE = 'create_role', 'Create Role'
        EDIT_ROLE = 'edit_role', 'Edit Role'
        DELETE_ROLE = 'delete_role', 'Delete Role'
        ASSIGN_USER = 'assign_user', 'Assign User to Role'
        REVOKE_ROLE = 'revoke_role', 'Revoke Role from User'
        INVITE_USER = 'invite_user', 'Invite User'
        EDIT_PERMISSION = 'edit_permission', 'Edit Permission'
        DEACTIVATE_USER = 'deactivate_user', 'Deactivate User'
        ACTIVATE_USER = 'activate_user', 'Activate User'
        CREATE_RESOURCE = 'create_resource', 'Create Resource'
        EDIT_RESOURCE = 'edit_resource', 'Edit Resource'
        DELETE_RESOURCE = 'delete_resource', 'Delete Resource'
        LOGIN = 'login', 'User Login'
        LOGOUT = 'logout', 'User Logout'
        REGISTER = 'register', 'User Registration'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='activity_logs',
    )
    action_type = models.CharField(max_length=30, choices=ActionType.choices)
    description = models.TextField()
    resource_affected = models.CharField(max_length=200, blank=True, default='')
    role_affected = models.CharField(max_length=200, blank=True, default='')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Activity Log'
        verbose_name_plural = 'Activity Logs'

    def __str__(self):
        return f"[{self.created_at}] {self.user}: {self.action_type}"



