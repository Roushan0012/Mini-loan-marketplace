export type OfferStatus = 'available' | 'selected' | 'expired' | 'withdrawn';

export interface OfferResponse {
  id: number;
  lender_decision_id: number;
  lender_code: string;
  lender_name: string;
  policy_version: string;
  loan_amount: string;
  apr: string;
  term_months: number;
  monthly_installment: string;
  mock_kfs_reference: string;
  status: OfferStatus;
  created_at: string;
  valid_until: string | null;
}

export interface OfferGenerationResponse {
  application_id: number;
  match_run_id: number | null;
  run_number: number | null;
  generated_count: number;
  offers: OfferResponse[];
}

export interface MockKFSResponse {
  document_type: string;
  document_version: string;
  mock_kfs_reference: string;
  offer_id: number;
  application_id: number;
  lender_code: string;
  lender_name: string;
  policy_version: string;
  offer_status: string;
  offer_created_at: string;
  valid_until: string | null;
  loan_amount: string;
  nominal_annual_apr_percent: string;
  term_months: number;
  number_of_installments: number;
  payment_frequency: string;
  monthly_installment: string;
  estimated_total_repayment: string;
  estimated_total_interest: string;
  amortization_method: string;
  fee_disclosure: string;
  calculation_disclosure: string;
  training_disclosure: string;
}

export interface OfferSelectionResponse {
  application_id: number;
  application_status: 'offer_selected';
  selected_offer: OfferResponse;
  withdrawn_offer_count: number;
  selection_result: 'selected' | 'already_selected';
}
