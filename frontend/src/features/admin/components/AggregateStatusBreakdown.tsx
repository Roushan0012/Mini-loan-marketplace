import React from 'react';
import { Card } from '../../../components/ui/Card';
import { getStatusBreakdownItems } from '../utils/adminMetrics';

interface AggregateStatusBreakdownProps {
  title: string;
  description?: string;
  statusCounts: Record<string, number> | null | undefined;
  emptyMessage?: string;
  tableAriaLabel?: string;
  statusLabelHeading?: string;
  footerNote?: string;
}

export const AggregateStatusBreakdown: React.FC<AggregateStatusBreakdownProps> = ({
  title,
  description,
  statusCounts,
  emptyMessage = 'No status data recorded yet.',
  tableAriaLabel,
  statusLabelHeading = 'Status',
  footerNote,
}) => {
  const items = getStatusBreakdownItems(statusCounts);
  const totalCount = items.reduce((sum, item) => sum + item.count, 0);

  return (
    <Card title={title}>
      {description && (
        <p
          style={{
            color: 'var(--color-text-muted)',
            fontSize: '0.8125rem',
            margin: '-0.5rem 0 1rem 0',
            lineHeight: 1.4,
          }}
        >
          {description}
        </p>
      )}

      {items.length === 0 ? (
        <p style={{ color: 'var(--color-text-muted)', fontSize: '0.875rem', margin: '1rem 0' }}>
          {emptyMessage}
        </p>
      ) : (
        <>
          <div className="table-responsive">
            <table
              className="data-table"
              aria-label={tableAriaLabel || `${title} table`}
              style={{ width: '100%', marginBottom: '0.5rem' }}
            >
              <thead>
                <tr>
                  <th scope="col" style={{ width: '35%' }}>{statusLabelHeading}</th>
                  <th scope="col" style={{ width: '45%' }}>Distribution</th>
                  <th scope="col" style={{ width: '20%', textAlign: 'right' }}>Count (Share)</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.status}>
                    <td>
                      <span
                        className={`badge badge-status badge-${item.status.toLowerCase()}`}
                        style={{
                          fontWeight: 600,
                          fontSize: '0.75rem',
                          padding: '0.25rem 0.5rem',
                          borderRadius: 'var(--radius-sm)',
                        }}
                      >
                        {item.label}
                      </span>
                    </td>
                    <td style={{ verticalAlign: 'middle' }}>
                      <div
                        role="progressbar"
                        aria-valuenow={item.percentage}
                        aria-valuemin={0}
                        aria-valuemax={100}
                        aria-label={`${item.label}: ${item.count} (${item.percentage}%)`}
                        style={{
                          width: '100%',
                          height: '10px',
                          backgroundColor: 'var(--color-border, #e2e8f0)',
                          borderRadius: '5px',
                          overflow: 'hidden',
                          display: 'flex',
                        }}
                      >
                        <div
                          style={{
                            width: `${Math.min(100, Math.max(0, item.percentage))}%`,
                            backgroundColor: 'var(--color-primary, #3b82f6)',
                            transition: 'width 0.3s ease',
                          }}
                        />
                      </div>
                    </td>
                    <td style={{ textAlign: 'right', fontWeight: 600, fontSize: '0.875rem' }}>
                      <span>{item.count}</span>
                      <span
                        style={{
                          color: 'var(--color-text-muted)',
                          fontSize: '0.75rem',
                          fontWeight: 400,
                          marginLeft: '0.35rem',
                        }}
                      >
                        ({item.percentage}%)
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginTop: '0.75rem',
              paddingTop: '0.5rem',
              borderTop: '1px solid var(--color-border)',
              fontSize: '0.75rem',
              color: 'var(--color-text-muted)',
            }}
          >
            <span>Total categorized records: <strong>{totalCount}</strong></span>
            {footerNote && <span>{footerNote}</span>}
          </div>
        </>
      )}
    </Card>
  );
};
