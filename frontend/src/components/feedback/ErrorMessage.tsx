import React from 'react';

export interface ErrorMessageProps {
  message?: string;
  onRetry?: () => void;
  className?: string;
}

export const ErrorMessage: React.FC<ErrorMessageProps> = ({
  message,
  onRetry,
  className = '',
}) => {
  if (!message) return null;

  return (
    <div className={`alert alert-danger ${className}`} role="alert">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '1rem' }}>
        <span>{message}</span>
        {onRetry && (
          <button
            type="button"
            className="btn btn-outline"
            style={{ padding: '0.25rem 0.5rem', fontSize: '0.75rem', borderColor: 'currentColor' }}
            onClick={onRetry}
          >
            Retry
          </button>
        )}
      </div>
    </div>
  );
};
