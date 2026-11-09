import React from 'react';
import { OfferResponse } from '../types';
import { formatRupees, formatApr } from '../utils/formatMoney';
import { Button } from '../../../components/ui/Button';

export interface OfferCardProps {
  offer: OfferResponse;
  canSelect: boolean;
  isSelecting: boolean;
  onSelect: (offer: OfferResponse) => void;
  onViewKFS: (offerId: number) => void;
}

export const OfferCard: React.FC<OfferCardProps> = ({
  offer,
  canSelect,
  isSelecting,
  onSelect,
  onViewKFS,
}) => {
  const isSelected = offer.status === 'selected';
  const isWithdrawn = offer.status === 'withdrawn';
  const isExpired = offer.status === 'expired';
  const isAvailable = offer.status === 'available';

  const borderColor = isSelected
    ? 'var(--color-primary)'
    : isWithdrawn
    ? '#e2e8f0'
    : isExpired
    ? '#fca5a5'
    : 'var(--color-border)';

  const bgColor = isSelected
    ? '#eff6ff'
    : isWithdrawn
    ? '#f8fafc'
    : '#ffffff';

  return (
    <div
      className="card"
      style={{
        border: `2px solid ${borderColor}`,
        backgroundColor: bgColor,
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        opacity: isWithdrawn ? 0.75 : 1,
        transition: 'all 0.2s ease',
      }}
    >
      <div>
        {/* Header */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'flex-start',
            gap: '0.5rem',
            marginBottom: '0.75rem',
          }}
        >
          <div>
            <h4 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 600 }}>
              {offer.lender_name}
            </h4>
            <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', marginTop: '0.15rem' }}>
              Code: <code>{offer.lender_code}</code> &bull; Policy: {offer.policy_version}
            </div>
          </div>

          <div>
            {isSelected ? (
              <span className="badge badge-accepted" style={{ fontWeight: 700 }}>
                SELECTED
              </span>
            ) : isWithdrawn ? (
              <span className="badge badge-status" style={{ backgroundColor: '#e2e8f0', color: '#64748b' }}>
                WITHDRAWN
              </span>
            ) : isExpired ? (
              <span className="badge badge-declined">EXPIRED</span>
            ) : (
              <span className="badge badge-primary" style={{ backgroundColor: '#e0e7ff', color: '#4338ca' }}>
                AVAILABLE
              </span>
            )}
          </div>
        </div>

        {/* Financial Highlights */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '1fr 1fr',
            gap: '0.75rem',
            padding: '0.75rem 0',
            borderTop: '1px solid var(--color-border)',
            borderBottom: '1px solid var(--color-border)',
            marginBottom: '1rem',
          }}
        >
          <div>
            <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>Loan Amount</span>
            <div style={{ fontSize: '1.15rem', fontWeight: 700, color: 'var(--color-primary)' }}>
              {formatRupees(offer.loan_amount)}
            </div>
          </div>

          <div>
            <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>Annual APR</span>
            <div style={{ fontSize: '1.15rem', fontWeight: 700 }}>
              {formatApr(offer.apr)}
            </div>
          </div>

          <div>
            <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>Tenure</span>
            <div style={{ fontSize: '0.9375rem', fontWeight: 600 }}>
              {offer.term_months} Months
            </div>
          </div>

          <div>
            <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>Monthly Installment</span>
            <div style={{ fontSize: '0.9375rem', fontWeight: 600 }}>
              {formatRupees(offer.monthly_installment)}/mo
            </div>
          </div>
        </div>
      </div>

      {/* Action buttons */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', marginTop: '0.5rem' }}>
        <button
          type="button"
          className="btn btn-outline"
          style={{ fontSize: '0.8125rem', padding: '0.4rem 0.75rem', width: '100%' }}
          onClick={() => onViewKFS(offer.id)}
        >
          View Mock KFS
        </button>

        {canSelect && isAvailable && (
          <Button
            type="button"
            variant="primary"
            style={{ fontSize: '0.8125rem', padding: '0.4rem 0.75rem', width: '100%' }}
            onClick={() => onSelect(offer)}
            disabled={isSelecting}
            isLoading={isSelecting}
          >
            Select Offer
          </Button>
        )}
      </div>
    </div>
  );
};
