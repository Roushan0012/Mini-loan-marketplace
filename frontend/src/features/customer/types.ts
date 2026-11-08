export type WorkType = 'salaried' | 'self_employed' | 'other';

export type LoanApplicationStatus =
  | 'draft'
  | 'matched'
  | 'offer_selected'
  | 'submitted'
  | 'accepted'
  | 'declined'
  | 'timed_out'
  | 'failed';

export interface LoanApplicationCreatePayload {
  age: number;
  monthly_income: string;
  work_type: WorkType;
  requested_amount: string;
}

export interface LoanApplicationUpdatePayload {
  age?: number;
  monthly_income?: string;
  work_type?: WorkType;
  requested_amount?: string;
}

export interface LoanApplication {
  id: number;
  age: number;
  monthly_income: string;
  work_type: WorkType;
  requested_amount: string;
  status: LoanApplicationStatus;
  created_at: string;
  updated_at: string;
}
