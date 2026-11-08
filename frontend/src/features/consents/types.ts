export type ConsentPurpose = 'eligibility_matching' | 'sharing_with_mock_lenders' | string;

export type ConsentStatus = 'pending' | 'granted' | 'revoked';

export interface ConsentNotice {
  purpose: string;
  title: string;
  notice_version: string;
  notice_text: string;
  required_for_matching: boolean;
}

export interface ConsentGrantPayload {
  purpose: string;
  notice_version: string;
  accepted: boolean;
}

export interface ConsentRecord {
  id: number;
  application_id: number;
  purpose: string;
  notice_version: string;
  status: ConsentStatus;
  granted_at: string | null;
  revoked_at: string | null;
  created_at: string;
}

export interface ConsentReadiness {
  isReady: boolean;
  missingPurposes: string[];
  grantedPurposes: string[];
}
