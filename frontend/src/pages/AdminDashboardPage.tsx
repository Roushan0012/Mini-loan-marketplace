import React, { useEffect, useState } from 'react';
import { useAuth } from '../hooks/useAuth';
import { apiClient } from '../services/apiClient';
import { AdminMetrics } from '../types/api';
import { Card } from '../components/ui/Card';
import { LoadingSpinner } from '../components/feedback/LoadingSpinner';
import { ErrorMessage } from '../components/feedback/ErrorMessage';
import { ApiError } from '../services/apiErrors';

export const AdminDashboardPage: React.FC = () => {
  const { user } = useAuth();
  const [metrics, setMetrics] = useState<AdminMetrics | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchMetrics = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await apiClient.get<AdminMetrics>('/admin/dashboard/metrics');
      setMetrics(data);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.getFormattedMessage());
      } else {
        setError('Failed to load administrative metrics.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchMetrics();
  }, []);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h1 style={{ fontSize: '1.75rem', fontWeight: 700 }}>
            Administrator Monitoring: {user?.full_name}
          </h1>
          <p style={{ color: 'var(--color-text-muted)', fontSize: '0.875rem' }}>
            System-wide aggregate telemetry &bull; Privacy-preserving monitoring without individual customer PII
          </p>
        </div>
        <button
          type="button"
          className="btn btn-outline"
          onClick={fetchMetrics}
          disabled={isLoading}
        >
          Refresh Metrics
        </button>
      </div>

      <ErrorMessage message={error || undefined} onRetry={fetchMetrics} />

      {isLoading ? (
        <LoadingSpinner message="Aggregating platform metrics..." />
      ) : metrics ? (
        <>
          {/* Key Totals Grid */}
          <div className="metrics-grid">
            <div className="metric-card">
              <span className="metric-label">Total Leads</span>
              <span className="metric-value">{metrics.total_leads}</span>
            </div>
            <div className="metric-card">
              <span className="metric-label">Total Applications</span>
              <span className="metric-value">{metrics.total_applications}</span>
            </div>
            <div className="metric-card">
              <span className="metric-label">Completed Match Runs</span>
              <span className="metric-value">{metrics.total_match_runs}</span>
            </div>
            <div className="metric-card">
              <span className="metric-label">Generated Offers</span>
              <span className="metric-value">{metrics.total_offers}</span>
            </div>
            <div className="metric-card">
              <span className="metric-label">Dispatched Submissions</span>
              <span className="metric-value">{metrics.total_submissions}</span>
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '1.5rem' }}>
            {/* Applications by Status */}
            <Card title="Applications by Status">
              {Object.keys(metrics.applications_by_status).length === 0 ? (
                <p style={{ color: 'var(--color-text-muted)', fontSize: '0.875rem' }}>
                  No application data recorded yet.
                </p>
              ) : (
                <div className="table-responsive">
                  <table className="data-table" aria-label="Applications breakdown by status">
                    <thead>
                      <tr>
                        <th>Lifecycle Status</th>
                        <th style={{ textAlign: 'right' }}>Count</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(metrics.applications_by_status).map(([status, count]) => (
                        <tr key={status}>
                          <td>
                            <span className={`badge badge-status badge-${status}`}>
                              {status.replace('_', ' ')}
                            </span>
                          </td>
                          <td style={{ textAlign: 'right', fontWeight: 600 }}>{count}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Card>

            {/* Lender Events by Processing Status */}
            <Card title="Lender Webhook Events by Status">
              {Object.keys(metrics.lender_events_by_processing_status).length === 0 ? (
                <p style={{ color: 'var(--color-text-muted)', fontSize: '0.875rem' }}>
                  No webhook events recorded yet.
                </p>
              ) : (
                <div className="table-responsive">
                  <table className="data-table" aria-label="Webhook events breakdown">
                    <thead>
                      <tr>
                        <th>Processing Status</th>
                        <th style={{ textAlign: 'right' }}>Count</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(metrics.lender_events_by_processing_status).map(([procStatus, count]) => (
                        <tr key={procStatus}>
                          <td>
                            <span className="badge badge-status">
                              {procStatus}
                            </span>
                          </td>
                          <td style={{ textAlign: 'right', fontWeight: 600 }}>{count}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Card>
          </div>
        </>
      ) : null}
    </div>
  );
};
