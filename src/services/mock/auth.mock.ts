import type { AuthService } from '@/services/api/intelligence.service';
import type { AuthUser, LoginCredentials, RegisterPayload } from '@/types';
import { simulateNetworkDelay } from './delay';

function buildInitials(name: string): string {
  const parts = name.trim().split(/\s+/);
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return `${parts[0][0] ?? ''}${parts[parts.length - 1][0] ?? ''}`.toUpperCase();
}

export const mockAuthService: AuthService = {
  async login(credentials: LoginCredentials): Promise<AuthUser> {
    await simulateNetworkDelay(420);
    if (credentials.password === 'error') {
      throw new Error('Invalid email or password. (Sample error trigger)');
    }
    const localName = credentials.email.split('@')[0]?.replace(/[._]/g, ' ') || 'Developer';
    const formattedName = localName.replace(/\b\w/g, (c) => c.toUpperCase());
    return {
      id: 'usr-mock-email',
      name: formattedName,
      email: credentials.email.trim(),
      avatarInitials: buildInitials(formattedName),
      provider: 'email',
    };
  },

  async loginWithGitHub(): Promise<AuthUser> {
    await simulateNetworkDelay(450);
    return {
      id: 'usr-mock-github',
      name: 'Alex Rivera',
      email: 'alex.rivera@github.example',
      avatarInitials: 'AR',
      provider: 'github',
    };
  },

  async register(payload: RegisterPayload): Promise<AuthUser> {
    await simulateNetworkDelay(450);
    if (payload.email.toLowerCase().includes('taken')) {
      throw new Error('An account with this email already exists (sample check).');
    }
    return {
      id: `usr-${Date.now()}`,
      name: payload.name.trim(),
      email: payload.email.trim(),
      avatarInitials: buildInitials(payload.name),
      provider: 'email',
    };
  },

  async logout(): Promise<void> {
    await simulateNetworkDelay(150);
  },
};
