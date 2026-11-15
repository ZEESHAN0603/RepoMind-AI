export interface AuthUser {
  id: string;
  name: string;
  email: string;
  avatarInitials: string;
  provider: 'email' | 'github';
}

export interface LoginCredentials {
  email: string;
  password: string;
  rememberMe: boolean;
}

export interface RegisterPayload {
  name: string;
  email: string;
  password: string;
}
