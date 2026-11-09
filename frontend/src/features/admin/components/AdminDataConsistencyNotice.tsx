import React from 'react';
import { ApplicationConsistencyResult } from '../types';

interface AdminDataConsistencyNoticeProps {
  consistency: ApplicationConsistencyResult;
}

export const AdminDataConsistencyNotice: React.FC<AdminDataConsistencyNoticeProps> = ({
  consistency,
}) => {
  const { isConsistent, groupedTotal, reportedTotal, difference } = consistency;

  if (isConsistent) {
    return (
      <div
        className="alert alert-info"
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '0.75rem',
          fontSize: '0.8125rem',
          margin: 0,
        }}
      >
        <span style={{ fontSize: '1.1rem' }}>✓</span>
        <div>
          <strong>Reconciliation Verified:</strong> Application totals reconcile with the status breakdown.
          <span style={{ color: 'var(--color-text-muted)', marginLeft: '0.5rem' }}>
            ({reportedTotal} total applications = {groupedTotal} status entries)
          </span>
        </div>
      </div>
    );
  }

  const diffSign = difference > 0 ? `+${difference}` : `${difference}`;

  return (
    <div
      className="alert alert-warning"
      style={{
        display: 'flex',
        alignItems: 'flex-start',
        gap: '0.75rem',
        fontSize: '0.8125rem',
        margin: 0,
        borderLeft: '4px solid #f59e0b',
      }}
    >
      <span style={{ fontSize: '1.25rem', lineHeight: 1 }}>⚠️</span>
      <div>
        <p style={{ margin: '0 0 0.25rem 0', fontWeight: 600 }}>
          Application Status Discrepancy Detected
        </p>
        <p style={{ margin: 0, lineHeight: 1.4 }}>
          Total reported applications (<strong>{reportedTotal}</strong>) does not match the sum of status breakdown entries (<strong>{groupedTotal}</strong>), resulting in an aggregate difference of <strong>{diffSign}</strong>. The platform presents these raw counts transparently without heuristic adjustments.
        </p>
      </div>
    </div>
  );
};
