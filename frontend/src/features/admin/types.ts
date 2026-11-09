/**
 * Administrator aggregate analytics types.
 * Strictly aggregate telemetry returned by GET /api/v1/admin/dashboard/metrics.
 * Strictly contains zero customer PII, application IDs, or individual loan details.
 */

export interface AdminMetrics {
  total_leads: number;
  total_applications: number;
  total_match_runs: number;
  total_offers: number;
  total_submissions: number;
  applications_by_status: Record<string, number>;
  lender_events_by_processing_status: Record<string, number>;
}

export interface StatusBreakdownItem {
  status: string;
  label: string;
  count: number;
  percentage: number;
}

export interface ApplicationConsistencyResult {
  isConsistent: boolean;
  groupedTotal: number;
  reportedTotal: number;
  difference: number;
}
