import React from 'react';

interface AdminMetricCardProps {
  title: string;
  value: number | string;
  description?: string;
  badge?: React.ReactNode;
}

export const AdminMetricCard: React.FC<AdminMetricCardProps> = ({
  title,
  value,
  description,
  badge,
}) => {
  return (
    <div className="metric-card" style={{ position: 'relative' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <span className="metric-label">{title}</span>
        {badge}
      </div>
      <span className="metric-value">{value}</span>
      {description && (
        <span
          style={{
            fontSize: '0.75rem',
            color: 'var(--color-text-muted)',
            marginTop: '0.5rem',
          }}
        >
          {description}
        </span>
      )}
    </div>
  );
};
