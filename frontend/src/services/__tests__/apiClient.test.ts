import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { apiClient } from '../apiClient';
import { clearStoredToken, getStoredToken, setStoredToken } from '../tokenStorage';
import { ApiError } from '../apiErrors';

describe('apiClient', () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    sessionStorage.clear();
    vi.restoreAllMocks();
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it('1. Attaches bearer token when authenticated', async () => {
    setStoredToken('test-secret-token-12345');

    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ success: true }),
    });
    globalThis.fetch = mockFetch;

    await apiClient.get('/test-endpoint');

    expect(mockFetch).toHaveBeenCalledTimes(1);
    const headers = mockFetch.mock.calls[0][1]?.headers as Headers;
    expect(headers.get('Authorization')).toBe('Bearer test-secret-token-12345');
  });

  it('2. Does not expose token in errors or logs', async () => {
    const sensitiveToken = 'super-secret-user-bearer-token';
    setStoredToken(sensitiveToken);

    const mockFetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 403,
      statusText: 'Forbidden',
      json: async () => ({ detail: 'Access denied to this resource' }),
    });
    globalThis.fetch = mockFetch;

    try {
      await apiClient.get('/restricted-resource');
      expect.fail('Should have thrown an ApiError');
    } catch (err) {
      expect(err).toBeInstanceOf(ApiError);
      const apiErr = err as ApiError;
      expect(apiErr.status).toBe(403);
      expect(apiErr.message).toBe('Access denied to this resource');
      // Verify token is never embedded in error
      expect(JSON.stringify(apiErr)).not.toContain(sensitiveToken);
    }
  });

  it('3. Parses JSON API errors correctly for both string detail and validation error lists', async () => {
    // 3a. String detail (409 Conflict)
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 409,
      statusText: 'Conflict',
      json: async () => ({ detail: 'Email is already registered' }),
    });

    await expect(apiClient.post('/auth/register', {})).rejects.toMatchObject({
      status: 409,
      message: 'Email is already registered',
    });

    // 3b. Array detail (422 Unprocessable Content)
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 422,
      statusText: 'Unprocessable Entity',
      json: async () => ({
        detail: [
          { loc: ['body', 'password'], msg: 'Password must be at least 12 characters', type: 'value_error' },
        ],
      }),
    });

    try {
      await apiClient.post('/auth/register', {});
      expect.fail('Should have thrown 422 ApiError');
    } catch (err) {
      expect(err).toBeInstanceOf(ApiError);
      const apiErr = err as ApiError;
      expect(apiErr.status).toBe(422);
      expect(apiErr.getFormattedMessage()).toContain('Password must be at least 12 characters');
    }
  });

  it('4. Handles network failures gracefully', async () => {
    globalThis.fetch = vi.fn().mockRejectedValue(new Error('Failed to fetch'));

    await expect(apiClient.get('/applications')).rejects.toThrow(/Network failure/);
  });

  it('12. Logout and clearStoredToken removes token from sessionStorage', () => {
    setStoredToken('token-to-be-cleared');
    expect(getStoredToken()).toBe('token-to-be-cleared');

    clearStoredToken();
    expect(getStoredToken()).toBeNull();
  });

  it('Clears token automatically on confirmed 401 response', async () => {
    setStoredToken('expired-invalid-token');

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      statusText: 'Unauthorized',
      json: async () => ({ detail: 'Token has expired' }),
    });

    await expect(apiClient.get('/auth/me')).rejects.toThrow();
    expect(getStoredToken()).toBeNull();
  });
});
