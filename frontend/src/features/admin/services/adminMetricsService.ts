import { apiClient } from '../../../services/apiClient';
import { AdminMetrics } from '../types';

export const adminMetricsService = {
  /**
   * Retrieve aggregate platform monitoring metrics.
   * Scoped and authorized via admin role Bearer JWT token.
   * Never transmits admin_id, customer_id, or caller_id parameters.
   */
  async getAdminMetrics(): Promise<AdminMetrics> {
    return apiClient.get<AdminMetrics>('/admin/dashboard/metrics');
  },
};
