export type DecisionStatus = 'eligible' | 'ineligible';

export interface LenderDecision {
  id: number;
  lender_code: string;
  lender_name: string;
  policy_version_snapshot: string;
  decision_status: DecisionStatus;
  exclusion_reason_code: string | null;
  exclusion_reason: string | null;
  evaluated_at: string;
}

export interface MatchRun {
  id: number;
  application_id: number;
  run_number: number;
  status: string;
  started_at: string;
  completed_at: string | null;
  decisions: LenderDecision[];
}

export interface MatchRunSummary {
  total_runs: number;
  runs: MatchRun[];
}
