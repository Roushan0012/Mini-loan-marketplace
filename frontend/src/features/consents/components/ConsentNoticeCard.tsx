import React, { useState } from 'react';
import { ConsentNotice, ConsentRecord } from '../types';
import { ConsentStatusBadge } from './ConsentStatusBadge';
import { Button } from '../../../components/ui/Button';

export interface ConsentNoticeCardProps {
  notice: ConsentNotice;
  activeConsent?: ConsentRecord;
  revokedConsent?: ConsentRecord;
  onGrant: (purpose: string, noticeVersion: string) => Promise<void>;
  onRevoke: (consentId: number) => Promise<void>;
  isSubmitting?: boolean;
}

export const ConsentNoticeCard: React.FC<ConsentNoticeCardProps> = ({
  notice,
  activeConsent,
  revokedConsent,
  onGrant,
  onRevoke,
  isSubmitting = false,
}) => {
  const [isChecked, setIsChecked] = useState(false);
  const [showRevokeConfirm, setShowRevokeConfirm] = useState(false);

  const isGranted = Boolean(activeConsent);
  const isRevoked = Boolean(revokedConsent) && !isGranted;

  const handleGrant = async () => {
    if (!isChecked) return;
    await onGrant(notice.purpose, notice.notice_version);
    setIsChecked(false);
  };

  const handleConfirmRevoke = async () => {
    if (!activeConsent) return;
    await onRevoke(activeConsent.id);
    setShowRevokeConfirm(false);
  };

  return (
    <div
      className="card"
      style={{
        border: isGranted ? '1px solid #86efac' : '1px solid var(--color-border)',
        backgroundColor: isGranted ? '#f0fdf4' : '#ffffff',
        marginBottom: '1rem',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '0.75rem', marginBottom: '0.75rem' }}>
        <div>
          <h3 style={{ fontSize: '1.125rem', fontWeight: 600 }}>{notice.title}</h3>
          <div style={{ fontSize: '0.8125rem', color: 'var(--color-text-muted)', marginTop: '0.125rem' }}>
            <span>Purpose: <code>{notice.purpose}</code></span> &bull; <span>Version: <strong>{notice.notice_version}</strong></span>
            {notice.required_for_matching && (
              <span style={{ marginLeft: '0.5rem', color: '#b45309', fontWeight: 600 }}>
                (Required for Matching)
              </span>
            )}
          </div>
        </div>
        <div>
          {isGranted ? (
            <ConsentStatusBadge status="granted" />
          ) : isRevoked ? (
            <ConsentStatusBadge status="revoked" />
          ) : (
            <ConsentStatusBadge status="not_granted" />
          )}
        </div>
      </div>

      {/* Notice Text Content */}
      <div
        style={{
          padding: '0.875rem',
          backgroundColor: '#ffffff',
          border: '1px solid var(--color-border)',
          borderRadius: 'var(--radius-sm)',
          fontSize: '0.875rem',
          lineHeight: '1.45',
          marginBottom: '1rem',
          color: 'var(--color-text-main)',
        }}
      >
        <p style={{ whiteSpace: 'pre-wrap' }}>{notice.notice_text}</p>
      </div>

      {/* Action / State Area */}
      {isGranted ? (
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.75rem' }}>
          <div style={{ fontSize: '0.8125rem', color: 'var(--color-success)' }}>
            ✓ Consent active &bull; Granted on{' '}
            {activeConsent?.granted_at ? new Date(activeConsent.granted_at).toLocaleString() : 'N/A'}
          </div>

          {!showRevokeConfirm ? (
            <button
              type="button"
              className="btn btn-outline"
              style={{ color: 'var(--color-danger)', borderColor: '#fca5a5', padding: '0.35rem 0.75rem', fontSize: '0.8125rem' }}
              onClick={() => setShowRevokeConfirm(true)}
              disabled={isSubmitting}
            >
              Revoke Consent
            </button>
          ) : (
            <div
              className="alert alert-warning"
              style={{ width: '100%', marginTop: '0.5rem', fontSize: '0.8125rem' }}
            >
              <p style={{ fontWeight: 600, marginBottom: '0.5rem' }}>
                ⚠️ Are you sure you want to revoke this consent?
              </p>
              <p style={{ marginBottom: '0.75rem' }}>
                Revoking required matching consent will prevent future loan matching until a newly published notice version is granted. Previously revoked versions cannot be re-granted.
              </p>
              <div style={{ display: 'flex', gap: '0.5rem' }}>
                <Button
                  variant="danger"
                  onClick={handleConfirmRevoke}
                  isLoading={isSubmitting}
                  style={{ padding: '0.3rem 0.75rem', fontSize: '0.8125rem' }}
                >
                  Confirm Revocation
                </Button>
                <button
                  type="button"
                  className="btn btn-outline"
                  onClick={() => setShowRevokeConfirm(false)}
                  disabled={isSubmitting}
                  style={{ padding: '0.3rem 0.75rem', fontSize: '0.8125rem' }}
                >
                  Cancel
                </button>
              </div>
            </div>
          )}
        </div>
      ) : isRevoked ? (
        <div className="alert alert-danger" style={{ fontSize: '0.8125rem', margin: 0 }}>
          <p style={{ fontWeight: 600 }}>Consent Revoked for this Version</p>
          <p style={{ marginTop: '0.25rem' }}>
            You revoked consent for notice version <code>{notice.notice_version}</code> on{' '}
            {revokedConsent?.revoked_at ? new Date(revokedConsent.revoked_at).toLocaleString() : 'earlier date'}.
            In accordance with system policy, a newly published notice version is required before this consent can be granted again.
          </p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          <label style={{ display: 'flex', alignItems: 'flex-start', gap: '0.5rem', cursor: 'pointer', fontSize: '0.875rem' }}>
            <input
              type="checkbox"
              id={`accept-consent-${notice.purpose}`}
              checked={isChecked}
              onChange={(e) => setIsChecked(e.target.checked)}
              disabled={isSubmitting}
              style={{ marginTop: '0.2rem' }}
            />
            <span>
              I have read, understood, and accept the terms of the <strong>{notice.title}</strong> (Version {notice.notice_version}).
            </span>
          </label>

          <div>
            <Button
              type="button"
              variant="primary"
              onClick={handleGrant}
              disabled={!isChecked || isSubmitting}
              isLoading={isSubmitting}
              style={{ fontSize: '0.8125rem', padding: '0.45rem 1rem' }}
            >
              Grant Consent
            </Button>
          </div>
        </div>
      )}
    </div>
  );
};
