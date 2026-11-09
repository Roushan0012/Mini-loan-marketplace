import { apiClient } from '../../../services/apiClient';
import {
  LenderEventHistoryItem,
  OfferSubmissionResponse,
  OfferSubmissionStatusResponse,
} from '../types';

/**
 * Module-level in-memory fallback map for submission idempotency keys.
 * Used when window.sessionStorage is unavailable, restricted, or throws an error (e.g. sandboxed iframes, disabled storage, quota exceeded).
 *
 * IMPORTANT LIMITATION:
 * The in-memory fallback guarantees key reuse during the current JavaScript page lifetime.
 * It cannot guarantee reuse after a full page reload when sessionStorage is completely unavailable.
 */
const inMemoryFallbackKeys = new Map<string, string>();

/**
 * Generate a cryptographically secure UUID v4 string.
 * Strictly uses crypto.randomUUID() or crypto.getRandomValues(). Never uses Math.random().
 */
export function generateSecureIdempotencyKey(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }

  // Fallback using crypto.getRandomValues
  if (typeof crypto !== 'undefined' && typeof crypto.getRandomValues === 'function') {
    const bytes = new Uint8Array(16);
    crypto.getRandomValues(bytes);
    bytes[6] = (bytes[6] & 0x0f) | 0x40; // Version 4
    bytes[8] = (bytes[8] & 0x3f) | 0x80; // Variant 10
    const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('');
    return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
  }

  throw new Error('Secure cryptographic random generator is not supported by this environment.');
}

/**
 * Retrieve or generate an idempotency key for an application submission.
 * Prefers sessionStorage to survive page reloads and retries.
 * Falls back to an in-memory Map if sessionStorage is unavailable or throws.
 *
 * NOTE: The in-memory fallback guarantees key reuse across retry attempts within the current
 * browser tab/page lifecycle, but cannot survive full page reloads if sessionStorage is disabled.
 */
export function getOrCreateSubmissionKey(applicationId: number | string): string {
  const storageKey = `mini-loan-marketplace:submission:${applicationId}`;

  // If a fallback key was already generated for this session, reuse it
  const existingFallback = inMemoryFallbackKeys.get(storageKey);
  if (existingFallback && existingFallback.trim().length >= 8) {
    try {
      const stored = sessionStorage.getItem(storageKey);
      if (!stored) {
        sessionStorage.setItem(storageKey, existingFallback);
      }
    } catch {
      // Ignore sessionStorage exceptions when syncing
    }
    return existingFallback.trim();
  }

  try {
    const existingKey = sessionStorage.getItem(storageKey);
    if (existingKey && existingKey.trim().length >= 8) {
      return existingKey.trim();
    }
    const newKey = generateSecureIdempotencyKey();
    sessionStorage.setItem(storageKey, newKey);
    return newKey;
  } catch {
    // When sessionStorage.getItem or setItem fails (e.g. security sandbox, quota exceeded):
    const fallbackKey = inMemoryFallbackKeys.get(storageKey);
    if (fallbackKey && fallbackKey.trim().length >= 8) {
      return fallbackKey.trim();
    }
    const newFallbackKey = generateSecureIdempotencyKey();
    inMemoryFallbackKeys.set(storageKey, newFallbackKey);
    return newFallbackKey;
  }
}

/**
 * Remove the submission key for an application from both sessionStorage and in-memory fallback.
 */
export function clearSubmissionKey(applicationId: number | string): void {
  const storageKey = `mini-loan-marketplace:submission:${applicationId}`;
  inMemoryFallbackKeys.delete(storageKey);
  try {
    sessionStorage.removeItem(storageKey);
  } catch {
    // Ignore storage errors
  }
}

export const submissionService = {
  /**
   * Submit the selected offer to the mock lender using an Idempotency-Key header.
   */
  async submitSelectedOffer(
    applicationId: number | string,
    offerId: number | string,
    idempotencyKey: string
  ): Promise<OfferSubmissionResponse> {
    return apiClient.post<OfferSubmissionResponse>(
      `/applications/${applicationId}/offers/${offerId}/submit`,
      undefined,
      { idempotencyKey }
    );
  },

  /**
   * Retrieve current submission state for an application (read-only).
   * Returns null if no submission has been initiated yet.
   */
  async getSubmissionStatus(
    applicationId: number | string
  ): Promise<OfferSubmissionStatusResponse | null> {
    const res = await apiClient.get<OfferSubmissionStatusResponse | null>(
      `/applications/${applicationId}/submission`
    );
    return res ?? null;
  },

  /**
   * Retrieve mock lender webhook event audit ledger for this application submission.
   */
  async getSubmissionEvents(
    applicationId: number | string
  ): Promise<LenderEventHistoryItem[]> {
    return apiClient.get<LenderEventHistoryItem[]>(
      `/applications/${applicationId}/submission/events`
    );
  },
};
