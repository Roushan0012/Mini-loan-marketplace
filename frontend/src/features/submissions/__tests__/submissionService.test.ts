import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  generateSecureIdempotencyKey,
  getOrCreateSubmissionKey,
  clearSubmissionKey,
  submissionService,
} from '../services/submissionService';
import { apiClient } from '../../../services/apiClient';

describe('Submission Service & Idempotency Key Management', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    sessionStorage.clear();
  });

  it('33. generateSecureIdempotencyKey generates valid UUID v4 using crypto', () => {
    const key = generateSecureIdempotencyKey();
    expect(key).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i);
    expect(key.length).toBe(36);
  });

  it('31. getOrCreateSubmissionKey persists key in sessionStorage per application', () => {
    const key1 = getOrCreateSubmissionKey(42);
    expect(key1).toBeTruthy();

    // Stored in application-specific key
    expect(sessionStorage.getItem('mini-loan-marketplace:submission:42')).toBe(key1);

    // Reading again returns the exact same key
    const key2 = getOrCreateSubmissionKey(42);
    expect(key2).toBe(key1);

    // Different application gets a different key
    const otherKey = getOrCreateSubmissionKey(99);
    expect(otherKey).not.toBe(key1);
  });

  it('29 & 30. Reuses the same key after simulated network failure or retry', () => {
    const key = getOrCreateSubmissionKey(42);

    // Simulated retry
    const retryKey = getOrCreateSubmissionKey(42);
    expect(retryKey).toBe(key);
  });

  it('Clears submission key only on explicit clear', () => {
    getOrCreateSubmissionKey(42);
    expect(sessionStorage.getItem('mini-loan-marketplace:submission:42')).toBeTruthy();

    clearSubmissionKey(42);
    expect(sessionStorage.getItem('mini-loan-marketplace:submission:42')).toBeNull();
  });

  it('sessionStorage working: same key returned on repeated calls', () => {
    clearSubmissionKey(101);
    const key1 = getOrCreateSubmissionKey(101);
    const key2 = getOrCreateSubmissionKey(101);
    expect(key1).toBe(key2);
    expect(sessionStorage.getItem('mini-loan-marketplace:submission:101')).toBe(key1);
  });

  it('sessionStorage getItem throwing: in-memory fallback key reused on retry', () => {
    clearSubmissionKey(102);
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('SecurityError: The operation is insecure.');
    });

    const key1 = getOrCreateSubmissionKey(102);
    expect(key1).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i);

    // Repeated call/retry reuses fallback key
    const key2 = getOrCreateSubmissionKey(102);
    expect(key2).toBe(key1);
  });

  it('sessionStorage setItem throwing: in-memory fallback key reused on retry', () => {
    clearSubmissionKey(103);
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('QuotaExceededError: The quota has been exceeded.');
    });

    const key1 = getOrCreateSubmissionKey(103);
    expect(key1).toBeTruthy();

    // Repeated call/retry reuses fallback key
    const key2 = getOrCreateSubmissionKey(103);
    expect(key2).toBe(key1);
  });

  it('clearSubmissionKey removes in-memory fallback key', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('Storage access denied');
    });

    clearSubmissionKey(104);
    const key1 = getOrCreateSubmissionKey(104);
    expect(key1).toBeTruthy();

    // After clearing, a new fallback key is generated
    clearSubmissionKey(104);
    const key2 = getOrCreateSubmissionKey(104);
    expect(key2).toBeTruthy();
    expect(key2).not.toBe(key1);
  });

  it('crypto.randomUUID is preferred where available', () => {
    const mockUUID = '11111111-2222-4333-8444-555555555555';
    const uuidSpy = vi.spyOn(crypto, 'randomUUID').mockReturnValue(mockUUID as `${string}-${string}-${string}-${string}-${string}`);

    const key = generateSecureIdempotencyKey();
    expect(key).toBe(mockUUID);
    expect(uuidSpy).toHaveBeenCalledTimes(1);
  });

  it('crypto.getRandomValues fallback works when crypto.randomUUID is unavailable', () => {
    const originalRandomUUID = crypto.randomUUID;
    // Temporarily remove crypto.randomUUID
    Object.defineProperty(crypto, 'randomUUID', {
      value: undefined,
      configurable: true,
      writable: true,
    });

    try {
      const key = generateSecureIdempotencyKey();
      expect(key).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i);
      expect(key.length).toBe(36);
    } finally {
      Object.defineProperty(crypto, 'randomUUID', {
        value: originalRandomUUID,
        configurable: true,
        writable: true,
      });
    }
  });

  it('Math.random is never used for idempotency key generation', () => {
    const mathSpy = vi.spyOn(Math, 'random');

    generateSecureIdempotencyKey();
    getOrCreateSubmissionKey(105);

    expect(mathSpy).not.toHaveBeenCalled();
  });

  it('27 & 28. submitSelectedOffer sends POST with empty body and Idempotency-Key header', async () => {
    const postSpy = vi.spyOn(apiClient, 'post').mockResolvedValue({
      id: 1,
      application_id: 42,
      offer_id: 101,
      lender_code: 'APEX_FINANCIAL',
      lender_name: 'Apex Financial',
      policy_version: 'v1.0',
      status: 'submitted',
      mock_reference: 'MOCK-REF-123',
      submitted_at: '2026-03-01T12:00:00Z',
      created_at: '2026-03-01T12:00:00Z',
      updated_at: '2026-03-01T12:00:00Z',
      submission_result: 'created',
    });

    const key = 'test-idempotency-key-uuid-12345';
    const result = await submissionService.submitSelectedOffer(42, 101, key);

    expect(postSpy).toHaveBeenCalledTimes(1);
    const [endpoint, body, options] = postSpy.mock.calls[0];
    expect(endpoint).toBe('/applications/42/offers/101/submit');
    // 28. Empty body
    expect(body).toBeUndefined();
    // 27. Idempotency-Key passed in options
    expect(options).toEqual({ idempotencyKey: key });
    expect(result.status).toBe('submitted');
  });

  it('getSubmissionStatus calls GET /applications/{id}/submission', async () => {
    const getSpy = vi.spyOn(apiClient, 'get').mockResolvedValue(null);

    const res = await submissionService.getSubmissionStatus(42);
    expect(getSpy).toHaveBeenCalledWith('/applications/42/submission');
    expect(res).toBeNull();
  });

  it('getSubmissionEvents calls GET /applications/{id}/submission/events', async () => {
    const getSpy = vi.spyOn(apiClient, 'get').mockResolvedValue([]);

    const res = await submissionService.getSubmissionEvents(42);
    expect(getSpy).toHaveBeenCalledWith('/applications/42/submission/events');
    expect(res).toEqual([]);
  });
});
