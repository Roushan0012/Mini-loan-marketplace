export * from '../features/customer/types';
export * from '../features/consents/types';
export * from '../features/matching/types';
export * from '../features/offers/types';
export * from '../features/submissions/types';

export interface CallerLead {
  id: number;
  synthetic_reference: string;
  applicant_name: string;
  age: number;
  monthly_income: string;
  work_type: string;
  requested_amount: string;
  status: string;
  assigned_at: string;
}

export interface AdminMetrics {
  total_leads: number;
  total_applications: number;
  total_match_runs: number;
  total_offers: number;
  total_submissions: number;
  applications_by_status: Record<string, number>;
  lender_events_by_processing_status: Record<string, number>;
}
