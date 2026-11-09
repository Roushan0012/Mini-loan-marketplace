import { apiClient } from '../../../services/apiClient';
import { CallerLead } from '../types';

export const callerLeadService = {
  /**
   * Retrieve leads assigned exclusively to the authenticated caller.
   * Scoped to caller identity via backend JWT token.
   *
   * @param limit Number of records per page (default 25)
   * @param offset Number of records to skip (default 0)
   */
  async getAssignedLeads(limit: number = 25, offset: number = 0): Promise<CallerLead[]> {
    return apiClient.get<CallerLead[]>(`/caller/leads?limit=${limit}&offset=${offset}`);
  },
};
