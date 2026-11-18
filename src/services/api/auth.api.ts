import type { AuthService } from './intelligence.service';
import type { AuthUser, LoginCredentials, RegisterPayload } from '@/types';
import { mockAuthService } from '@/services/mock/auth.mock';

const API_BASE = '/api/v1';

function buildInitials(name: string): string {
  const parts = name.trim().split(/\s+/);
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return `${parts[0][0] ?? ''}${parts[parts.length - 1][0] ?? ''}`.toUpperCase();
}

export class ApiAuthService implements AuthService {
  async login(credentials: LoginCredentials): Promise<AuthUser> {
    try {
      const res = await fetch(`${API_BASE}/auth/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          email: credentials.email,
          password: credentials.password,
        }),
      });

      if (!res.ok) {
        let errorMsg = 'Invalid email or password.';
        try {
          const errorData = await res.json();
          if (errorData.detail) {
            errorMsg = typeof errorData.detail === 'string' ? errorData.detail : JSON.stringify(errorData.detail);
          }
        } catch {
          // Keep default message
        }
        throw new Error(errorMsg);
      }

      const tokenData = await res.json();
      if (typeof window !== 'undefined') {
        window.localStorage.setItem('repomind_access_token', tokenData.access_token);
        if (tokenData.refresh_token) {
          window.localStorage.setItem('repomind_refresh_token', tokenData.refresh_token);
        }
      }

      // Fetch current user details
      const meRes = await fetch(`${API_BASE}/auth/me`, {
        headers: {
          Authorization: `Bearer ${tokenData.access_token}`,
        },
      });

      if (meRes.ok) {
        const userData = await meRes.json();
        return {
          id: userData.id,
          name: userData.full_name,
          email: userData.email,
          avatarInitials: buildInitials(userData.full_name),
          provider: 'email',
        };
      }

      const defaultName = credentials.email.split('@')[0].replace(/[._]/g, ' ') || 'Developer';
      return {
        id: 'usr-current',
        name: defaultName,
        email: credentials.email,
        avatarInitials: buildInitials(defaultName),
        provider: 'email',
      };
    } catch (err) {
      // If server is not reachable, fall back to mock service for preview/offline mode
      if (err instanceof TypeError && err.message.includes('fetch')) {
        console.warn('Backend server unavailable, using mock auth.');
        return mockAuthService.login(credentials);
      }
      throw err;
    }
  }

  async register(payload: RegisterPayload): Promise<AuthUser> {
    try {
      const res = await fetch(`${API_BASE}/auth/register`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          email: payload.email,
          password: payload.password,
          full_name: payload.name,
        }),
      });

      if (!res.ok) {
        let errorMsg = 'Registration failed.';
        try {
          const errorData = await res.json();
          if (errorData.detail) {
            errorMsg = typeof errorData.detail === 'string' ? errorData.detail : JSON.stringify(errorData.detail);
          }
        } catch {
          // Keep default
        }
        throw new Error(errorMsg);
      }

      // After registration succeeds, log in to obtain JWT tokens
      return await this.login({
        email: payload.email,
        password: payload.password,
        rememberMe: true,
      });
    } catch (err) {
      if (err instanceof TypeError && err.message.includes('fetch')) {
        console.warn('Backend server unavailable, using mock register.');
        return mockAuthService.register(payload);
      }
      throw err;
    }
  }

  async loginWithGitHub(): Promise<AuthUser> {
    return mockAuthService.loginWithGitHub();
  }

  async logout(): Promise<void> {
    const refreshToken =
      typeof window !== 'undefined'
        ? window.localStorage.getItem('repomind_refresh_token')
        : null;

    if (refreshToken) {
      try {
        await fetch(`${API_BASE}/auth/logout`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ refresh_token: refreshToken }),
        });
      } catch {
        // Ignore logout request failure
      }
    }

    if (typeof window !== 'undefined') {
      window.localStorage.removeItem('repomind_access_token');
      window.localStorage.removeItem('repomind_refresh_token');
    }
  }
}

export const apiAuthService = new ApiAuthService();
