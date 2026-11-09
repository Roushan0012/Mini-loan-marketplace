/**
 * Caller lead representation returned by GET /api/v1/caller/leads.
 * Strictly read-only representation of mock leads assigned to the authenticated caller.
 */
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

export interface CallerWorkspaceFilters {
  searchTerm: string;
  statusFilter: string;
  workTypeFilter: string;
}
