import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface AuthState {
  token: string | null;
  username: string;
  role: string;
  astronautId: string;
  isDemo: boolean;
  setCredentials: (token: string, user: { username: string; role: string; astronaut_id: string | null; is_demo: boolean }) => void;
  logout: () => void;
  setDemo: (isDemo: boolean) => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      username: '',
      role: 'ASTRONAUT',
      astronautId: 'AST-001',
      isDemo: false,
      setCredentials: (token, user) =>
        set({
          token,
          username: user.username,
          role: user.role,
          astronautId: user.astronaut_id || 'AST-001',
          isDemo: user.is_demo,
        }),
      logout: () =>
        set({
          token: null,
          username: '',
          role: 'ASTRONAUT',
          astronautId: 'AST-001',
          isDemo: false,
        }),
      setDemo: (isDemo) => set({ isDemo }),
    }),
    { name: 'trustline-auth' }
  )
);
