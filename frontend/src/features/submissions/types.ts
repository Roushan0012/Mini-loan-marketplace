export type SubmissionStatus =
  | 'pending'
  | 'submitted'
  | 'accepted'
  | 'declined'
  | 'timed_out'
  | 'failed';

export interface OfferSubmissionResponse {
  id: number;
  application_id: number;
  offer_id: number;
  lender_code: string;
  lender_name: string;
  policy_version: string;
  status: SubmissionStatus;
  mock_reference: string | null;
  submitted_at: string;
  created_at: string;
  updated_at: string;
  submission_result: 'created' | 'replayed';
}

export interface OfferSubmissionStatusResponse {
  id: number;
  application_id: number;
  offer_id: number;
  lender_code: string;
  lender_name: string;
  policy_version: string;
  status: SubmissionStatus;
  mock_reference: string | null;
  submitted_at: string;
  created_at: string;
  updated_at: string;
}

export interface LenderEventHistoryItem {
  id: number;
  event_id: string;
  event_type: string;
  sequence_number: number | null;
  processing_status: string;
  occurred_at: string;
  received_at: string;
  event_payload: Record<string, unknown>;
}
