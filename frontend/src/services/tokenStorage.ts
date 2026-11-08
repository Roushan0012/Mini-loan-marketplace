/**
 * Session storage token management.
 * Note: Storing tokens in sessionStorage is a local educational training tradeoff.
 * While it prevents persistence across browser tabs and sessions, it remains accessible
 * to JavaScript in the page. In production, HttpOnly secure cookies are recommended.
 */

const TOKEN_KEY = 'mini_loan_marketplace_token';

export const getStoredToken = (): string | null => {
  try {
    return sessionStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
};

export const setStoredToken = (token: string): void => {
  try {
    sessionStorage.setItem(TOKEN_KEY, token);
  } catch {
    // Fallback if sessionStorage is inaccessible
  }
};

export const clearStoredToken = (): void => {
  try {
    sessionStorage.removeItem(TOKEN_KEY);
  } catch {
    // Fallback
  }
};
