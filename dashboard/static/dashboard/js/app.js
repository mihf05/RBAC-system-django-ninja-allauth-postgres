/**
 * RBAC Admin Dashboard — Main Application
 * Handles navigation, data loading, and all CRUD operations.
 */
document.addEventListener('DOMContentLoaded', () => {
    // ── Auth Check ────────────────────────────────────────────
    if (!Auth.isLoggedIn()) {
        window.location.href = '/login/';
        return;
    }

    // ── State ─────────────────────────────────────────────────
    let currentPage = 'dashboard';
    let rolesCache = [];
    let resourcesCache = [];
    let usersCache = [];
    let editingRoleId = null;
    let editingFeatureId = null;
    let managingUserId = null;

    // ── Chart Instances ───────────────────────────────────────
    let usersPerRoleChart = null;
    let rolesByStatusChart = null;

    // ── Initialize ────────────────────────────────────────────
    initApp();

    async function initApp() {
        setupNavigation();
        setupEventListeners();
        try {
            await Auth.fetchCurrentUser();
        } catch (err) {
            console.error('Failed to sync user profile:', err);
        }
        updateUserUI();
        await loadDashboard();
    }

    // ── User UI ───────────────────────────────────────────────
    function updateUserUI() {
        const user = Auth.getUser();
        if (!user) return;

        const initials = user.initials || user.email.substring(0, 2).toUpperCase();
        const name = user.full_name || user.email.split('@')[0];

        document.getElementById('sidebarAvatar').textContent = initials;
        document.getElementById('sidebarUserName').textContent = name;
        document.getElementById('topbarAvatar').textContent = initials;
        document.getElementById('topbarUsername').textContent = name;

        // Dynamic sidebar link adjustment based on permissions
        const isAdmin = user.is_staff || (user.roles && user.roles.some(r => r === 'Admin' || r.name === 'Admin'));
        const hasPerm = (resource, action) => {
            if (isAdmin) return true;
            return user.permissions && user.permissions[resource] && user.permissions[resource][action];
        };

        const setNavDisplay = (id, resource) => {
            const el = document.getElementById(id);
            if (el) {
                if (hasPerm(resource, 'read')) {
                    el.style.setProperty('display', '', '');
                } else {
                    el.style.setProperty('display', 'none', 'important');
                }
            }
        };

        setNavDisplay('nav-dashboard', 'Dashboard');
        setNavDisplay('nav-roles', 'Roles');
        setNavDisplay('nav-users', 'Users');
        setNavDisplay('nav-features', 'Features & APIs');
        setNavDisplay('nav-activity', 'Activity Log');
    }

    // ══════════════════════════════════════════════════════════
    // NAVIGATION
    // ══════════════════════════════════════════════════════════

    function setupNavigation() {
        document.querySelectorAll('.nav-item').forEach(item => {
            item.addEventListener('click', (e) => {
                e.preventDefault();
                navigateTo(item.dataset.page);
            });
        });

        // View All link on dashboard
        document.querySelectorAll('.view-all-link').forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                navigateTo(link.dataset.page);
            });
        });

        // Mobile menu toggle
        document.getElementById('menuToggle').addEventListener('click', () => {
            document.getElementById('sidebar').classList.toggle('open');
        });
    }

    function navigateTo(page) {
        currentPage = page;

        // Update nav
        document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
        document.querySelector(`.nav-item[data-page="${page}"]`)?.classList.add('active');

        // Update pages
        document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
        document.getElementById(`page-${page}`)?.classList.add('active');

        // Update title
        const titles = {
            dashboard: ['Dashboard', 'System overview & analytics'],
            roles: ['ADMIN ACCESS CONTROL & ROLE MANAGEMENT', 'Comprehensive System & User Permissions'],
            users: ['User Directory & Assignment', 'Manage users, roles, and invitations'],
            features: ['Features & Secure APIs', 'Configure dynamic system functions and allowed operations'],
            activity: ['Activity Log', 'Recent access changes & admin activity'],
        };
        const [title, subtitle] = titles[page] || ['Dashboard', ''];
        document.getElementById('pageTitle').textContent = title;
        document.getElementById('pageSubtitle').textContent = subtitle;

        // Load page data
        switch (page) {
            case 'dashboard': loadDashboard(); break;
            case 'roles': loadRoles(); break;
            case 'users': loadUsers(); break;
            case 'features': loadFeatures(); break;
            case 'activity': loadActivity(); break;
        }

        // Close mobile sidebar
        document.getElementById('sidebar').classList.remove('open');
    }

    // ══════════════════════════════════════════════════════════
    // EVENT LISTENERS
    // ══════════════════════════════════════════════════════════

    function setupEventListeners() {
        // Logout
        document.getElementById('logoutBtn').addEventListener('click', () => Auth.logout());

        // ── Roles ─────────────────────────────────────────────
        document.getElementById('btnNewRole').addEventListener('click', showNewRoleForm);
        document.getElementById('btnCancelRole').addEventListener('click', hideRoleForm);
        document.getElementById('btnCancelRole2').addEventListener('click', hideRoleForm);
        document.getElementById('roleForm').addEventListener('submit', handleSaveRole);

        document.getElementById('roleStatus').addEventListener('change', (e) => {
            document.getElementById('roleStatusLabel').textContent = e.target.checked ? 'Active' : 'Inactive';
        });

        document.getElementById('roleSearchInput').addEventListener('input', debounce(() => loadRoles(), 300));
        document.getElementById('permSearchInput').addEventListener('input', debounce(filterPermissionTable, 300));

        // Select All checkboxes
        ['Read', 'Write', 'Update', 'Delete'].forEach(perm => {
            document.getElementById(`selectAll${perm}`).addEventListener('change', (e) => {
                document.querySelectorAll(`.perm-${perm.toLowerCase()}`).forEach(toggle => {
                    if (e.target.checked) {
                        toggle.classList.add('active');
                    } else {
                        toggle.classList.remove('active');
                    }
                });
            });
        });

        // ── Users ─────────────────────────────────────────────
        document.getElementById('userSearchInput').addEventListener('input', debounce(() => loadUsers(), 300));
        document.getElementById('userStatusFilter').addEventListener('change', () => loadUsers());
        document.getElementById('userRoleFilter').addEventListener('change', () => loadUsers());

        // ── Features & APIs ───────────────────────────────────
        document.getElementById('btnNewFeature').addEventListener('click', showNewFeatureModal);
        document.getElementById('closeFeatureModal').addEventListener('click', hideFeatureModal);
        document.getElementById('btnCancelFeature').addEventListener('click', hideFeatureModal);
        document.getElementById('featureForm').addEventListener('submit', handleSaveFeature);
        document.getElementById('featureSearchInput').addEventListener('input', debounce(() => loadFeatures(), 300));



        // Invite User Modal
        document.getElementById('btnInviteUser').addEventListener('click', showInviteModal);
        document.getElementById('closeInviteModal').addEventListener('click', hideInviteModal);
        document.getElementById('btnCancelInvite').addEventListener('click', hideInviteModal);
        document.getElementById('inviteForm').addEventListener('submit', handleInviteUser);

        // Assign Role Modal
        document.getElementById('closeAssignModal').addEventListener('click', hideAssignModal);
        document.getElementById('btnAssignRole').addEventListener('click', handleAssignRole);

        // ── Activity ──────────────────────────────────────────
        document.getElementById('activitySearchInput').addEventListener('input', debounce(() => loadActivity(), 300));
        document.getElementById('activityTypeFilter').addEventListener('change', () => loadActivity());
    }

    // ══════════════════════════════════════════════════════════
    // DASHBOARD
    // ══════════════════════════════════════════════════════════

    async function loadDashboard() {
        try {
            const [stats, usersPerRole, rolesByStatus, activity] = await Promise.all([
                Auth.apiCall('/stats/overview/').catch(() => null),
                Auth.apiCall('/stats/users-per-role/').catch(() => null),
                Auth.apiCall('/stats/roles-by-status/').catch(() => null),
                Auth.apiCall('/activity/?page_size=5').catch(() => null),
            ]);

            // Update stats
            if (stats) {
                document.getElementById('statsGrid').style.display = '';
                animateNumber('statTotalUsers', stats.total_users);
                animateNumber('statTotalRoles', stats.total_roles);
                animateNumber('statActiveRoles', stats.active_roles);
                animateNumber('statPendingInvites', stats.pending_invites);
            } else {
                document.getElementById('statsGrid').style.display = 'none';
            }

            // Render charts
            if (usersPerRole && rolesByStatus) {
                document.querySelector('.charts-grid').style.display = '';
                renderUsersPerRoleChart(usersPerRole);
                renderRolesByStatusChart(rolesByStatus);
            } else {
                document.querySelector('.charts-grid').style.display = 'none';
            }

            // Render recent activity
            if (activity) {
                const activityTable = document.getElementById('dashboardActivityTable');
                if (activityTable) {
                    activityTable.closest('.card').style.display = '';
                    renderActivityTable('dashboardActivityBody', activity, true);
                }
            } else {
                const activityTable = document.getElementById('dashboardActivityTable');
                if (activityTable) {
                    activityTable.closest('.card').style.display = 'none';
                }
            }
        } catch (err) {
            showToast(err.message, 'error');
        }
    }

    function animateNumber(elementId, target) {
        const el = document.getElementById(elementId);
        const start = parseInt(el.textContent) || 0;
        const duration = 600;
        const startTime = performance.now();

        function update(now) {
            const elapsed = now - startTime;
            const progress = Math.min(elapsed / duration, 1);
            const eased = 1 - Math.pow(1 - progress, 3);
            el.textContent = Math.round(start + (target - start) * eased);
            if (progress < 1) requestAnimationFrame(update);
        }
        requestAnimationFrame(update);
    }

    function renderUsersPerRoleChart(data) {
        const ctx = document.getElementById('usersPerRoleChart').getContext('2d');
        if (usersPerRoleChart) usersPerRoleChart.destroy();

        usersPerRoleChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: data.map(d => d.label),
                datasets: [{
                    label: 'Users',
                    data: data.map(d => d.value),
                    backgroundColor: data.map(d => d.color || '#2563eb'),
                    borderRadius: 8,
                    borderSkipped: false,
                    barPercentage: 0.6,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: '#1e293b',
                        titleFont: { family: 'Inter', weight: '600' },
                        bodyFont: { family: 'Inter' },
                        padding: 12,
                        cornerRadius: 8,
                    },
                },
                scales: {
                    x: {
                        grid: { display: false },
                        ticks: { font: { family: 'Inter', size: 12, weight: '500' }, color: '#94a3b8' },
                    },
                    y: {
                        grid: { color: 'rgba(0,0,0,0.04)' },
                        ticks: {
                            font: { family: 'Inter', size: 12 },
                            color: '#94a3b8',
                            stepSize: 1,
                        },
                        beginAtZero: true,
                    },
                },
            },
        });
    }

    function renderRolesByStatusChart(data) {
        const ctx = document.getElementById('rolesByStatusChart').getContext('2d');
        if (rolesByStatusChart) rolesByStatusChart.destroy();

        rolesByStatusChart = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: data.map(d => d.label),
                datasets: [{
                    data: data.map(d => d.value),
                    backgroundColor: data.map(d => d.color),
                    borderWidth: 0,
                    spacing: 4,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '65%',
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            padding: 20,
                            font: { family: 'Inter', size: 13, weight: '500' },
                            color: '#475569',
                            usePointStyle: true,
                            pointStyleWidth: 12,
                        },
                    },
                    tooltip: {
                        backgroundColor: '#1e293b',
                        titleFont: { family: 'Inter', weight: '600' },
                        bodyFont: { family: 'Inter' },
                        padding: 12,
                        cornerRadius: 8,
                    },
                },
            },
        });
    }

    // ══════════════════════════════════════════════════════════
    // ROLES
    // ══════════════════════════════════════════════════════════

    async function loadRoles() {
        try {
            const search = document.getElementById('roleSearchInput')?.value || '';
            rolesCache = await Auth.apiCall(`/roles/?search=${encodeURIComponent(search)}`);
            renderRolesTable();
        } catch (err) {
            showToast(err.message, 'error');
        }
    }

    function renderRolesTable() {
        const tbody = document.getElementById('rolesTableBody');
        if (!rolesCache.length) {
            tbody.innerHTML = '<tr><td colspan="6" class="empty-state">No roles found. Create one to get started.</td></tr>';
            return;
        }

        tbody.innerHTML = rolesCache.map(role => `
            <tr>
                <td>
                    <strong>${escapeHtml(role.name)}</strong>
                    ${role.is_system ? '<span class="badge badge-pending" style="margin-left:6px;font-size:10px;">System</span>' : ''}
                </td>
                <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${escapeHtml(role.description || '—')}</td>
                <td><span style="font-weight:600;">${role.user_count}</span></td>
                <td><span class="badge ${role.is_active ? 'badge-active' : 'badge-inactive'}">${role.is_active ? 'Active' : 'Inactive'}</span></td>
                <td>${formatDate(role.created_at)}</td>
                <td>
                    <div style="display:flex;gap:4px;">
                        <button class="btn-icon edit" onclick="App.editRole(${role.id})" title="Edit Role">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                        </button>
                        ${!role.is_system ? `
                        <button class="btn-icon danger" onclick="App.deleteRole(${role.id}, '${escapeHtml(role.name)}')" title="Delete Role">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
                        </button>` : ''}
                    </div>
                </td>
            </tr>
        `).join('');
    }

    async function showNewRoleForm() {
        editingRoleId = null;
        document.getElementById('roleFormTitle').textContent = 'ROLE PROFILER: CREATE NEW ROLE';
        document.getElementById('btnSaveRole').querySelector('.btn-text').textContent = 'SAVE & CREATE ROLE';
        document.getElementById('roleFormId').value = '';
        document.getElementById('roleName').value = '';
        document.getElementById('roleDescription').value = '';
        document.getElementById('roleStatus').checked = true;
        document.getElementById('roleStatusLabel').textContent = 'Active';
        document.getElementById('roleNameError').textContent = '';

        document.getElementById('roleListCard').classList.add('hidden');
        document.getElementById('roleFormCard').classList.remove('hidden');

        await loadPermissionMatrix();
    }

    async function editRole(roleId) {
        try {
            const role = await Auth.apiCall(`/roles/${roleId}/`);
            editingRoleId = roleId;

            document.getElementById('roleFormTitle').textContent = 'ROLE PROFILER: EDIT ROLE';
            document.getElementById('btnSaveRole').querySelector('.btn-text').textContent = 'UPDATE ROLE';
            document.getElementById('roleFormId').value = roleId;
            document.getElementById('roleName').value = role.name;
            document.getElementById('roleDescription').value = role.description;
            document.getElementById('roleStatus').checked = role.is_active;
            document.getElementById('roleStatusLabel').textContent = role.is_active ? 'Active' : 'Inactive';
            document.getElementById('roleNameError').textContent = '';

            document.getElementById('roleListCard').classList.add('hidden');
            document.getElementById('roleFormCard').classList.remove('hidden');

            await loadPermissionMatrix(role.permissions);
        } catch (err) {
            showToast(err.message, 'error');
        }
    }

    function hideRoleForm() {
        document.getElementById('roleFormCard').classList.add('hidden');
        document.getElementById('roleListCard').classList.remove('hidden');
        editingRoleId = null;
    }

    async function loadPermissionMatrix(existingPermissions = []) {
        try {
            resourcesCache = await Auth.apiCall('/resources/');
            renderPermissionTable(existingPermissions);
        } catch (err) {
            showToast(err.message, 'error');
        }
    }

    function renderPermissionTable(existingPermissions = []) {
        const tbody = document.getElementById('permissionTableBody');
        if (!resourcesCache.length) {
            tbody.innerHTML = '<tr><td colspan="6" class="empty-state">No resources defined yet.</td></tr>';
            return;
        }

        // Create a map of existing permissions
        const permMap = {};
        existingPermissions.forEach(p => { permMap[p.resource_id] = p; });

        tbody.innerHTML = resourcesCache.map(resource => {
            const perm = permMap[resource.id] || {};
            
            // Draw controls ONLY if resource has that operation capability
            const readCell = resource.has_read 
                ? `<button type="button" class="perm-toggle perm-read ${perm.can_read ? 'active' : ''}" data-resource="${resource.id}" data-perm="read" title="Read"></button>`
                : `<span style="color:var(--text-muted);font-size:13px;font-weight:500;">—</span>`;
                
            const writeCell = resource.has_write 
                ? `<button type="button" class="perm-toggle perm-write ${perm.can_write ? 'active' : ''}" data-resource="${resource.id}" data-perm="write" title="Write"></button>`
                : `<span style="color:var(--text-muted);font-size:13px;font-weight:500;">—</span>`;
                
            const updateCell = resource.has_update 
                ? `<button type="button" class="perm-toggle perm-update ${perm.can_update ? 'active' : ''}" data-resource="${resource.id}" data-perm="update" title="Update"></button>`
                : `<span style="color:var(--text-muted);font-size:13px;font-weight:500;">—</span>`;
                
            const deleteCell = resource.has_delete 
                ? `<button type="button" class="perm-toggle perm-delete ${perm.can_delete ? 'active' : ''}" data-resource="${resource.id}" data-perm="delete" title="Delete"></button>`
                : `<span style="color:var(--text-muted);font-size:13px;font-weight:500;">—</span>`;

            return `
                <tr data-resource-id="${resource.id}">
                    <td>
                        <strong>${escapeHtml(resource.name)}</strong>
                        <div style="font-size: 10px; color: var(--text-muted); margin-top:2px;">
                            Supports: ${[
                                resource.has_read ? 'Read' : '',
                                resource.has_write ? 'Write' : '',
                                resource.has_update ? 'Update' : '',
                                resource.has_delete ? 'Delete' : ''
                            ].filter(Boolean).join(', ') || 'None'}
                        </div>
                    </td>
                    <td class="perm-cell">${readCell}</td>
                    <td class="perm-cell">${writeCell}</td>
                    <td class="perm-cell">${updateCell}</td>
                    <td class="perm-cell">${deleteCell}</td>
                    <td class="perm-cell">
                        <button type="button" class="select-all-row-btn" data-resource="${resource.id}">All</button>
                    </td>
                </tr>
            `;
        }).join('');

        // Bind toggle events
        tbody.querySelectorAll('.perm-toggle').forEach(btn => {
            btn.addEventListener('click', () => btn.classList.toggle('active'));
        });

        // Bind select all row
        tbody.querySelectorAll('.select-all-row-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const row = btn.closest('tr');
                const toggles = row.querySelectorAll('.perm-toggle');
                const allActive = Array.from(toggles).every(t => t.classList.contains('active'));
                toggles.forEach(t => {
                    if (allActive) t.classList.remove('active');
                    else t.classList.add('active');
                });
            });
        });
    }

    function filterPermissionTable() {
        const search = document.getElementById('permSearchInput').value.toLowerCase();
        document.querySelectorAll('#permissionTableBody tr').forEach(row => {
            const name = row.querySelector('td')?.textContent.toLowerCase() || '';
            row.style.display = name.includes(search) ? '' : 'none';
        });
    }

    function collectPermissions() {
        const permissions = [];
        document.querySelectorAll('#permissionTableBody tr').forEach(row => {
            const resourceId = parseInt(row.dataset.resourceId);
            if (!resourceId) return;

            permissions.push({
                resource_id: resourceId,
                can_read: row.querySelector('.perm-read')?.classList.contains('active') || false,
                can_write: row.querySelector('.perm-write')?.classList.contains('active') || false,
                can_update: row.querySelector('.perm-update')?.classList.contains('active') || false,
                can_delete: row.querySelector('.perm-delete')?.classList.contains('active') || false,
            });
        });
        return permissions;
    }

    async function handleSaveRole(e) {
        e.preventDefault();
        const btn = document.getElementById('btnSaveRole');
        const nameInput = document.getElementById('roleName');
        const nameError = document.getElementById('roleNameError');

        // Validate
        const name = nameInput.value.trim();
        if (!name) {
            nameError.textContent = 'Role name is required';
            nameInput.classList.add('error');
            return;
        }
        if (name.length < 2) {
            nameError.textContent = 'Role name must be at least 2 characters';
            nameInput.classList.add('error');
            return;
        }
        nameError.textContent = '';
        nameInput.classList.remove('error');

        btn.classList.add('loading');

        try {
            const roleData = {
                name,
                description: document.getElementById('roleDescription').value,
                is_active: document.getElementById('roleStatus').checked,
            };

            let role;
            if (editingRoleId) {
                role = await Auth.apiCall(`/roles/${editingRoleId}/`, { method: 'PUT', body: roleData });
            } else {
                role = await Auth.apiCall('/roles/', { method: 'POST', body: roleData });
            }

            // Save permissions
            const permissions = collectPermissions();
            if (permissions.length > 0) {
                await Auth.apiCall(`/roles/${role.id}/permissions/`, {
                    method: 'POST',
                    body: { permissions },
                });
            }

            showToast(`Role "${role.name}" ${editingRoleId ? 'updated' : 'created'} successfully`, 'success');
            hideRoleForm();
            await loadRoles();
        } catch (err) {
            showToast(err.message, 'error');
        } finally {
            btn.classList.remove('loading');
        }
    }

    async function deleteRole(roleId, roleName) {
        if (!confirm(`Are you sure you want to delete the role "${roleName}"? This action cannot be undone.`)) {
            return;
        }

        try {
            await Auth.apiCall(`/roles/${roleId}/`, { method: 'DELETE' });
            showToast(`Role "${roleName}" deleted successfully`, 'success');
            await loadRoles();
        } catch (err) {
            showToast(err.message, 'error');
        }
    }

    // ══════════════════════════════════════════════════════════
    // USERS
    // ══════════════════════════════════════════════════════════

    async function loadUsers() {
        try {
            const search = document.getElementById('userSearchInput')?.value || '';
            const status = document.getElementById('userStatusFilter')?.value || '';
            const role = document.getElementById('userRoleFilter')?.value || '';

            const params = new URLSearchParams();
            if (search) params.set('search', search);
            if (status) params.set('status', status);
            if (role) params.set('role', role);

            usersCache = await Auth.apiCall(`/users/?${params.toString()}`);
            renderUsersTable();
            await updateRoleFilters();
        } catch (err) {
            showToast(err.message, 'error');
        }
    }

    async function updateRoleFilters() {
        try {
            if (!rolesCache.length) {
                rolesCache = await Auth.apiCall('/roles/');
            }

            const select = document.getElementById('userRoleFilter');
            const currentValue = select.value;
            const options = '<option value="">All Roles</option>' +
                rolesCache.map(r => `<option value="${escapeHtml(r.name)}" ${r.name === currentValue ? 'selected' : ''}>${escapeHtml(r.name)}</option>`).join('');
            select.innerHTML = options;
        } catch {
            // Non-critical
        }
    }

    function renderUsersTable() {
        const tbody = document.getElementById('usersTableBody');
        if (!usersCache.length) {
            tbody.innerHTML = '<tr><td colspan="6" class="empty-state">No users found.</td></tr>';
            return;
        }

        tbody.innerHTML = usersCache.map(user => `
            <tr>
                <td>
                    <div class="user-cell">
                        <div class="user-cell-avatar">${escapeHtml(user.initials)}</div>
                        <span class="user-cell-name">${escapeHtml(user.full_name)}</span>
                    </div>
                </td>
                <td>${escapeHtml(user.email)}</td>
                <td>
                    <div class="role-badges-list">
                        ${user.roles.length ? user.roles.map(r => `<span class="badge badge-role">${escapeHtml(r.name)}</span>`).join('') : '<span style="color:var(--text-muted);font-size:12px;">No roles</span>'}
                    </div>
                </td>
                <td><span class="badge ${user.is_active ? 'badge-active' : 'badge-inactive'}">${user.is_active ? 'Active' : 'Deactivated'}</span></td>
                <td>${formatDate(user.date_joined)}</td>
                <td>
                    <div style="display:flex;gap:4px;">
                        <button class="btn-icon edit" onclick="App.manageUserRoles(${user.id})" title="Manage Roles">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
                        </button>
                        ${user.is_active
                            ? `<button class="btn-icon danger" onclick="App.deactivateUser(${user.id})" title="Deactivate">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="4.93" y1="4.93" x2="19.07" y2="19.07"/></svg>
                               </button>`
                            : `<button class="btn-icon edit" onclick="App.activateUser(${user.id})" title="Activate">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>
                               </button>`
                        }
                    </div>
                </td>
            </tr>
        `).join('');
    }

    async function manageUserRoles(userId) {
        try {
            managingUserId = userId;
            const user = await Auth.apiCall(`/users/${userId}/`);
            if (!rolesCache.length) rolesCache = await Auth.apiCall('/roles/');

            document.getElementById('assignUserName').textContent = `${user.full_name} (${user.email})`;

            // Current roles with revoke buttons
            const currentRoles = document.getElementById('currentRolesList');
            if (user.roles.length) {
                currentRoles.innerHTML = user.roles.map(r => `
                    <span class="badge badge-role" style="display:inline-flex;align-items:center;gap:6px;">
                        ${escapeHtml(r.name)}
                        <span style="cursor:pointer;font-size:14px;line-height:1;" onclick="App.revokeRole(${userId}, ${r.id})" title="Revoke">&times;</span>
                    </span>
                `).join('');
            } else {
                currentRoles.innerHTML = '<span style="color:var(--text-muted);font-size:12px;">No roles assigned</span>';
            }

            // Available roles dropdown
            const assignedIds = user.roles.map(r => r.id);
            const available = rolesCache.filter(r => r.is_active && !assignedIds.includes(r.id));
            const select = document.getElementById('assignRoleSelect');
            select.innerHTML = '<option value="">Select a role...</option>' +
                available.map(r => `<option value="${r.id}">${escapeHtml(r.name)}</option>`).join('');

            document.getElementById('assignRoleModal').classList.remove('hidden');
        } catch (err) {
            showToast(err.message, 'error');
        }
    }

    function hideAssignModal() {
        document.getElementById('assignRoleModal').classList.add('hidden');
        managingUserId = null;
    }

    async function handleAssignRole() {
        const roleId = document.getElementById('assignRoleSelect').value;
        if (!roleId || !managingUserId) {
            showToast('Please select a role', 'error');
            return;
        }

        try {
            await Auth.apiCall(`/users/${managingUserId}/assign-role/`, {
                method: 'POST',
                body: { role_id: parseInt(roleId) },
            });
            showToast('Role assigned successfully', 'success');
            await manageUserRoles(managingUserId);
            await loadUsers();
        } catch (err) {
            showToast(err.message, 'error');
        }
    }

    async function revokeRole(userId, roleId) {
        if (!confirm('Are you sure you want to revoke this role?')) return;

        try {
            await Auth.apiCall(`/users/${userId}/revoke-role/`, {
                method: 'POST',
                body: { role_id: roleId },
            });
            showToast('Role revoked successfully', 'success');
            await manageUserRoles(userId);
            await loadUsers();
        } catch (err) {
            showToast(err.message, 'error');
        }
    }

    async function deactivateUser(userId) {
        if (!confirm('Are you sure you want to deactivate this user?')) return;

        try {
            await Auth.apiCall(`/users/${userId}/deactivate/`, { method: 'POST' });
            showToast('User deactivated', 'success');
            await loadUsers();
        } catch (err) {
            showToast(err.message, 'error');
        }
    }

    async function activateUser(userId) {
        try {
            await Auth.apiCall(`/users/${userId}/activate/`, { method: 'POST' });
            showToast('User activated', 'success');
            await loadUsers();
        } catch (err) {
            showToast(err.message, 'error');
        }
    }

    // ── Invite Modal ──────────────────────────────────────────
    async function showInviteModal() {
        if (!rolesCache.length) {
            try { rolesCache = await Auth.apiCall('/roles/'); } catch {}
        }

        const group = document.getElementById('inviteRolesGroup');
        group.innerHTML = rolesCache.filter(r => r.is_active).map(r => `
            <label class="checkbox-label">
                <input type="checkbox" value="${r.id}">
                <span class="check-mark"></span>
                <span>${escapeHtml(r.name)}</span>
            </label>
        `).join('');

        document.getElementById('inviteEmail').value = '';
        document.getElementById('inviteEmailError').textContent = '';
        document.getElementById('inviteModal').classList.remove('hidden');
    }

    function hideInviteModal() {
        document.getElementById('inviteModal').classList.add('hidden');
    }

    async function handleInviteUser(e) {
        e.preventDefault();
        const btn = document.getElementById('btnSendInvite');
        const emailInput = document.getElementById('inviteEmail');
        const emailError = document.getElementById('inviteEmailError');

        const email = emailInput.value.trim();
        if (!email) {
            emailError.textContent = 'Email is required';
            return;
        }
        const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!emailPattern.test(email)) {
            emailError.textContent = 'Please enter a valid email';
            return;
        }
        emailError.textContent = '';

        const roleIds = Array.from(document.querySelectorAll('#inviteRolesGroup input:checked'))
            .map(cb => parseInt(cb.value));

        btn.classList.add('loading');

        try {
            await Auth.apiCall('/users/invite/', {
                method: 'POST',
                body: { email, role_ids: roleIds },
            });
            showToast(`Invitation sent to ${email}`, 'success');
            hideInviteModal();
        } catch (err) {
            showToast(err.message, 'error');
        } finally {
            btn.classList.remove('loading');
        }
    }

    // ══════════════════════════════════════════════════════════
    // ACTIVITY LOG
    // ══════════════════════════════════════════════════════════

    async function loadActivity() {
        try {
            const search = document.getElementById('activitySearchInput')?.value || '';
            const actionType = document.getElementById('activityTypeFilter')?.value || '';

            const params = new URLSearchParams();
            if (search) params.set('search', search);
            if (actionType) params.set('action_type', actionType);

            const activity = await Auth.apiCall(`/activity/?${params.toString()}`);
            renderActivityTable('activityTableBody', activity, false);
        } catch (err) {
            showToast(err.message, 'error');
        }
    }

    function renderActivityTable(tbodyId, logs, compact = false) {
        const tbody = document.getElementById(tbodyId);
        if (!logs.length) {
            const cols = compact ? 4 : 5;
            tbody.innerHTML = `<tr><td colspan="${cols}" class="empty-state">No activity logs found.</td></tr>`;
            return;
        }

        tbody.innerHTML = logs.map(log => {
            const actionClass = getActionClass(log.action_type);
            if (compact) {
                return `
                    <tr>
                        <td style="white-space:nowrap;">${formatDateTime(log.created_at)}</td>
                        <td>${escapeHtml(log.user_name)}</td>
                        <td><span class="action-badge ${actionClass}">${escapeHtml(log.action_display)}</span></td>
                        <td style="max-width:300px;overflow:hidden;text-overflow:ellipsis;">${escapeHtml(log.description)}</td>
                    </tr>
                `;
            }
            return `
                <tr>
                    <td style="white-space:nowrap;">${formatDateTime(log.created_at)}</td>
                    <td>
                        <div class="user-cell">
                            <span class="user-cell-name">${escapeHtml(log.user_name)}</span>
                        </div>
                    </td>
                    <td><span class="action-badge ${actionClass}">${escapeHtml(log.action_display)}</span></td>
                    <td style="max-width:300px;overflow:hidden;text-overflow:ellipsis;">${escapeHtml(log.description)}</td>
                    <td>
                        ${log.role_affected ? `<span class="badge badge-role">${escapeHtml(log.role_affected)}</span>` : ''}
                        ${log.resource_affected && !log.role_affected ? `<span style="font-size:12px;color:var(--text-muted);">${escapeHtml(log.resource_affected)}</span>` : ''}
                    </td>
                </tr>
            `;
        }).join('');
    }

    function getActionClass(actionType) {
        if (actionType.includes('create')) return 'create';
        if (actionType.includes('edit') || actionType.includes('update')) return 'edit';
        if (actionType.includes('delete')) return 'delete';
        if (actionType.includes('assign')) return 'assign';
        if (actionType.includes('revoke') || actionType.includes('deactivate')) return 'revoke';
        if (actionType.includes('login') || actionType.includes('register')) return 'login';
        return 'edit';
    }

    // ══════════════════════════════════════════════════════════
    // UTILITIES
    // ══════════════════════════════════════════════════════════

    function escapeHtml(str) {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    function formatDate(dateStr) {
        if (!dateStr) return '—';
        return new Date(dateStr).toLocaleDateString('en-US', {
            year: 'numeric', month: 'short', day: 'numeric',
        });
    }

    function formatDateTime(dateStr) {
        if (!dateStr) return '—';
        return new Date(dateStr).toLocaleString('en-US', {
            month: 'short', day: 'numeric',
            hour: '2-digit', minute: '2-digit',
        });
    }

    function debounce(fn, ms) {
        let timer;
        return (...args) => {
            clearTimeout(timer);
            timer = setTimeout(() => fn(...args), ms);
        };
    }

    function showToast(message, type = 'info') {
        const container = document.getElementById('toastContainer');
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.innerHTML = `
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:18px;height:18px;flex-shrink:0;">
                ${type === 'success'
                    ? '<polyline points="20 6 9 17 4 12"/>'
                    : type === 'error'
                    ? '<circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/>'
                    : '<circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/>'}
            </svg>
            <span>${escapeHtml(message)}</span>
        `;
        container.appendChild(toast);

        setTimeout(() => {
            toast.style.animation = 'toastOut 0.3s ease forwards';
            setTimeout(() => toast.remove(), 300);
        }, 4000);
    }

    // ══════════════════════════════════════════════════════════
    // FEATURES & APIS MANAGEMENT
    // ══════════════════════════════════════════════════════════

    async function loadFeatures() {
        try {
            const search = document.getElementById('featureSearchInput')?.value || '';
            resourcesCache = await Auth.apiCall(`/resources/?search=${encodeURIComponent(search)}`);
            renderFeaturesTable();
        } catch (err) {
            showToast(err.message, 'error');
        }
    }

    function renderFeaturesTable() {
        const tbody = document.getElementById('featuresTableBody');
        if (!resourcesCache.length) {
            tbody.innerHTML = '<tr><td colspan="5" class="empty-state">No features registered in the system.</td></tr>';
            return;
        }

        tbody.innerHTML = resourcesCache.map(res => {
            const badges = [];
            if (res.has_read) badges.push('<span class="badge" style="background:#dbeafe;color:#2563eb;font-weight:600;font-size:10px;margin-right:2px;">READ</span>');
            if (res.has_write) badges.push('<span class="badge" style="background:#dcfce7;color:#16a34a;font-weight:600;font-size:10px;margin-right:2px;">WRITE</span>');
            if (res.has_update) badges.push('<span class="badge" style="background:#fef3c7;color:#d97706;font-weight:600;font-size:10px;margin-right:2px;">UPDATE</span>');
            if (res.has_delete) badges.push('<span class="badge" style="background:#fee2e2;color:#dc2626;font-weight:600;font-size:10px;margin-right:2px;">DELETE</span>');
            
            return `
                <tr>
                    <td><strong>${escapeHtml(res.name)}</strong></td>
                    <td style="max-width:250px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${escapeHtml(res.description || '—')}</td>
                    <td>
                        <div style="display:flex;gap:4px;flex-wrap:wrap;">
                            ${badges.join('') || '<span style="color:var(--text-muted);font-size:11px;">No Operations</span>'}
                        </div>
                    </td>
                    <td><span class="badge ${res.is_active ? 'badge-active' : 'badge-inactive'}">${res.is_active ? 'Active' : 'Inactive'}</span></td>
                    <td>
                        <div style="display:flex;gap:4px;">
                            <button class="btn-icon edit" onclick="App.editFeature(${res.id})" title="Modify Operations">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                            </button>
                            <button class="btn-icon danger" onclick="App.deleteFeature(${res.id}, '${escapeHtml(res.name)}')" title="Delete Feature">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
                            </button>
                        </div>
                    </td>
                </tr>
            `;
        }).join('');
    }

    function showNewFeatureModal() {
        editingFeatureId = null;
        document.getElementById('featureModalTitle').textContent = 'Register New Feature / API';
        document.getElementById('featureFormId').value = '';
        document.getElementById('featureName').value = '';
        document.getElementById('featureName').disabled = false;
        document.getElementById('featureDescription').value = '';
        document.getElementById('featHasRead').checked = true;
        document.getElementById('featHasWrite').checked = true;
        document.getElementById('featHasUpdate').checked = true;
        document.getElementById('featHasDelete').checked = true;
        document.getElementById('featureNameError').textContent = '';
        
        document.getElementById('featureModal').classList.remove('hidden');
    }

    async function editFeature(resId) {
        try {
            const res = resourcesCache.find(r => r.id === resId);
            if (!res) return;
            editingFeatureId = resId;

            document.getElementById('featureModalTitle').textContent = 'Modify Feature Operations';
            document.getElementById('featureFormId').value = resId;
            document.getElementById('featureName').value = res.name;
            document.getElementById('featureName').disabled = true; // Avoid renaming system seeded features
            document.getElementById('featureDescription').value = res.description || '';
            document.getElementById('featHasRead').checked = res.has_read;
            document.getElementById('featHasWrite').checked = res.has_write;
            document.getElementById('featHasUpdate').checked = res.has_update;
            document.getElementById('featHasDelete').checked = res.has_delete;
            document.getElementById('featureNameError').textContent = '';

            document.getElementById('featureModal').classList.remove('hidden');
        } catch (err) {
            showToast(err.message, 'error');
        }
    }

    function hideFeatureModal() {
        document.getElementById('featureModal').classList.add('hidden');
        editingFeatureId = null;
    }

    async function handleSaveFeature(e) {
        e.preventDefault();
        const nameInput = document.getElementById('featureName');
        const nameError = document.getElementById('featureNameError');
        const name = nameInput.value.trim();

        if (!name) {
            nameError.textContent = 'Feature name is required';
            nameInput.classList.add('error');
            return;
        }
        nameError.textContent = '';
        nameInput.classList.remove('error');

        const btn = document.getElementById('btnSaveFeature');
        btn.classList.add('loading');

        try {
            const payload = {
                name,
                description: document.getElementById('featureDescription').value,
                has_read: document.getElementById('featHasRead').checked,
                has_write: document.getElementById('featHasWrite').checked,
                has_update: document.getElementById('featHasUpdate').checked,
                has_delete: document.getElementById('featHasDelete').checked,
            };

            if (editingFeatureId) {
                await Auth.apiCall(`/resources/${editingFeatureId}/`, {
                    method: 'PUT',
                    body: payload
                });
                showToast(`Feature "${name}" updated successfully`, 'success');
            } else {
                await Auth.apiCall('/resources/', {
                    method: 'POST',
                    body: payload
                });
                showToast(`Feature "${name}" registered successfully`, 'success');
            }

            hideFeatureModal();
            await loadFeatures();
        } catch (err) {
            showToast(err.message, 'error');
        } finally {
            btn.classList.remove('loading');
        }
    }

    async function deleteFeature(resId, name) {
        if (!confirm(`Are you sure you want to delete the Feature/API "${name}"? This will delete all permissions mapped to it.`)) {
            return;
        }

        try {
            await Auth.apiCall(`/resources/${resId}/`, { method: 'DELETE' });
            showToast(`Feature "${name}" deleted successfully`, 'success');
            await loadFeatures();
        } catch (err) {
            showToast(err.message, 'error');
        }
    }

    // ── Expose methods for inline onclick handlers ────────────
    window.App = {
        editRole,
        deleteRole,
        manageUserRoles,
        revokeRole,
        deactivateUser,
        activateUser,
        editFeature,
        deleteFeature,
    };
});
