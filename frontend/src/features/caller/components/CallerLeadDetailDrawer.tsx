import React, { useEffect, useRef } from 'react';
import { CallerLead } from '../types';
import { formatRupees } from '../../offers/utils/formatMoney';
import { CallerLeadStatusBadge } from './CallerLeadStatusBadge';

interface CallerLeadDetailDrawerProps {
  lead: CallerLead | null;
  isOpen: boolean;
  onClose: () => void;
}

export const CallerLeadDetailDrawer: React.FC<CallerLeadDetailDrawerProps> = ({
  lead,
  isOpen,
  onClose,
}) => {
  const closeButtonRef = useRef<HTMLButtonElement>(null);

  // Focus close button on open, handle Escape key
  useEffect(() => {
    if (!isOpen) return;

    closeButtonRef.current?.focus();

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen || !lead) return null;

  const formatWorkType = (wt: string) => {
    switch (wt) {
      case 'salaried':
        return 'Salaried Employee';
      case 'self_employed':
        return 'Self-Employed';
      case 'other':
        return 'Other';
      default:
        return wt.replace(/_/g, ' ');
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
        zIndex: 1050,
        padding: '1rem',
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) {
          onClose();
        }
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="caller-lead-drawer-title"
        className="card"
        style={{
          width: '100%',
          maxWidth: '560px',
          backgroundColor: '#ffffff',
          boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.2)',
          padding: '1.75rem',
          maxHeight: '90vh',
          overflowY: 'auto',
        }}
      >
        {/* Header */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'flex-start',
            marginBottom: '1.25rem',
            paddingBottom: '0.75rem',
            borderBottom: '1px solid var(--color-border)',
          }}
        >
          <div>
            <h3
              id="caller-lead-drawer-title"
              style={{ fontSize: '1.25rem', fontWeight: 700, margin: '0 0 0.25rem 0' }}
            >
              Lead: {lead.synthetic_reference}
            </h3>
            <p style={{ margin: 0, fontSize: '0.875rem', color: 'var(--color-text-muted)' }}>
              Assigned applicant profile information
            </p>
          </div>
          <button
            ref={closeButtonRef}
            type="button"
            className="btn btn-outline"
            onClick={onClose}
            aria-label="Close lead details"
            style={{
              padding: '0.25rem 0.5rem',
              fontSize: '1rem',
              lineHeight: 1,
              borderRadius: 'var(--radius-sm)',
            }}
          >
            ✕
          </button>
        </div>

        {/* Lead Details Grid */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
            gap: '1rem',
            marginBottom: '1.5rem',
          }}
        >
          <div
            style={{
              padding: '0.75rem 1rem',
              backgroundColor: 'var(--color-bg-alt, #f8fafc)',
              borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--color-border)',
            }}
          >
            <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', display: 'block' }}>
              Applicant Name
            </span>
            <span style={{ fontWeight: 600, fontSize: '0.95rem' }}>{lead.applicant_name}</span>
          </div>

          <div
            style={{
              padding: '0.75rem 1rem',
              backgroundColor: 'var(--color-bg-alt, #f8fafc)',
              borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--color-border)',
            }}
          >
            <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', display: 'block' }}>
              Synthetic Reference
            </span>
            <code style={{ fontWeight: 600, fontSize: '0.9rem' }}>{lead.synthetic_reference}</code>
          </div>

          <div
            style={{
              padding: '0.75rem 1rem',
              backgroundColor: 'var(--color-bg-alt, #f8fafc)',
              borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--color-border)',
            }}
          >
            <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', display: 'block' }}>
              Age
            </span>
            <span style={{ fontWeight: 600, fontSize: '0.95rem' }}>{lead.age} years</span>
          </div>

          <div
            style={{
              padding: '0.75rem 1rem',
              backgroundColor: 'var(--color-bg-alt, #f8fafc)',
              borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--color-border)',
            }}
          >
            <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', display: 'block' }}>
              Employment Type
            </span>
            <span style={{ fontWeight: 600, fontSize: '0.95rem' }}>{formatWorkType(lead.work_type)}</span>
          </div>

          <div
            style={{
              padding: '0.75rem 1rem',
              backgroundColor: 'var(--color-bg-alt, #f8fafc)',
              borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--color-border)',
            }}
          >
            <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', display: 'block' }}>
              Monthly Income
            </span>
            <span style={{ fontWeight: 600, fontSize: '1rem', color: 'var(--color-text-main)' }}>
              {formatRupees(lead.monthly_income)}
            </span>
          </div>

          <div
            style={{
              padding: '0.75rem 1rem',
              backgroundColor: 'var(--color-bg-alt, #f8fafc)',
              borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--color-border)',
            }}
          >
            <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', display: 'block' }}>
              Requested Amount
            </span>
            <span style={{ fontWeight: 700, fontSize: '1rem', color: 'var(--color-primary)' }}>
              {formatRupees(lead.requested_amount)}
            </span>
          </div>

          <div
            style={{
              padding: '0.75rem 1rem',
              backgroundColor: 'var(--color-bg-alt, #f8fafc)',
              borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--color-border)',
            }}
          >
            <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', display: 'block' }}>
              Lead Status
            </span>
            <div style={{ marginTop: '0.25rem' }}>
              <CallerLeadStatusBadge status={lead.status} />
            </div>
          </div>

          <div
            style={{
              padding: '0.75rem 1rem',
              backgroundColor: 'var(--color-bg-alt, #f8fafc)',
              borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--color-border)',
            }}
          >
            <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', display: 'block' }}>
              Assigned Timestamp
            </span>
            <span style={{ fontSize: '0.875rem' }}>
              {new Date(lead.assigned_at).toLocaleString()}
            </span>
          </div>
        </div>

        {/* Read-Only Notice */}
        <div className="alert alert-info" style={{ fontSize: '0.8125rem', marginBottom: '1.25rem' }}>
          <strong>ℹ️ Read-Only Scope:</strong> Lead details are strictly read-only for assigned callers. Communication logs, status modifications, lead reassignments, and customer application details are not accessible or permitted in this workspace.
        </div>

        {/* Action Footer */}
        <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
          <button
            type="button"
            className="btn btn-outline"
            onClick={onClose}
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
