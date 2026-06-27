import React, { createContext, useContext, useEffect, useState } from 'react';
import { login as authLogin, logout as authLogout, getToken, isAuthenticated as checkAuth } from '../services/auth';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => getToken());

  useEffect(() => {
    const current = getToken();
    if (current !== token) setToken(current);
  }, []);

  const login = async (pin) => {
    const result = await authLogin(pin);
    if (result) {
      setToken(getToken());
      return true;
    }
    return false;
  };

  const logout = () => {
    authLogout();
    setToken(null);
  };

  const isAuthenticated = () => checkAuth();

  return (
    <AuthContext.Provider value={{ token, login, logout, isAuthenticated }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
