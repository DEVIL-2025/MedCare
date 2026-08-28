import { createContext, useContext, useState, useEffect } from 'react';
import { api } from '../api/client';

const AuthContext = createContext();

export const DEMO_PROFILES = [
  {
    id: 'admin',
    identifier: 'admin',
    password: 'Admin@12345',
    name: 'System Administrator',
    role: 'ADMIN',
    roleLabel: 'Admin (Full Access)',
    department: 'Executive SCM & IT Governance',
    avatar: 'A',
    tone: 'brick',
  },
  {
    id: 'manager',
    identifier: 'manager',
    password: 'Manager@12345',
    name: 'Rohan Mehta',
    role: 'MANAGER',
    roleLabel: 'Regional SCM Manager',
    department: 'DC Operations & Rebalancing',
    avatar: 'R',
    tone: 'forest',
  },
];

function formatUser(rawUser) {
  if (!rawUser) return null;
  const name = rawUser.full_name || rawUser.name || 'SCM User';
  const firstLetter = name.charAt(0).toUpperCase();
  return {
    ...rawUser,
    name,
    avatar: firstLetter,
    role: rawUser.role || 'MANAGER',
    roleLabel: rawUser.role === 'ADMIN' ? 'System Administrator' : 'Regional SCM Manager',
    permissions: rawUser.permissions || [],
  };
}

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem('medcare_auth_token'));
  const [user, setUser] = useState(() => {
    const saved = localStorage.getItem('medcare_user');
    return saved ? formatUser(JSON.parse(saved)) : null;
  });
  const [loading, setLoading] = useState(true);

  // Validate session against PostgreSQL on initial app mount
  useEffect(() => {
    async function validateSession() {
      const storedToken = localStorage.getItem('medcare_auth_token');
      if (!storedToken) {
        setUser(null);
        setLoading(false);
        return;
      }

      try {
        const userData = await api.getMe();
        const formatted = formatUser(userData);
        setUser(formatted);
        localStorage.setItem('medcare_user', JSON.stringify(formatted));
      } catch (err) {
        console.warn('Session verification failed, logging out:', err.message);
        localStorage.removeItem('medcare_auth_token');
        localStorage.removeItem('medcare_user');
        setUser(null);
        setToken(null);
      } finally {
        setLoading(false);
      }
    }

    validateSession();
  }, []);

  const login = async (identifier, password) => {
    const res = await api.login(identifier, password);
    if (res && res.access_token) {
      localStorage.setItem('medcare_auth_token', res.access_token);
      const formatted = formatUser(res.user);
      localStorage.setItem('medcare_user', JSON.stringify(formatted));
      setToken(res.access_token);
      setUser(formatted);
      return formatted;
    }
    throw new Error('Authentication response did not contain access token.');
  };

  const logout = async () => {
    try {
      await api.logout();
    } catch {
      // Ignore network errors during logout
    } finally {
      localStorage.removeItem('medcare_auth_token');
      localStorage.removeItem('medcare_user');
      setToken(null);
      setUser(null);
    }
  };

  const changePassword = async (currentPassword, newPassword) => {
    const res = await api.changePassword(currentPassword, newPassword);
    if (user) {
      const updatedUser = { ...user, must_change_password: false };
      setUser(updatedUser);
      localStorage.setItem('medcare_user', JSON.stringify(updatedUser));
    }
    return res;
  };

  const refreshUser = async () => {
    try {
      const userData = await api.getMe();
      const formatted = formatUser(userData);
      setUser(formatted);
      localStorage.setItem('medcare_user', JSON.stringify(formatted));
      return formatted;
    } catch (err) {
      console.error('Failed to refresh user:', err);
    }
  };

  const isAdmin = user?.role === 'ADMIN';
  const isManager = user?.role === 'MANAGER';

  const hasPermission = (permissionCode) => {
    if (!user) return false;
    if (isAdmin) return true;
    return user.permissions?.includes(permissionCode);
  };

  return (
    <AuthContext.Provider
      value={{
        token,
        user,
        loading,
        isAuthenticated: !!user && !!token,
        isAdmin,
        isManager,
        hasPermission,
        login,
        logout,
        changePassword,
        refreshUser,
        demoProfiles: DEMO_PROFILES,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
