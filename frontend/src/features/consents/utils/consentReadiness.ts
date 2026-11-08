import { ConsentNotice, ConsentReadiness, ConsentRecord } from '../types';

/**
 * Pure frontend helper to evaluate consent readiness for matching.
 * Checks whether all notices required for matching have an active 'granted'
 * record matching the exact published notice_version.
 */
export function getConsentReadiness(
  notices: ConsentNotice[],
  consentHistory: ConsentRecord[]
): ConsentReadiness {
  const requiredNotices = notices.filter((n) => n.required_for_matching);
  const grantedPurposes: string[] = [];
  const missingPurposes: string[] = [];

  for (const notice of requiredNotices) {
    // Must match exact purpose and exact notice_version, with status 'granted' and no revocation
    const activeConsent = consentHistory.find(
      (c) =>
        c.purpose === notice.purpose &&
        c.notice_version === notice.notice_version &&
        c.status === 'granted' &&
        !c.revoked_at
    );

    if (activeConsent) {
      grantedPurposes.push(notice.purpose);
    } else {
      missingPurposes.push(notice.purpose);
    }
  }

  const isReady = requiredNotices.length > 0 && missingPurposes.length === 0;

  return {
    isReady,
    missingPurposes,
    grantedPurposes,
  };
}
