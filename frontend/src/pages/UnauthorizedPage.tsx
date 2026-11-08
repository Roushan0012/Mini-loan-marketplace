import React from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { Card } from '../components/ui/Card';
import { getDashboardPathForRole } from '../app/routes/routeUtils';

export const UnauthorizedPage: React.FC = () => {
  const { user } = useAuth();
  const dashboardPath = getDashboardPathForRole(user?.role);

  return (
    <div style={{ maxWidth: '480px', margin: '4rem auto', textAlign: 'center' }}>
      <Card>
        <div style={{ fontSize: '3rem', marginBottom: '0.5rem' }}>🚫</div>
        <h1 style={{ fontSize: '1.75rem', fontWeight: 700, marginBottom: '0.5rem', color: 'var(--color-danger)' }}>
          403 - Unauthorized Access
        </h1>
        <p style={{ color: 'var(--color-text-muted)', fontSize: '0.875rem', marginBottom: '1.5rem' }}>
          Your current account role ({user ? <strong>{user.role}</strong> : 'unauthenticated'}) does not have permission to access the requested view. Role separation is enforced by both frontend route guards and backend security controls.
        </p>
        <Link to={dashboardPath} className="btn btn-primary">
          Back to Authorized Dashboard
        </Link>
      </Card>
    </div>
  );
};
