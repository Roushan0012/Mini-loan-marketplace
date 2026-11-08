import { apiClient } from '../../../services/apiClient';
import { ConsentGrantPayload, ConsentNotice, ConsentRecord } from '../types';

export const consentService = {
  /**
   * Retrieve published versioned consent notices.
   */
  async getCurrentConsentNotices(): Promise<ConsentNotice[]> {
    return apiClient.get<ConsentNotice[]>('/consents/notices');
  },

  /**
   * Retrieve full chronological consent history for an owned loan application.
   */
  async getApplicationConsentHistory(applicationId: number | string): Promise<ConsentRecord[]> {
    return apiClient.get<ConsentRecord[]>(`/applications/${applicationId}/consents`);
  },

  /**
   * Grant purpose-specific consent for a loan application.
   */
  async grantApplicationConsent(
    applicationId: number | string,
    payload: ConsentGrantPayload
  ): Promise<ConsentRecord> {
    return apiClient.post<ConsentRecord>(`/applications/${applicationId}/consents`, payload);
  },

  /**
   * Revoke an active consent record for a loan application.
   */
  async revokeApplicationConsent(
    applicationId: number | string,
    consentId: number | string
  ): Promise<ConsentRecord> {
    return apiClient.post<ConsentRecord>(
      `/applications/${applicationId}/consents/${consentId}/revoke`
    );
  },
};
