/**
 * Centralized API client for RepoMind frontend.
 * Provides unified base URL handling, Bearer token injection,
 * and automatic 401 token refresh retry interception.
 */

export const API_BASE: string = (
  (import.meta.env.VITE_API_BASE_URL as string | undefined) || '/api/v1'
).replace(/\/+$/, '');

export function getAuthHeader(): Record<string, string> {
  if (typeof window === 'undefined') return {};
  const token = window.localStorage.getItem('repomind_access_token');
  return token ? { Authorization: `Bearer ${token}` } : {};
}

let isRefreshing = false;
let refreshSubscribers: Array<(token: string) => void> = [];

function onTokenRefreshed(token: string) {
  refreshSubscribers.forEach((callback) => callback(token));
  refreshSubscribers = [];
}

function addRefreshSubscriber(callback: (token: string) => void) {
  refreshSubscribers.push(callback);
}

export async function refreshAccessToken(): Promise<string | null> {
  if (typeof window === 'undefined') return null;
  const refreshToken = window.localStorage.getItem('repomind_refresh_token');
  if (!refreshToken) return null;

  try {
    const res = await fetch(`${API_BASE}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });

    if (!res.ok) {
      window.localStorage.removeItem('repomind_access_token');
      window.localStorage.removeItem('repomind_refresh_token');
      return null;
    }

    const data = await res.json();
    if (data.access_token) {
      window.localStorage.setItem('repomind_access_token', data.access_token);
      if (data.refresh_token) {
        window.localStorage.setItem('repomind_refresh_token', data.refresh_token);
      }
      return data.access_token;
    }
    return null;
  } catch {
    return null;
  }
}

/**
 * Universal authenticated fetch wrapper that handles token refresh on 401.
 */
export async function apiFetch(
  input: string,
  init?: RequestInit
): Promise<Response> {
  const url = input.startsWith('http') ? input : `${API_BASE}${input.startsWith('/') ? '' : '/'}${input}`;

  const headers = new Headers(init?.headers || {});
  const currentToken = typeof window !== 'undefined' ? window.localStorage.getItem('repomind_access_token') : null;
  if (currentToken && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${currentToken}`);
  }

  const response = await fetch(url, {
    ...init,
    headers,
  });

  // Handle 401 Unauthorized with token refresh and retry
  if (response.status === 401 && typeof window !== 'undefined') {
    const refreshToken = window.localStorage.getItem('repomind_refresh_token');
    if (!refreshToken) {
      return response;
    }

    if (!isRefreshing) {
      isRefreshing = true;
      const newToken = await refreshAccessToken();
      isRefreshing = false;

      if (newToken) {
        onTokenRefreshed(newToken);
        headers.set('Authorization', `Bearer ${newToken}`);
        return fetch(url, { ...init, headers });
      } else {
        return response;
      }
    }

    // Wait for in-flight refresh to complete
    return new Promise<Response>((resolve) => {
      addRefreshSubscriber((newToken: string) => {
        headers.set('Authorization', `Bearer ${newToken}`);
        resolve(fetch(url, { ...init, headers }));
      });
    });
  }

  return response;
}
