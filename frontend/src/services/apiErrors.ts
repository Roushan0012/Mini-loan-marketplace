export interface ApiErrorDetail {
  loc?: (string | number)[];
  msg?: string;
  type?: string;
}

export class ApiError extends Error {
  public readonly status: number;
  public readonly detail?: unknown;

  constructor(status: number, message: string, detail?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
    Object.setPrototypeOf(this, ApiError.prototype);
  }

  /**
   * Helper to format detailed error messages, especially for FastAPI 422 validation errors.
   */
  public getFormattedMessage(): string {
    if (this.detail && Array.isArray(this.detail)) {
      const messages = (this.detail as ApiErrorDetail[]).map((err) => {
        const field = err.loc && err.loc.length > 0 ? String(err.loc[err.loc.length - 1]) : '';
        const msg = err.msg || 'Invalid input';
        return field ? `${field}: ${msg}` : msg;
      });
      return messages.join(', ');
    }
    if (
      this.detail &&
      typeof this.detail === 'object' &&
      'message' in this.detail &&
      typeof (this.detail as { message: unknown }).message === 'string'
    ) {
      return (this.detail as { message: string }).message;
    }
    if (typeof this.detail === 'string' && this.detail.trim().length > 0) {
      return this.detail;
    }
    return this.message || `Request failed with status ${this.status}`;
  }
}
