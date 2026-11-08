import React from 'react';
import { RegisterForm } from '../features/auth/components/RegisterForm';
import { Card } from '../components/ui/Card';

export const RegisterPage: React.FC = () => {
  return (
    <div style={{ maxWidth: '520px', margin: '2rem auto' }}>
      <Card>
        <div style={{ textAlign: 'center', marginBottom: '1.5rem' }}>
          <h1 style={{ fontSize: '1.75rem', fontWeight: 700, color: 'var(--color-text-main)' }}>
            Customer Registration
          </h1>
          <p style={{ color: 'var(--color-text-muted)', fontSize: '0.875rem', marginTop: '0.25rem' }}>
            Create a customer account to simulate loan applications and compare offers
          </p>
        </div>

        <div className="alert alert-warning" role="note" style={{ fontSize: '0.8125rem' }}>
          <strong>Note:</strong> Self-registration creates a fictional customer profile. Caller and Admin credentials are provisioned administratively by the system.
        </div>

        <RegisterForm />
      </Card>
    </div>
  );
};
