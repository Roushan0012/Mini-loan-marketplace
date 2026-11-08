import React from 'react';

export interface EmptyStateProps {
  title: string;
  description?: string;
  action?: React.ReactNode;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  title,
  description,
  action,
}) => {
  return (
    <div
      style={{
        textAlign: 'center',
        padding: '3rem 1.5rem',
        border: '2px dashed var(--color-border)',
        borderRadius: 'var(--radius-lg)',
        backgroundColor: '#ffffff',
        margin: '1rem 0',
      }}
    >
      <div style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>📋</div>
      <h3 style={{ fontSize: '1.125rem', fontWeight: 600, color: 'var(--color-text-main)' }}>
        {title}
      </h3>
      {description && (
        <p style={{ color: 'var(--color-text-muted)', fontSize: '0.875rem', marginTop: '0.25rem', maxWidth: '400px', marginInline: 'auto' }}>
          {description}
        </p>
      )}
      {action && <div style={{ marginTop: '1.25rem' }}>{action}</div>}
    </div>
  );
};
