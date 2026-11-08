import React, { forwardRef, useState } from 'react';

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label: string;
  error?: string;
  showPasswordToggle?: boolean;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ id, label, error, type = 'text', showPasswordToggle = false, className = '', ...props }, ref) => {
    const [isPasswordVisible, setIsPasswordVisible] = useState(false);
    const inputId = id || props.name || Math.random().toString(36).substring(2, 9);
    const errorId = `${inputId}-error`;

    const effectiveType = showPasswordToggle && type === 'password'
      ? (isPasswordVisible ? 'text' : 'password')
      : type;

    return (
      <div className="form-group">
        <label htmlFor={inputId} className="form-label">
          {label}
        </label>
        <div className={showPasswordToggle ? 'input-password-wrapper' : undefined}>
          <input
            id={inputId}
            ref={ref}
            type={effectiveType}
            className={`form-input ${error ? 'form-input-error' : ''} ${className}`}
            aria-invalid={Boolean(error)}
            aria-describedby={error ? errorId : undefined}
            {...props}
          />
          {showPasswordToggle && type === 'password' && (
            <button
              type="button"
              className="password-toggle-btn"
              onClick={() => setIsPasswordVisible((prev) => !prev)}
              aria-label={isPasswordVisible ? 'Hide password' : 'Show password'}
            >
              {isPasswordVisible ? 'Hide' : 'Show'}
            </button>
          )}
        </div>
        {error && (
          <p id={errorId} className="form-error-text" role="alert">
            {error}
          </p>
        )}
      </div>
    );
  }
);

Input.displayName = 'Input';
