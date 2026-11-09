import React, { useState } from 'react';
import { OfferResponse, OfferSelectionResponse } from '../types';
import { offerService } from '../services/offerService';
import { formatRupees, formatApr } from '../utils/formatMoney';
import { Button } from '../../../components/ui/Button';
import { ErrorMessage } from '../../../components/feedback/ErrorMessage';
import { ApiError } from '../../../services/apiErrors';

export interface OfferSelectionPanelProps {
  applicationId: number;
  pendingOffer: OfferResponse | null;
  isOpen: boolean;
  onCancel: () => void;
  onSuccess: (result: OfferSelectionResponse) => void;
}

export const OfferSelectionPanel: React.FC<OfferSelectionPanelProps> = ({
  applicationId,
  pendingOffer,
  isOpen,
  onCancel,
  onSuccess,
}) => {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen || !pendingOffer) {
    return null;
  }

  const handleConfirmSelect = async () => {
    setIsSubmitting(true);
    setError(null);

    try {
      const result = await offerService.selectOffer(applicationId, pendingOffer.id);
      onSuccess(result);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.getFormattedMessage());
      } else {
        setError('Failed to select offer. Please check your network connection.');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div
      className="modal-backdrop"
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: 'rgba(15, 23, 42, 0.6)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1000,
        padding: '1rem',
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget && !isSubmitting) onCancel();
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="confirm-selection-title"
        className="card"
        style={{
          width: '100%',
          maxWidth: '520px',
          backgroundColor: '#ffffff',
          boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.2)',
          padding: '1.75rem',
        }}
      >
        <h3 id="confirm-selection-title" style={{ fontSize: '1.25rem', fontWeight: 700, margin: '0 0 0.75rem 0' }}>
          Confirm Loan Offer Selection
        </h3>

        {error && (
          <div style={{ marginBottom: '1rem' }}>
            <ErrorMessage message={error} />
          </div>
        )}

        <div
          style={{
            padding: '1rem',
            backgroundColor: 'var(--color-bg-alt, #f8fafc)',
            border: '1px solid var(--color-border)',
            borderRadius: 'var(--radius-sm)',
            marginBottom: '1rem',
          }}
        >
          <div style={{ fontSize: '1.1rem', fontWeight: 600 }}>{pendingOffer.lender_name}</div>
          <div style={{ fontSize: '0.8125rem', color: 'var(--color-text-muted)' }}>
            Code: <code>{pendingOffer.lender_code}</code> &bull; Policy: {pendingOffer.policy_version}
          </div>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: '1fr 1fr',
              gap: '0.5rem',
              marginTop: '0.75rem',
              paddingTop: '0.75rem',
              borderTop: '1px solid var(--color-border)',
              fontSize: '0.875rem',
            }}
          >
            <div>
              <span style={{ color: 'var(--color-text-muted)', fontSize: '0.75rem' }}>Amount:</span>
              <div style={{ fontWeight: 600 }}>{formatRupees(pendingOffer.loan_amount)}</div>
            </div>
            <div>
              <span style={{ color: 'var(--color-text-muted)', fontSize: '0.75rem' }}>APR:</span>
              <div style={{ fontWeight: 600 }}>{formatApr(pendingOffer.apr)}</div>
            </div>
            <div>
              <span style={{ color: 'var(--color-text-muted)', fontSize: '0.75rem' }}>Tenure:</span>
              <div>{pendingOffer.term_months} Months</div>
            </div>
            <div>
              <span style={{ color: 'var(--color-text-muted)', fontSize: '0.75rem' }}>EMI:</span>
              <div>{formatRupees(pendingOffer.monthly_installment)}/mo</div>
            </div>
          </div>
        </div>

        {/* Explicit Disclosure Notices */}
        <div className="alert alert-info" style={{ fontSize: '0.8125rem', marginBottom: '1.25rem' }}>
          <p style={{ margin: '0 0 0.5rem 0', fontWeight: 600 }}>Important Conditions:</p>
          <ul style={{ margin: 0, paddingLeft: '1.25rem', lineHeight: '1.4' }}>
            <li>You can select exactly <strong>one</strong> offer for this application.</li>
            <li>Selecting this offer will automatically <strong>withdraw all other competing offers</strong>.</li>
            <li>Offer selection <strong>does not constitute final lender approval</strong>.</li>
            <li>Selection prepares the application for final submission in the next step.</li>
          </ul>
        </div>

        {/* Actions */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
          <button
            type="button"
            className="btn btn-outline"
            onClick={onCancel}
            disabled={isSubmitting}
          >
            Cancel
          </button>
          <Button
            type="button"
            variant="primary"
            onClick={handleConfirmSelect}
            isLoading={isSubmitting}
            disabled={isSubmitting}
          >
            Confirm Selection
          </Button>
        </div>
      </div>
    </div>
  );
};
