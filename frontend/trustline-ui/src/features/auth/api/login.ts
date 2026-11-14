import { api } from '@/shared/lib/api-client';
import { useAuthStore } from '../stores/auth-store';

export async function loginUser(username: string, password: string) {
  const result = await api.login({ username, password });
  useAuthStore.getState().setCredentials(result.access_token, result.user);
  return result;
}

export async function registerUser(
  username: string,
  password: string,
  role: string = 'ASTRONAUT',
  astronautId: string | null = null,
) {
  return api.register({ username, password, role, astronaut_id: astronautId });
}

export async function fetchCurrentUser() {
  return api.getMe();
}
