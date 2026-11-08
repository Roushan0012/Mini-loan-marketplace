import React, { useEffect, useState } from 'react';
import { useAuth } from '../hooks/useAuth';
import { apiClient } from '../services/apiClient';
import { CallerLead } from '../types/api';
import { Card } from '../components/ui/Card';
import { LoadingSpinner } from '../components/feedback/LoadingSpinner';
import { ErrorMessage } from '../components/feedback/ErrorMessage';
import { EmptyState } from '../components/feedback/EmptyState';
import { ApiError } from '../services/apiErrors';

export const CallerDashboardPage: React.FC = () => {
  const { user } = useAuth();
  const [leads, setLeads] = useState<CallerLead[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchLeads = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await apiClient.get<CallerLead[]>('/caller/leads');
      setLeads(data);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.getFormattedMessage());
      } else {
        setError('Failed to load assigned leads. Please verify your connection.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchLeads();
  }, []);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h1 style={{ fontSize: '1.75rem', fontWeight: 700 }}>
            Caller Workspace: {user?.full_name}
          </h1>
          <p style={{ color: 'var(--color-text-muted)', fontSize: '0.875rem' }}>
            Strict Lead Isolation Active &bull; Viewing only leads assigned to your caller ID
          </p>
        </div>
        <button
          type="button"
          className="btn btn-outline"
          onClick={fetchLeads}
          disabled={isLoading}
        >
          Refresh Leads
        </button>
      </div>

      <ErrorMessage message={error || undefined} onRetry={fetchLeads} />

      {/* Metrics Banner */}
      <div className="metrics-grid">
        <div className="metric-card">
          <span className="metric-label">Assigned Leads</span>
          <span className="metric-value">{leads.length}</span>
        </div>
        <div className="metric-card">
          <span className="metric-label">Pending Review</span>
          <span className="metric-value">
            {leads.filter((l) => l.status === 'new' || l.status === 'in_progress').length}
          </span>
        </div>
      </div>

      <Card title="Assigned Leads Queue">
        {isLoading ? (
          <LoadingSpinner message="Fetching your assigned leads..." />
        ) : leads.length === 0 ? (
          <EmptyState
            title="No Leads Assigned"
            description="You currently have no leads assigned to your queue. Leads assigned to other callers remain strictly isolated."
          />
        ) : (
          <div className="table-responsive">
            <table className="data-table" aria-label="Assigned leads table">
              <thead>
                <tr>
                  <th>Ref ID</th>
                  <th>Applicant Name</th>
                  <th>Requested Amount</th>
                  <th>Monthly Income</th>
                  <th>Work Type</th>
                  <th>Status</th>
                  <th>Assigned Date</th>
                </tr>
              </thead>
              <tbody>
                {leads.map((lead) => (
                  <tr key={lead.id}>
                    <td style={{ fontWeight: 600 }}>{lead.synthetic_reference}</td>
                    <td>{lead.applicant_name}</td>
                    <td style={{ fontWeight: 600 }}>
                      ₹{Number(lead.requested_amount).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                    </td>
                    <td>₹{Number(lead.monthly_income).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</td>
                    <td style={{ textTransform: 'capitalize' }}>{lead.work_type.replace('_', ' ')}</td>
                    <td>
                      <span className={`badge badge-status badge-${lead.status}`}>
                        {lead.status}
                      </span>
                    </td>
                    <td style={{ color: 'var(--color-text-muted)' }}>
                      {new Date(lead.assigned_at).toLocaleDateString()}
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
