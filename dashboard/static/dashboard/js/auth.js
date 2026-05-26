/**
 * Auth Module — JWT Token Management & API Client
 * Handles token storage, refresh, and authenticated API calls.
 */
const Auth = (() => {
    const API_BASE = '/api';
    const TOKEN_KEY = 'access_token';
    const REFRESH_KEY = 'refresh_token';
    const USER_KEY = 'user';

    /** Get stored access token */
    function getAccessToken() {
        return localStorage.getItem(TOKEN_KEY);
    }

    /** Get stored refresh token */
    function getRefreshToken() {
        return localStorage.getItem(REFRESH_KEY);
    }

    /** Store tokens */
    function setTokens(access, refresh) {
        localStorage.setItem(TOKEN_KEY, access);
        localStorage.setItem(REFRESH_KEY, refresh);
    }

    /** Get stored user data */
    function getUser() {
        try {
            return JSON.parse(localStorage.getItem(USER_KEY));
        } catch {
            return null;
        }
    }

    /** Store user data */
    function setUser(user) {
        localStorage.setItem(USER_KEY, JSON.stringify(user));
    }

    /** Clear all auth data */
    function clearAuth() {
        localStorage.removeItem(TOKEN_KEY);
        localStorage.removeItem(REFRESH_KEY);
        localStorage.removeItem(USER_KEY);
    }

    /** Check if user is logged in */
    function isLoggedIn() {
        return !!getAccessToken();
    }

    /** Decode JWT payload (without verification) */
    function decodeToken(token) {
        try {
            const payload = token.split('.')[1];
            return JSON.parse(atob(payload));
        } catch {
            return null;
        }
    }

    /** Check if token is expired */
    function isTokenExpired(token) {
        const decoded = decodeToken(token);
        if (!decoded || !decoded.exp) return true;
        return Date.now() >= decoded.exp * 1000;
    }

    /** Refresh the access token */
    async function refreshAccessToken() {
        const refreshToken = getRefreshToken();
        if (!refreshToken) {
            throw new Error('No refresh token available');
        }

        const res = await fetch(`${API_BASE}/auth/token/refresh/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ refresh: refreshToken }),
        });

        if (!res.ok) {
            clearAuth();
            throw new Error('Token refresh failed');
        }

        const data = await res.json();
        setTokens(data.access, data.refresh);
        return data.access;
    }

    /** Get a valid access token, refreshing if needed */
    async function getValidToken() {
        let token = getAccessToken();
        if (!token) {
            throw new Error('Not authenticated');
        }

        if (isTokenExpired(token)) {
            token = await refreshAccessToken();
        }

        return token;
    }

    /**
     * Make an authenticated API request.
     * Automatically handles token refresh on 401.
     */
    async function apiCall(endpoint, options = {}) {
        const token = await getValidToken();

        const defaultHeaders = {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`,
        };

        const config = {
            ...options,
            headers: {
                ...defaultHeaders,
                ...options.headers,
            },
        };

        if (options.body && typeof options.body === 'object') {
            config.body = JSON.stringify(options.body);
        }

        let res = await fetch(`${API_BASE}${endpoint}`, config);

        // If 401, try refreshing token once
        if (res.status === 401) {
            try {
                const newToken = await refreshAccessToken();
                config.headers['Authorization'] = `Bearer ${newToken}`;
                res = await fetch(`${API_BASE}${endpoint}`, config);
            } catch {
                clearAuth();
                window.location.href = '/login/';
                throw new Error('Session expired');
            }
        }

        const data = await res.json();

        if (!res.ok) {
            throw new Error(data.detail || data.message || `API error: ${res.status}`);
        }

        return data;
    }

    /** Logout the user */
    async function logout() {
        try {
            const refreshToken = getRefreshToken();
            if (refreshToken) {
                await fetch(`${API_BASE}/auth/logout/`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${getAccessToken()}`,
                    },
                    body: JSON.stringify({ refresh: refreshToken }),
                });
            }
        } catch {
            // Ignore logout API errors
        }

        clearAuth();
        window.location.href = '/login/';
    }

    /** Fetch and update current user profile */
    async function fetchCurrentUser() {
        const user = await apiCall('/auth/me/');
        setUser(user);
        return user;
    }

    return {
        getAccessToken,
        getRefreshToken,
        setTokens,
        getUser,
        setUser,
        clearAuth,
        isLoggedIn,
        apiCall,
        logout,
        fetchCurrentUser,
        API_BASE,
    };
})();
