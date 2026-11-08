import React, { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { apiClient } from '../services/apiClient';
import { LoanApplication } from '../types/api';
import { Card } from '../components/ui/Card';
import { LoadingSpinner } from '../components/feedback/LoadingSpinner';
import { ErrorMessage } from '../components/feedback/ErrorMessage';
import { EmptyState } from '../components/feedback/EmptyState';
import { ApiError } from '../services/apiErrors';

export const CustomerDashboardPage: React.FC = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [applications, setApplications] = useState<LoanApplication[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchApplications = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await apiClient.get<LoanApplication[]>('/applications');
      setApplications(data);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.getFormattedMessage());
      } else {
        setError('Failed to load loan applications. Please verify your connection.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchApplications();
  }, []);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Header section */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h1 style={{ fontSize: '1.75rem', fontWeight: 700 }}>
            Welcome back, {user?.full_name}!
          </h1>
          <p style={{ color: 'var(--color-text-muted)', fontSize: '0.875rem' }}>
            Customer Dashboard &bull; Manage your simulated loan applications and compare offers
          </p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button
            type="button"
            className="btn btn-outline"
            onClick={fetchApplications}
            disabled={isLoading}
          >
            Refresh
          </button>
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => navigate('/customer/applications/new')}
          >
            + New Application
          </button>
        </div>
      </div>

      <ErrorMessage message={error || undefined} onRetry={fetchApplications} />

      {/* Metrics Banner */}
      <div className="metrics-grid">
        <div className="metric-card">
          <span className="metric-label">Total Applications</span>
          <span className="metric-value">{applications.length}</span>
        </div>
        <div className="metric-card">
          <span className="metric-label">Active / Submitted</span>
          <span className="metric-value">
            {applications.filter((a) => ['draft', 'matched', 'offer_selected', 'submitted'].includes(a.status)).length}
          </span>
        </div>
        <div className="metric-card">
          <span className="metric-label">Completed / Terminal</span>
          <span className="metric-value">
            {applications.filter((a) => ['accepted', 'declined', 'timed_out', 'failed'].includes(a.status)).length}
          </span>
        </div>
      </div>

      {/* Applications list */}
      <Card title="My Loan Applications">
        {isLoading ? (
          <LoadingSpinner message="Loading your applications..." />
        ) : applications.length === 0 ? (
          <EmptyState
            title="No Loan Applications Yet"
            description="You have not created any loan applications. Click 'New Application' to start a new simulated loan journey."
            action={
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => navigate('/customer/applications/new')}
              >
                Start First Application
              </button>
            }
          />
        ) : (
          <div className="table-responsive">
            <table className="data-table" aria-label="Loan applications list">
              <thead>
                <tr>
                  <th>App ID</th>
                  <th>Requested Amount</th>
                  <th>Age</th>
                  <th>Monthly Income</th>
                  <th>Work Type</th>
                  <th>Status</th>
                  <th>Created</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {applications.map((app) => (
                  <tr
                    key={app.id}
                    style={{ cursor: 'pointer' }}
                    onClick={() => navigate(`/customer/applications/${app.id}`)}
                  >
                    <td style={{ fontWeight: 600 }}>
                      <Link
                        to={`/customer/applications/${app.id}`}
                        style={{ color: 'var(--color-primary)', textDecoration: 'underline' }}
                        onClick={(e) => e.stopPropagation()}
                      >
                        #{app.id}
                      </Link>
                    </td>
                    <td style={{ fontWeight: 600 }}>
                      ₹{Number(app.requested_amount).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                    </td>
                    <td>{app.age} yrs</td>
                    <td>₹{Number(app.monthly_income).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</td>
                    <td style={{ textTransform: 'capitalize' }}>{app.work_type.replace('_', ' ')}</td>
                    <td>
                      <span className={`badge badge-status badge-${app.status}`}>
                        {app.status.replace('_', ' ')}
                      </span>
                    </td>
                    <td style={{ color: 'var(--color-text-muted)' }}>
                      {new Date(app.created_at).toLocaleDateString()}
                    </td>
                    <td>
                      <button
                        type="button"
                        className="btn btn-outline"
                        style={{ padding: '0.25rem 0.5rem', fontSize: '0.75rem' }}
                        onClick={(e) => {
                          e.stopPropagation();
                          navigate(`/customer/applications/${app.id}`);
                        }}
                      >
                        View
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
};
