export interface LoanApplication {
  id: number;
  age: number;
  monthly_income: string;
  work_type: string;
  requested_amount: string;
  status: string;
  created_at: string;
  updated_at: string;
}

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
