import { createContext, useContext, useState, useEffect } from 'react';

const AuthContext = createContext();

const DEMO_USERS = [
  {
    id: 'planner',
    name: 'Dr. Aditi Rao',
    role: 'Lead Demand Planner',
    department: 'Supply Chain Planning',
    avatar: 'A',
    tone: 'gold',
  },
  {
    id: 'manager',
    name: 'Rohan Mehta',
    role: 'Regional SCM Manager',
    department: 'DC Operations & Rebalancing',
    avatar: 'R',
    tone: 'forest',
  },
  {
    id: 'vp',
    name: 'Vikram Nair',
    role: 'VP Global Supply Chain',
    department: 'Executive Leadership',
    avatar: 'V',
    tone: 'brick',
  },
];

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    const saved = localStorage.getItem('medcare_user');
    return saved ? JSON.parse(saved) : DEMO_USERS[0];
  });

  const login = (userData) => {
    setUser(userData);
    localStorage.setItem('medcare_user', JSON.stringify(userData));
  };

  const logout = () => {
    setUser(null);
    localStorage.removeItem('medcare_user');
  };

  return (
    <AuthContext.Provider value={{ user, login, logout, demoUsers: DEMO_USERS }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
