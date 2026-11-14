import { useCallback } from 'react';
import { useAuthStore } from '../stores/auth-store';
import { api } from '@/shared/lib/api-client';

export function useAuth() {
  const {
    token,
    username,
    role,
    astronautId,
    displayName,
    isDemo,
    setCredentials,
    initDirectEntry,
    switchRole,
    logout: clearAuth,
    setDemo,
  } = useAuthStore();

  const login = useCallback(async (uname: string, password: string) => {
    const result = await api.login({ username: uname, password });
    setCredentials(result.access_token, result.user);
    return result;
  }, [setCredentials]);

  const register = useCallback(async (uname: string, password: string, userRole: string = 'ASTRONAUT', astroId: string | null = null) => {
    return api.register({ username: uname, password, role: userRole, astronaut_id: astroId });
  }, []);

  const logout = useCallback(() => {
    clearAuth();
  }, [clearAuth]);

  const isAuthenticated = Boolean(token);
  const isPrivileged = role === 'MEDICAL_OFFICER' || role === 'ADMINISTRATOR';
  const isAdmin = role === 'ADMINISTRATOR';

  return {
    token,
    username,
    role,
    astronautId,
    displayName,
    isDemo,
    isAuthenticated,
    isPrivileged,
    isAdmin,
    login,
    register,
    initDirectEntry,
    switchRole,
    logout,
    setDemo,
  };
}
