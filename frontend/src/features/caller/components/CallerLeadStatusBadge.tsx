import React from 'react';

interface CallerLeadStatusBadgeProps {
  status: string;
}

export const CallerLeadStatusBadge: React.FC<CallerLeadStatusBadgeProps> = ({ status }) => {
  const normalized = (status || '').toLowerCase().trim();

  const getBadgeStyle = () => {
    switch (normalized) {
      case 'new':
        return {
          backgroundColor: '#dbeafe',
          color: '#1e40af',
          border: '1px solid #bfdbfe',
        };
      case 'in_progress':
        return {
          backgroundColor: '#fef3c7',
          color: '#92400e',
          border: '1px solid #fde68a',
        };
      case 'contacted':
        return {
          backgroundColor: '#e0e7ff',
          color: '#3730a3',
          border: '1px solid #c7d2fe',
        };
      case 'qualified':
        return {
          backgroundColor: '#dcfce7',
          color: '#166534',
          border: '1px solid #bbf7d0',
        };
      case 'disqualified':
        return {
          backgroundColor: '#fee2e2',
          color: '#991b1b',
          border: '1px solid #fecaca',
        };
      case 'closed':
        return {
          backgroundColor: '#f1f5f9',
          color: '#475569',
          border: '1px solid #cbd5e1',
        };
      default:
        // Safely support any unknown or custom backend status
        return {
          backgroundColor: 'var(--color-bg-alt, #f8fafc)',
          color: 'var(--color-text-main, #334155)',
          border: '1px solid var(--color-border, #e2e8f0)',
        };
    }
  };

  const formatStatusLabel = (s: string): string => {
    if (!s) return 'UNKNOWN';
    return s.replace(/_/g, ' ').toUpperCase();
  };

  return (
    <span
      className={`badge badge-status badge-${normalized}`}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        padding: '0.25rem 0.5rem',
        borderRadius: 'var(--radius-sm, 4px)',
        fontSize: '0.75rem',
        fontWeight: 600,
        textTransform: 'uppercase',
        letterSpacing: '0.025em',
        ...getBadgeStyle(),
      }}
    >
      {formatStatusLabel(status)}
    </span>
  );
};
