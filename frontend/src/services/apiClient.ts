import { ApiError } from './apiErrors';
import { clearStoredToken, getStoredToken } from './tokenStorage';

export interface RequestOptions extends RequestInit {
  requiresAuth?: boolean;
  idempotencyKey?: string;
}

const DEFAULT_BASE_URL = 'http://localhost:8000/api/v1';

export const getApiBaseUrl = (): string => {
  const envUrl = import.meta.env.VITE_API_BASE_URL;
  if (typeof envUrl === 'string' && envUrl.trim().length > 0) {
    return envUrl.trim().replace(/\/+$/, '');
  }
  return DEFAULT_BASE_URL;
};

export async function apiRequest<T>(
  endpoint: string,
  options: RequestOptions = {}
): Promise<T> {
  const baseUrl = getApiBaseUrl();
  const cleanEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
  const url = `${baseUrl}${cleanEndpoint}`;

  const headers = new Headers(options.headers || {});

  // Add Authorization header if token exists and auth is not explicitly disabled
  if (options.requiresAuth !== false) {
    const token = getStoredToken();
    if (token) {
      headers.set('Authorization', `Bearer ${token}`);
    }
  }

  // Set Idempotency-Key if provided
  if (options.idempotencyKey) {
    headers.set('Idempotency-Key', options.idempotencyKey);
  }

  // Set Content-Type only if request has a body and header is not already set
  if (options.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  // Always expect JSON
  if (!headers.has('Accept')) {
    headers.set('Accept', 'application/json');
  }

  try {
    const response = await fetch(url, {
      ...options,
      headers,
    });

    if (!response.ok) {
      let errorDetail: unknown = null;
      let errorMessage = `HTTP Error ${response.status}: ${response.statusText}`;

      try {
        const errorJson = await response.json();
        if (errorJson && typeof errorJson === 'object') {
          if ('detail' in errorJson) {
            errorDetail = errorJson.detail;
            if (typeof errorJson.detail === 'string') {
              errorMessage = errorJson.detail;
            } else if (Array.isArray(errorJson.detail)) {
              errorMessage = errorJson.detail
                .map((d: { msg?: string; loc?: string[] }) => d.msg || 'Validation error')
                .join(', ');
            }
          } else if ('message' in errorJson && typeof errorJson.message === 'string') {
            errorMessage = errorJson.message;
          }
        }
      } catch {
        // Response was not JSON
        try {
          const text = await response.text();
          if (text) {
            errorMessage = text;
          }
        } catch {
          // Ignore
        }
      }

      // Automatically clear token on confirmed 401 when request was authenticated
      if (response.status === 401 && headers.has('Authorization')) {
        clearStoredToken();
      }

      throw new ApiError(response.status, errorMessage, errorDetail);
    }

    // Handle 204 No Content
    if (response.status === 204) {
      return {} as T;
    }

    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw error;
    }
    // Network or fetch failure
    const networkMessage = error instanceof Error ? error.message : 'Network request failed';
    throw new ApiError(0, `Network failure: ${networkMessage}`);
  }
}

export const apiClient = {
  get<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
    return apiRequest<T>(endpoint, { ...options, method: 'GET' });
  },

  post<T>(endpoint: string, body?: unknown, options: RequestOptions = {}): Promise<T> {
    return apiRequest<T>(endpoint, {
      ...options,
      method: 'POST',
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  },

  patch<T>(endpoint: string, body?: unknown, options: RequestOptions = {}): Promise<T> {
    return apiRequest<T>(endpoint, {
      ...options,
      method: 'PATCH',
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  },

  delete<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
    return apiRequest<T>(endpoint, { ...options, method: 'DELETE' });
  },
};
