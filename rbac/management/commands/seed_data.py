"""
Management command to seed initial clean data for the RBAC system.
Creates default Admin and Contributor roles, plus admin and contributor user accounts.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from rbac.models import Role, UserRoleAssignment, ActivityLog

User = get_user_model()


class Command(BaseCommand):
    help = 'Seed the database with clean Admin and Contributor initial data'

    def handle(self, *args, **options):
        self.stdout.write('[*] Seeding clean RBAC database...\n')

        # ── Create Users ───────────────────────────────────────
        admin_user, admin_created = User.objects.get_or_create(
            email='admin@example.com',
            defaults={
                'username': 'admin',
                'first_name': 'System',
                'last_name': 'Admin',
                'is_staff': True,
                'is_superuser': True,
                'is_active': True,
            }
        )
        if admin_created:
            admin_user.set_password('admin123')
            admin_user.save()
            self.stdout.write(self.style.SUCCESS('  [+] Created admin user (admin@example.com / admin123)'))
        else:
            self.stdout.write('  -> Admin user already exists')

        contributor_user, contributor_created = User.objects.get_or_create(
            email='contributor@example.com',
            defaults={
                'username': 'contributor',
                'first_name': 'Jane',
                'last_name': 'Contributor',
                'is_active': True,
            }
        )
        if contributor_created:
            contributor_user.set_password('password123')
            contributor_user.save()
            self.stdout.write(self.style.SUCCESS('  [+] Created contributor user (contributor@example.com / password123)'))
        else:
            self.stdout.write('  -> Contributor user already exists')

        # ── Create Roles ───────────────────────────────────────
        admin_role, admin_role_created = Role.objects.get_or_create(
            name='Admin',
            defaults={
                'description': 'Full system administrator with unrestricted access',
                'is_system': True,
                'created_by': admin_user,
            }
        )
        if admin_role_created:
            self.stdout.write(self.style.SUCCESS('  [+] Created role: Admin'))

        contributor_role, contributor_role_created = Role.objects.get_or_create(
            name='Contributor',
            defaults={
                'description': 'Can create features and perform operations but restricted by assignment',
                'is_system': False,
                'created_by': admin_user,
            }
        )
        if contributor_role_created:
            self.stdout.write(self.style.SUCCESS('  [+] Created role: Contributor'))

        # ── Assign Roles to Users ─────────────────────────────
        _, assigned_admin = UserRoleAssignment.objects.get_or_create(
            user=admin_user,
            role=admin_role,
            defaults={'assigned_by': admin_user}
        )
        if assigned_admin:
            self.stdout.write(self.style.SUCCESS('  [+] Assigned Admin role to admin@example.com'))

        _, assigned_contrib = UserRoleAssignment.objects.get_or_create(
            user=contributor_user,
            role=contributor_role,
            defaults={'assigned_by': admin_user}
        )
        if assigned_contrib:
            self.stdout.write(self.style.SUCCESS('  [+] Assigned Contributor role to contributor@example.com'))

        # ── Create seed activity log ──────────────────────────
        ActivityLog.objects.create(
            user=admin_user,
            action_type='create_role',
            description='Clean system initialized: Admin and Contributor roles established.',
            role_affected='Admin, Contributor',
        )

        self.stdout.write(self.style.SUCCESS('\n[OK] Database seeded successfully!'))
        self.stdout.write('\nLogin credentials:')
        self.stdout.write('   Admin:       admin@example.com / admin123')
        self.stdout.write('   Contributor: contributor@example.com / password123\n')
