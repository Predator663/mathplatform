import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { User } from '../types';
import { useSubjectStore } from './subject';

interface AuthState {
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
  isAuthenticated: boolean;
  setAuth: (user: User, access: string, refresh: string) => void;
  clearAuth: () => void;
  updateUser: (user: User) => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      accessToken: null,
      refreshToken: null,
      isAuthenticated: false,

      setAuth: (user, access, refresh) => {
        localStorage.setItem('access_token', access);
        localStorage.setItem('refresh_token', refresh);
        set({ user, accessToken: access, refreshToken: refresh, isAuthenticated: true });
      },

      clearAuth: () => {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        set({ user: null, accessToken: null, refreshToken: null, isAuthenticated: false });
        // A stale activeSubjectId left over from this session (or a
        // different user on a shared browser) silently zeroes out every
        // subject-scoped screen for whoever logs in next — see
        // SubjectSwitcher.tsx. Wipe it so the next login starts clean.
        useSubjectStore.setState({ activeSubjectId: null, subjects: [] });
      },

      updateUser: (user) => set({ user }),
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({
        user: state.user,
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
);
