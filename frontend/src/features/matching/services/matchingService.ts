import { apiClient } from '../../../services/apiClient';
import { MatchRun, MatchRunSummary } from '../types';

export const matchingService = {
  /**
   * Run deterministic multi-lender eligibility matching for an owned loan application.
   */
  async runMatching(applicationId: number | string): Promise<MatchRun> {
    return apiClient.post<MatchRun>(`/applications/${applicationId}/match`);
  },

  /**
   * Retrieve chronological matching history and lender decisions for an owned loan application.
   */
  async getMatchHistory(applicationId: number | string): Promise<MatchRunSummary> {
    return apiClient.get<MatchRunSummary>(`/applications/${applicationId}/matches`);
  },
};
