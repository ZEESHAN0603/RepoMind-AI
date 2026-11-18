import { create } from 'zustand';
import { APP_CONFIG } from '@/constants/app';
import type { AuthUser, LoginCredentials, RegisterPayload } from '@/types';
import { authService } from '@/services';

interface AuthState {
  user: AuthUser | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
  login: (credentials: LoginCredentials) => Promise<void>;
  loginWithGitHub: () => Promise<void>;
  register: (payload: RegisterPayload) => Promise<void>;
  logout: () => Promise<void>;
  clearError: () => void;
}

function getInitialUser(): AuthUser | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = window.localStorage.getItem(APP_CONFIG.AUTH_STORAGE_KEY);
    if (!raw || raw === 'signed_out') return null;
    const token = window.localStorage.getItem('repomind_access_token');
    if (!token) return null;
    return JSON.parse(raw) as AuthUser;
  } catch {
    return null;
  }
}

const initialUser = getInitialUser();

export const useAuthStore = create<AuthState>((set) => ({
  user: initialUser,
  isAuthenticated: Boolean(initialUser),
  isLoading: false,
  error: null,

  login: async (credentials) => {
    set({ isLoading: true, error: null });
    try {
      const user = await authService.login(credentials);
      if (credentials.rememberMe) {
        window.localStorage.setItem(
          APP_CONFIG.AUTH_STORAGE_KEY,
          JSON.stringify(user)
        );
      } else {
        window.localStorage.removeItem(APP_CONFIG.AUTH_STORAGE_KEY);
      }
      set({ user, isAuthenticated: true, isLoading: false });
    } catch (err) {
      const message =
        err instanceof Error ? err.message : 'Unable to sign in.';
      set({ error: message, isLoading: false });
      throw err;
    }
  },

  loginWithGitHub: async () => {
    set({ isLoading: true, error: null });
    try {
      const user = await authService.loginWithGitHub();
      window.localStorage.setItem(
        APP_CONFIG.AUTH_STORAGE_KEY,
        JSON.stringify(user)
      );
      set({ user, isAuthenticated: true, isLoading: false });
    } catch (err) {
      const message =
        err instanceof Error ? err.message : 'GitHub sign-in failed.';
      set({ error: message, isLoading: false });
      throw err;
    }
  },

  register: async (payload) => {
    set({ isLoading: true, error: null });
    try {
      const user = await authService.register(payload);
      window.localStorage.setItem(
        APP_CONFIG.AUTH_STORAGE_KEY,
        JSON.stringify(user)
      );
      set({ user, isAuthenticated: true, isLoading: false });
    } catch (err) {
      const message =
        err instanceof Error ? err.message : 'Registration failed.';
      set({ error: message, isLoading: false });
      throw err;
    }
  },

  logout: async () => {
    await authService.logout();
    try {
      window.localStorage.setItem(APP_CONFIG.AUTH_STORAGE_KEY, 'signed_out');
    } catch {
      // ignore
    }
    set({ user: null, isAuthenticated: false, error: null });
  },

  clearError: () => set({ error: null }),
}));
