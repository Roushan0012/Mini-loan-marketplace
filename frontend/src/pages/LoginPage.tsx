import React from 'react';
import { useSearchParams } from 'react-router-dom';
import { LoginForm } from '../features/auth/components/LoginForm';
import { Card } from '../components/ui/Card';

export const LoginPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const wasRegistered = searchParams.get('registered') === 'true';

  return (
    <div style={{ maxWidth: '480px', margin: '2rem auto' }}>
      <Card>
        <div style={{ textAlign: 'center', marginBottom: '1.5rem' }}>
          <h1 style={{ fontSize: '1.75rem', fontWeight: 700, color: 'var(--color-text-main)' }}>
            Welcome Back
          </h1>
          <p style={{ color: 'var(--color-text-muted)', fontSize: '0.875rem', marginTop: '0.25rem' }}>
            Sign in to access your Mini Loan Marketplace dashboard
          </p>
        </div>

        {wasRegistered && (
          <div className="alert alert-info" role="status">
            Account registered successfully! Please sign in with your credentials.
          </div>
        )}

        <LoginForm />
      </Card>
    </div>
  );
};
