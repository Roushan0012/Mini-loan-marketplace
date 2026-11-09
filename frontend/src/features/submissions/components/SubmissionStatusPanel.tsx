import React, { useState } from 'react';
import { LoanApplicationStatus } from '../../customer/types';
import { OfferResponse } from '../../offers/types';
import {
  LenderEventHistoryItem,
  OfferSubmissionResponse,
  OfferSubmissionStatusResponse,
} from '../types';
import {
  clearSubmissionKey,
  getOrCreateSubmissionKey,
  submissionService,
} from '../services/submissionService';
import { LenderEventTimeline } from './LenderEventTimeline';
import { Button } from '../../../components/ui/Button';
import { ErrorMessage } from '../../../components/feedback/ErrorMessage';
import { ApiError } from '../../../services/apiErrors';

export interface SubmissionStatusPanelProps {
  applicationId: number;
  applicationStatus: LoanApplicationStatus;
  selectedOffer: OfferResponse | null;
  submission: OfferSubmissionStatusResponse | null;
  events: LenderEventHistoryItem[];
  onSubmissionComplete: (submission: OfferSubmissionResponse) => void;
  onRefresh: () => void;
  isRefreshing?: boolean;
}

export const SubmissionStatusPanel: React.FC<SubmissionStatusPanelProps> = ({
  applicationId,
  applicationStatus,
  selectedOffer,
  submission,
  events,
  onSubmissionComplete,
  onRefresh,
  isRefreshing = false,
}) => {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canSubmit = applicationStatus === 'offer_selected' && selectedOffer && !submission;

  const handleSubmit = async () => {
    if (!canSubmit || !selectedOffer) return;

    setIsSubmitting(true);
    setError(null);

    // Retrieve or create idempotent key securely from sessionStorage
    const idempotencyKey = getOrCreateSubmissionKey(applicationId);

    try {
      const result = await submissionService.submitSelectedOffer(
        applicationId,
        selectedOffer.id,
        idempotencyKey
      );

      // Clear pending key upon confirmed authoritative success
      clearSubmissionKey(applicationId);
      onSubmissionComplete(result);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.getFormattedMessage());
      } else {
        setError('Submission attempt failed. You may retry using the preserved submission key.');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'accepted':
        return <span className="badge badge-accepted">ACCEPTED (MOCK)</span>;
      case 'declined':
        return <span className="badge badge-declined">DECLINED (MOCK)</span>;
      case 'timed_out':
        return <span className="badge badge-submitted" style={{ backgroundColor: '#fef3c7', color: '#b45309' }}>TIMED OUT</span>;
      case 'failed':
        return <span className="badge badge-declined">FAILED</span>;
      case 'submitted':
        return <span className="badge badge-submitted">SUBMITTED (DISPATCHED)</span>;
      case 'pending':
      default:
        return <span className="badge badge-status">PENDING</span>;
    }
  };

  return (
    <div className="card" style={{ marginBottom: '1.5rem' }}>
      {/* Header */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '0.75rem',
          marginBottom: '1rem',
        }}
      >
        <div>
          <h3 style={{ fontSize: '1.25rem', fontWeight: 600, margin: 0 }}>
            Mock Lender Submission & Outcome Tracking
          </h3>
          <p style={{ fontSize: '0.8125rem', color: 'var(--color-text-muted)', margin: '0.25rem 0 0 0' }}>
            Idempotent dispatch of your selected terms to the simulated lending partner and webhook lifecycle tracking.
          </p>
        </div>

        {submission && (
          <button
            type="button"
            className="btn btn-outline"
            style={{ fontSize: '0.8125rem', padding: '0.35rem 0.75rem' }}
            onClick={onRefresh}
            disabled={isRefreshing}
          >
            {isRefreshing ? 'Refreshing...' : '↻ Refresh Status'}
          </button>
        )}
      </div>

      {error && (
        <div style={{ marginBottom: '1rem' }}>
          <ErrorMessage message={error} />
        </div>
      )}

      {/* Case 1: Can Submit Selected Offer */}
      {canSubmit && (
        <div
          style={{
            padding: '1.25rem',
            backgroundColor: 'var(--color-bg-alt, #f8fafc)',
            border: '1px solid var(--color-border)',
            borderRadius: 'var(--radius-sm)',
          }}
        >
          <div style={{ marginBottom: '1rem' }}>
            <h4 style={{ margin: '0 0 0.35rem 0', fontSize: '1rem', fontWeight: 600 }}>
              Ready for Simulated Lender Submission
            </h4>
            <p style={{ margin: 0, fontSize: '0.875rem', color: 'var(--color-text-muted)', lineHeight: '1.4' }}>
              You have selected the offer from <strong>{selectedOffer.lender_name}</strong>. Clicking Submit below will dispatch this application using an idempotent client key to prevent duplicate processing.
            </p>
          </div>

          <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center', flexWrap: 'wrap' }}>
            <Button
              type="button"
              variant="primary"
              onClick={handleSubmit}
              isLoading={isSubmitting}
              disabled={isSubmitting}
            >
              Submit to Mock Lender
            </Button>
            <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>
              Protected by unique idempotent submission key.
            </span>
          </div>
        </div>
      )}

      {/* Case 2: Submission Exists */}
      {submission && (
        <div>
          {/* Status Meta Box */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
              gap: '1rem',
              padding: '1.25rem',
              backgroundColor: 'var(--color-bg-alt, #f8fafc)',
              border: '1px solid var(--color-border)',
              borderRadius: 'var(--radius-sm)',
              marginBottom: '1rem',
            }}
          >
            <div>
              <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>Target Mock Lender</span>
              <div style={{ fontWeight: 600, fontSize: '1rem' }}>{submission.lender_name}</div>
              <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>
                Code: <code>{submission.lender_code}</code> &bull; Snapshot: {submission.policy_version}
              </div>
            </div>

            <div>
              <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>Lifecycle Status</span>
              <div style={{ marginTop: '0.2rem' }}>{getStatusBadge(submission.status)}</div>
              <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', marginTop: '0.2rem' }}>
                Ref: <code>{submission.mock_reference || 'Pending'}</code>
              </div>
            </div>

            <div>
              <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>Timestamps</span>
              <div style={{ fontSize: '0.8125rem' }}>
                Submitted: {new Date(submission.submitted_at).toLocaleString()}
              </div>
              <div style={{ fontSize: '0.8125rem', color: 'var(--color-text-muted)', marginTop: '0.2rem' }}>
                Updated: {new Date(submission.updated_at).toLocaleString()}
              </div>
            </div>
          </div>

          {/* Simulated Terminal Outcome Explanations */}
          {submission.status === 'accepted' && (
            <div className="alert alert-success" style={{ fontSize: '0.875rem', marginBottom: '1rem' }}>
              <strong>🎉 Simulated Offer Accepted:</strong> The mock lender has approved the loan under the agreed terms.
              <p style={{ margin: '0.25rem 0 0 0', fontSize: '0.8125rem' }}>
                Note: This is a fictional simulation for training purposes only. No actual funds will be disbursed.
              </p>
            </div>
          )}

          {submission.status === 'declined' && (
            <div className="alert alert-danger" style={{ fontSize: '0.875rem', marginBottom: '1rem' }}>
              <strong>✕ Simulated Offer Declined:</strong> The mock lender underwriting system rejected the final application.
              <p style={{ margin: '0.25rem 0 0 0', fontSize: '0.8125rem' }}>
                Simulated training outcome. See the event ledger below for recorded webhook reason codes.
              </p>
            </div>
          )}

          {submission.status === 'timed_out' && (
            <div className="alert alert-warning" style={{ fontSize: '0.875rem', marginBottom: '1rem' }}>
              <strong>⏳ Simulated Partner Timeout:</strong> The mock lender did not return an outcome within the expected window.
            </div>
          )}

          {submission.status === 'failed' && (
            <div className="alert alert-danger" style={{ fontSize: '0.875rem', marginBottom: '1rem' }}>
              <strong>⚠️ Simulated Processing Failure:</strong> The mock lender encountered an unrecoverable simulated processing error.
            </div>
          )}

          {submission.status === 'submitted' && (
            <div className="alert alert-info" style={{ fontSize: '0.875rem', marginBottom: '1rem' }}>
              <strong>📨 Dispatched to Partner:</strong> Your offer has been submitted to {submission.lender_name}. Asynchronous webhook outcome events will appear below as they are processed.
            </div>
          )}

          {/* Event Ledger */}
          <LenderEventTimeline
            events={events}
            onRefresh={onRefresh}
            isRefreshing={isRefreshing}
          />
        </div>
      )}

      {/* Case 3: Earlier state (draft or matched without selection) */}
      {!canSubmit && !submission && (
        <div style={{ color: 'var(--color-text-muted)', fontSize: '0.875rem', padding: '1rem 0' }}>
          Select an available mock loan offer above to unlock partner submission.
        </div>
      )}
    </div>
  );
};
