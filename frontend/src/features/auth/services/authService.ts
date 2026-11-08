import { apiClient } from '../../../services/apiClient';
import { clearStoredToken, getStoredToken, setStoredToken } from '../../../services/tokenStorage';
import { AuthTokens, LoginPayload, RegisterPayload, UserProfile } from '../../../types/auth';

export const authService = {
  /**
   * Register a new customer account.
   * Public registration always creates a customer role on the backend.
   */
  async register(payload: RegisterPayload): Promise<UserProfile> {
    return apiClient.post<UserProfile>('/auth/register', payload, {
      requiresAuth: false,
    });
  },

  /**
   * Log in with email and password.
   * Returns bearer token and expiration.
   */
  async login(payload: LoginPayload): Promise<AuthTokens> {
    const tokens = await apiClient.post<AuthTokens>('/auth/login', payload, {
      requiresAuth: false,
    });
    setStoredToken(tokens.access_token);
    return tokens;
  },

  /**
   * Fetch currently authenticated user profile.
   */
  async getCurrentUser(): Promise<UserProfile> {
    return apiClient.get<UserProfile>('/auth/me');
  },

  /**
   * Log out current user and clear local session.
   */
  logout(): void {
    clearStoredToken();
  },

  /**
   * Check if a token is currently present.
   */
  hasToken(): boolean {
    return Boolean(getStoredToken());
  },
};
