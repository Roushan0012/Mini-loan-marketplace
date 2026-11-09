import React, { useEffect, useState } from 'react';
import { MockKFSResponse } from '../types';
import { offerService } from '../services/offerService';
import { formatRupees, formatApr } from '../utils/formatMoney';
import { LoadingSpinner } from '../../../components/feedback/LoadingSpinner';
import { ErrorMessage } from '../../../components/feedback/ErrorMessage';
import { ApiError } from '../../../services/apiErrors';

export interface MockKFSDialogProps {
  applicationId: number;
  offerId: number | null;
  isOpen: boolean;
  onClose: () => void;
}

export const MockKFSDialog: React.FC<MockKFSDialogProps> = ({
  applicationId,
  offerId,
  isOpen,
  onClose,
}) => {
  const [kfs, setKfs] = useState<MockKFSResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen || offerId === null) {
      setKfs(null);
      setError(null);
      return;
    }

    let isMounted = true;
    const fetchKFS = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const data = await offerService.getMockKFS(applicationId, offerId);
        if (isMounted) {
          setKfs(data);
        }
      } catch (err) {
        if (isMounted) {
          if (err instanceof ApiError) {
            setError(err.getFormattedMessage());
          } else {
            setError('Failed to load Key Facts Statement. Please check your connection.');
          }
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    };

    fetchKFS();

    return () => {
      isMounted = false;
    };
  }, [applicationId, offerId, isOpen]);

  // Handle keyboard Escape
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) {
    return null;
  }

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
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="mock-kfs-title"
        className="card"
        style={{
          width: '100%',
          maxWidth: '750px',
          maxHeight: '90vh',
          overflowY: 'auto',
          backgroundColor: '#ffffff',
          boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.2)',
          padding: '1.75rem',
        }}
      >
        {/* Header */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'flex-start',
            borderBottom: '1px solid var(--color-border)',
            paddingBottom: '1rem',
            marginBottom: '1rem',
          }}
        >
          <div>
            <span
              className="badge badge-status"
              style={{ fontSize: '0.75rem', marginBottom: '0.35rem', display: 'inline-block' }}
            >
              SIMULATED DISCLOSURE
            </span>
            <h2 id="mock-kfs-title" style={{ fontSize: '1.35rem', fontWeight: 700, margin: 0 }}>
              Mock Key Facts Statement (KFS)
            </h2>
            <div style={{ fontSize: '0.8125rem', color: 'var(--color-text-muted)', marginTop: '0.25rem' }}>
              Reference: <code>{kfs?.mock_kfs_reference || 'Loading...'}</code>
            </div>
          </div>

          <button
            type="button"
            className="btn btn-outline"
            style={{ padding: '0.35rem 0.75rem', fontSize: '0.875rem' }}
            onClick={onClose}
            aria-label="Close dialog"
          >
            ✕ Close
          </button>
        </div>

        {/* Content */}
        {isLoading ? (
          <LoadingSpinner message="Retrieving Key Facts Statement..." />
        ) : error ? (
          <div style={{ padding: '1rem 0' }}>
            <ErrorMessage message={error} />
            <div style={{ textAlign: 'center', marginTop: '1rem' }}>
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => {
                  if (offerId !== null) {
                    setIsLoading(true);
                    offerService
                      .getMockKFS(applicationId, offerId)
                      .then(setKfs)
                      .catch((e) => setError(e.message))
                      .finally(() => setIsLoading(false));
                  }
                }}
              >
                Retry
              </button>
            </div>
          </div>
        ) : kfs ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
            {/* Prominent Training Disclosure */}
            <div
              className="alert alert-warning"
              style={{ fontSize: '0.8125rem', lineHeight: '1.4' }}
            >
              <strong>⚠️ Simulated Training Disclosure:</strong>
              <p style={{ margin: '0.25rem 0 0 0' }}>
                This is a fictional software-training document only. It is not an actual credit offer,
                loan agreement, legal disclosure, or regulatory Key Facts Statement.
              </p>
            </div>

            {/* Document & Lender Meta */}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                gap: '1rem',
                backgroundColor: 'var(--color-bg-alt, #f8fafc)',
                padding: '1rem',
                borderRadius: 'var(--radius-sm)',
              }}
            >
              <div>
                <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>Lender</span>
                <div style={{ fontWeight: 600 }}>{kfs.lender_name}</div>
                <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>
                  Code: <code>{kfs.lender_code}</code> &bull; Policy: {kfs.policy_version}
                </div>
              </div>

              <div>
                <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>Document Details</span>
                <div style={{ fontWeight: 500, fontSize: '0.875rem' }}>{kfs.document_type}</div>
                <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>
                  Version: {kfs.document_version}
                </div>
              </div>

              <div>
                <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>Offer Status</span>
                <div>
                  <span className="badge badge-accepted" style={{ textTransform: 'uppercase' }}>
                    {kfs.offer_status}
                  </span>
                </div>
                {kfs.valid_until && (
                  <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', marginTop: '0.2rem' }}>
                    Valid until: {new Date(kfs.valid_until).toLocaleDateString()}
                  </div>
                )}
              </div>
            </div>

            {/* Financial Terms Table */}
            <div>
              <h4 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '0.75rem' }}>
                Financial Terms & Repayment Schedule
              </h4>
              <div className="table-responsive">
                <table className="data-table" aria-label="KFS Financial Terms">
                  <tbody>
                    <tr>
                      <td style={{ fontWeight: 500 }}>Loan Principal Amount</td>
                      <td style={{ fontWeight: 700, color: 'var(--color-primary)' }}>
                        {formatRupees(kfs.loan_amount)}
                      </td>
                    </tr>
                    <tr>
                      <td style={{ fontWeight: 500 }}>Nominal Annual Percentage Rate (APR)</td>
                      <td style={{ fontWeight: 600 }}>{formatApr(kfs.nominal_annual_apr_percent)}</td>
                    </tr>
                    <tr>
                      <td style={{ fontWeight: 500 }}>Loan Tenure</td>
                      <td>{kfs.term_months} Months ({kfs.number_of_installments} Installments)</td>
                    </tr>
                    <tr>
                      <td style={{ fontWeight: 500 }}>Payment Frequency</td>
                      <td>{kfs.payment_frequency}</td>
                    </tr>
                    <tr>
                      <td style={{ fontWeight: 500 }}>Equated Monthly Installment (EMI)</td>
                      <td style={{ fontWeight: 700 }}>{formatRupees(kfs.monthly_installment)}</td>
                    </tr>
                    <tr>
                      <td style={{ fontWeight: 500 }}>Estimated Total Interest</td>
                      <td>{formatRupees(kfs.estimated_total_interest)}</td>
                    </tr>
                    <tr>
                      <td style={{ fontWeight: 500 }}>Estimated Total Repayment</td>
                      <td style={{ fontWeight: 700 }}>{formatRupees(kfs.estimated_total_repayment)}</td>
                    </tr>
                    <tr>
                      <td style={{ fontWeight: 500 }}>Amortization Method</td>
                      <td style={{ fontSize: '0.8125rem' }}>{kfs.amortization_method}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            {/* Disclosures */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              <h4 style={{ fontSize: '0.9375rem', fontWeight: 600, margin: 0 }}>
                Disclosures & Explanatory Notes
              </h4>
              <div style={{ fontSize: '0.8125rem', color: 'var(--color-text-muted)', lineHeight: '1.45' }}>
                <p style={{ margin: '0 0 0.5rem 0' }}>
                  <strong>Fees:</strong> {kfs.fee_disclosure}
                </p>
                <p style={{ margin: '0 0 0.5rem 0' }}>
                  <strong>Calculation:</strong> {kfs.calculation_disclosure}
                </p>
                <p style={{ margin: 0 }}>
                  <strong>Training Policy:</strong> {kfs.training_disclosure}
                </p>
              </div>
            </div>

            {/* Footer action */}
            <div style={{ display: 'flex', justifyContent: 'flex-end', paddingTop: '0.5rem' }}>
              <button type="button" className="btn btn-outline" onClick={onClose}>
                Close
              </button>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
};
