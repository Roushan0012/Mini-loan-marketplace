import { apiClient } from '../../../services/apiClient';
import {
  LoanApplication,
  LoanApplicationCreatePayload,
  LoanApplicationUpdatePayload,
} from '../types';

export const applicationService = {
  /**
   * Retrieve all loan applications owned by the authenticated customer.
   */
  async listApplications(): Promise<LoanApplication[]> {
    return apiClient.get<LoanApplication[]>('/applications');
  },

  /**
   * Retrieve a specific loan application by ID.
   */
  async getApplication(applicationId: number | string): Promise<LoanApplication> {
    return apiClient.get<LoanApplication>(`/applications/${applicationId}`);
  },

  /**
   * Create a new draft loan application for the authenticated customer.
   * Customer ID is automatically derived by the backend from the Bearer token.
   */
  async createApplication(payload: LoanApplicationCreatePayload): Promise<LoanApplication> {
    return apiClient.post<LoanApplication>('/applications', payload);
  },

  /**
   * Partially update a draft loan application.
   * Only draft applications can be updated.
   */
  async updateApplication(
    applicationId: number | string,
    payload: LoanApplicationUpdatePayload
  ): Promise<LoanApplication> {
    return apiClient.patch<LoanApplication>(`/applications/${applicationId}`, payload);
  },
};
