"""
Management command to seed initial data for the RBAC system.
Creates default roles, resources, permissions, and a superuser.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from rbac.models import Role, Resource, Permission, UserRoleAssignment, ActivityLog

User = get_user_model()


class Command(BaseCommand):
    help = 'Seed the database with initial RBAC data'

    def handle(self, *args, **options):
        self.stdout.write('[*] Seeding RBAC database...\n')

        # ── Create Superuser ───────────────────────────────────
        admin_user, created = User.objects.get_or_create(
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
        if created:
            admin_user.set_password('admin123')
            admin_user.save()
            self.stdout.write(self.style.SUCCESS('  [+] Created admin user (admin@example.com / admin123)'))
        else:
            self.stdout.write('  -> Admin user already exists')

        # ── Create Resources ──────────────────────────────────
        resource_data = [
            ('Articles', 'Blog posts and content articles', True, True, True, True),
            ('User Profiles', 'User account and profile data', True, True, True, True),
            ('Settings', 'System configuration settings', True, False, True, False),
            ('Reports', 'Analytics and data reports', True, False, False, False),
            ('API Endpoints', 'REST API access control', True, True, True, True),
            ('Audit Logs', 'System audit and activity logs', True, False, False, False),
            ('Media Files', 'Uploaded images and documents', True, True, True, True),
        ]

        resources = {}
        for name, desc, r, w, u, d in resource_data:
            resource, created = Resource.objects.get_or_create(
                name=name,
                defaults={
                    'description': desc,
                    'has_read': r,
                    'has_write': w,
                    'has_update': u,
                    'has_delete': d,
                }
            )
            # If already exists, update capabilities just in case
            if not created:
                resource.has_read = r
                resource.has_write = w
                resource.has_update = u
                resource.has_delete = d
                resource.save()
            resources[name] = resource
            if created:
                self.stdout.write(self.style.SUCCESS(f'  [+] Created resource: {name}'))

        # ── Create Roles ──────────────────────────────────────
        roles_data = [
            {
                'name': 'Admin',
                'description': 'Full system administrator with unrestricted access',
                'is_system': True,
                'permissions': {r: {'read': True, 'write': True, 'update': True, 'delete': True} for r in resources},
            },
            {
                'name': 'Editor',
                'description': 'Can read and write content, update user profiles',
                'is_system': False,
                'permissions': {
                    'Articles': {'read': True, 'write': True, 'update': True, 'delete': False},
                    'User Profiles': {'read': True, 'write': False, 'update': True, 'delete': False},
                    'Settings': {'read': True, 'write': False, 'update': False, 'delete': False},
                    'Reports': {'read': True, 'write': False, 'update': False, 'delete': False},
                    'API Endpoints': {'read': True, 'write': False, 'update': False, 'delete': False},
                    'Audit Logs': {'read': True, 'write': False, 'update': False, 'delete': False},
                    'Media Files': {'read': True, 'write': True, 'update': True, 'delete': False},
                },
            },
            {
                'name': 'Viewer',
                'description': 'Read-only access to published content and reports',
                'is_system': False,
                'permissions': {
                    'Articles': {'read': True, 'write': False, 'update': False, 'delete': False},
                    'User Profiles': {'read': True, 'write': False, 'update': False, 'delete': False},
                    'Reports': {'read': True, 'write': False, 'update': False, 'delete': False},
                    'Media Files': {'read': True, 'write': False, 'update': False, 'delete': False},
                },
            },
            {
                'name': 'Contributor',
                'description': 'Can create content but cannot publish or delete',
                'is_system': False,
                'permissions': {
                    'Articles': {'read': True, 'write': True, 'update': False, 'delete': False},
                    'User Profiles': {'read': True, 'write': False, 'update': False, 'delete': False},
                    'Media Files': {'read': True, 'write': True, 'update': False, 'delete': False},
                },
            },
        ]

        for role_data in roles_data:
            role, created = Role.objects.get_or_create(
                name=role_data['name'],
                defaults={
                    'description': role_data['description'],
                    'is_system': role_data['is_system'],
                    'created_by': admin_user,
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'  [+] Created role: {role_data["name"]}'))

                # Create permissions
                for resource_name, perms in role_data['permissions'].items():
                    if resource_name in resources:
                        Permission.objects.get_or_create(
                            role=role,
                            resource=resources[resource_name],
                            defaults={
                                'can_read': perms.get('read', False),
                                'can_write': perms.get('write', False),
                                'can_update': perms.get('update', False),
                                'can_delete': perms.get('delete', False),
                            }
                        )

                # Ensure permissions exist for all resources
                for res_name, res_obj in resources.items():
                    Permission.objects.get_or_create(
                        role=role, resource=res_obj,
                        defaults={'can_read': False, 'can_write': False, 'can_update': False, 'can_delete': False}
                    )

        # ── Assign Admin role to admin user ────────────────────
        admin_role = Role.objects.get(name='Admin')
        _, created = UserRoleAssignment.objects.get_or_create(
            user=admin_user,
            role=admin_role,
            defaults={'assigned_by': admin_user}
        )
        if created:
            self.stdout.write(self.style.SUCCESS('  [+] Assigned Admin role to admin user'))

        # ── Create sample users ────────────────────────────────
        sample_users = [
            {'email': 'editor@example.com', 'first_name': 'Jane', 'last_name': 'Editor', 'role': 'Editor'},
            {'email': 'viewer@example.com', 'first_name': 'John', 'last_name': 'Viewer', 'role': 'Viewer'},
            {'email': 'contributor@example.com', 'first_name': 'Alice', 'last_name': 'Writer', 'role': 'Contributor'},
        ]

        for user_data in sample_users:
            user, created = User.objects.get_or_create(
                email=user_data['email'],
                defaults={
                    'username': user_data['email'].split('@')[0],
                    'first_name': user_data['first_name'],
                    'last_name': user_data['last_name'],
                    'is_active': True,
                }
            )
            if created:
                user.set_password('password123')
                user.save()
                role = Role.objects.get(name=user_data['role'])
                UserRoleAssignment.objects.get_or_create(
                    user=user, role=role,
                    defaults={'assigned_by': admin_user}
                )
                self.stdout.write(self.style.SUCCESS(f'  [+] Created user: {user_data["email"]} with {user_data["role"]} role'))

        # ── Create seed activity logs ──────────────────────────
        if not ActivityLog.objects.exists():
            ActivityLog.objects.create(
                user=admin_user,
                action_type='create_role',
                description='System initialized: Default roles created',
                role_affected='Admin, Editor, Viewer, Contributor',
            )
            ActivityLog.objects.create(
                user=admin_user,
                action_type='create_resource',
                description='System initialized: Default resources created',
                resource_affected='Articles, User Profiles, Settings, Reports, API Endpoints, Audit Logs, Media Files',
            )

        # ── Create Seed Articles ──────────────────────────────
        from rbac.models import Article
        if not Article.objects.exists():
            Article.objects.create(
                title='Understanding Role-Based Access Control',
                content='Role-Based Access Control (RBAC) is an approach to restricting system access to authorized users in a highly secure and manageable manner.',
                author=admin_user,
            )
            Article.objects.create(
                title='Implementing JWT Tokens in Django Ninja',
                content='JSON Web Tokens (JWT) are an open, industry standard RFC 7519 method for representing claims securely between two parties. Dynamic JWT authentication fits beautifully into the Django Ninja framework.',
                author=admin_user,
            )
            self.stdout.write(self.style.SUCCESS('  [+] Created seed articles for permissions testing'))

        self.stdout.write(self.style.SUCCESS('\n[OK] Database seeded successfully!'))
        self.stdout.write('\nLogin credentials:')
        self.stdout.write('   Admin:       admin@example.com / admin123')
        self.stdout.write('   Editor:      editor@example.com / password123')
        self.stdout.write('   Viewer:      viewer@example.com / password123')
        self.stdout.write('   Contributor: contributor@example.com / password123\n')
