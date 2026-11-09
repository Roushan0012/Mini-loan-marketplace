import React from 'react';
import { CallerLead } from '../types';

interface CallerWorkspaceSummaryProps {
  leads: CallerLead[];
}

export const CallerWorkspaceSummary: React.FC<CallerWorkspaceSummaryProps> = ({ leads }) => {
  const totalOnPage = leads.length;
  const newOnPage = leads.filter((l) => (l.status || '').toLowerCase() === 'new').length;
  const inProgressOnPage = leads.filter((l) => (l.status || '').toLowerCase() === 'in_progress').length;

  return (
    <div style={{ marginBottom: '1.5rem' }}>
      <div className="metrics-grid">
        <div className="metric-card">
          <span className="metric-label">Leads on this page</span>
          <span className="metric-value">{totalOnPage}</span>
        </div>
        <div className="metric-card">
          <span className="metric-label">New leads on this page</span>
          <span className="metric-value">{newOnPage}</span>
        </div>
        <div className="metric-card">
          <span className="metric-label">In-progress leads on this page</span>
          <span className="metric-value">{inProgressOnPage}</span>
        </div>
      </div>
      <p style={{ margin: '-1rem 0 0 0', fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>
        * Metrics reflect records loaded on the current page view, not platform-wide totals.
      </p>
    </div>
  );
};
