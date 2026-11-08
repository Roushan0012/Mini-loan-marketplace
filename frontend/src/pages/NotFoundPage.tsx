import React from 'react';
import { Link } from 'react-router-dom';
import { Card } from '../components/ui/Card';

export const NotFoundPage: React.FC = () => {
  return (
    <div style={{ maxWidth: '480px', margin: '4rem auto', textAlign: 'center' }}>
      <Card>
        <div style={{ fontSize: '3rem', marginBottom: '0.5rem' }}>🔍</div>
        <h1 style={{ fontSize: '1.75rem', fontWeight: 700, marginBottom: '0.5rem' }}>
          404 - Page Not Found
        </h1>
        <p style={{ color: 'var(--color-text-muted)', fontSize: '0.875rem', marginBottom: '1.5rem' }}>
          The page or route you are looking for does not exist in the marketplace.
        </p>
        <Link to="/login" className="btn btn-primary">
          Return to Application
        </Link>
      </Card>
    </div>
  );
};
