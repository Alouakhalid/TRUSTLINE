import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export interface AuthUser {
  username: string;
  role: string;
  astronaut_id: string | null;
  display_name?: string;
  is_demo: boolean;
}

interface AuthState {
  token: string | null;
  username: string;
  role: string;
  astronautId: string | null;
  displayName: string;
  isDemo: boolean;
  setCredentials: (token: string, user: AuthUser) => void;
  initDirectEntry: () => Promise<void>;
  switchRole: (targetRole: 'ASTRONAUT' | 'MEDICAL_OFFICER' | 'ADMINISTRATOR', astronautId?: string) => Promise<void>;
  logout: () => void;
  setDemo: (isDemo: boolean) => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      username: '',
      role: 'ASTRONAUT',
      astronautId: null, // Invariant: Unknown astronaut identity must NEVER default to AST-001
      displayName: '',
      isDemo: false,
      setCredentials: (token, user) =>
        set({
          token,
          username: user.username,
          role: user.role,
          astronautId: user.astronaut_id || null,
          displayName: user.display_name || user.username,
          isDemo: user.is_demo,
        }),
      initDirectEntry: async () => {
        try {
          const res = await fetch('/auth/direct-entry', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({}),
          });
          if (res.ok) {
            const data = await res.json();
            set({
              token: data.access_token,
              username: data.user.username,
              role: data.user.role,
              astronautId: data.user.astronaut_id || null,
              displayName: data.user.display_name || data.user.username,
              isDemo: data.user.is_demo,
            });
          }
        } catch (e) {
          console.warn('Direct entry init failed:', e);
        }
      },
      switchRole: async (targetRole, astronautId) => {
        try {
          const res = await fetch('/auth/role-token', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ target_role: targetRole, astronaut_id: astronautId || null }),
          });
          if (res.ok) {
            const data = await res.json();
            set({
              token: data.access_token,
              username: data.user.username,
              role: data.user.role,
              astronautId: data.user.astronaut_id || null,
              displayName: data.user.display_name || data.user.username,
              isDemo: data.user.is_demo,
            });
          }
        } catch (e) {
          console.error('Role switch failed:', e);
        }
      },
      logout: () =>
        set({
          token: null,
          username: '',
          role: 'ASTRONAUT',
          astronautId: null,
          displayName: '',
          isDemo: false,
        }),
      setDemo: (isDemo) => set({ isDemo }),
    }),
    { name: 'trustline-auth' }
  )
);
