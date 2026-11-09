import React, { useEffect, useState, useCallback, useMemo } from 'react';
import { useAuth } from '../hooks/useAuth';
import { adminMetricsService } from '../features/admin/services/adminMetricsService';
import { AdminMetrics } from '../features/admin/types';
import { LoadingSpinner } from '../components/feedback/LoadingSpinner';
import { ErrorMessage } from '../components/feedback/ErrorMessage';
import { ApiError } from '../services/apiErrors';
import { AdminMetricCard } from '../features/admin/components/AdminMetricCard';
import { AggregateStatusBreakdown } from '../features/admin/components/AggregateStatusBreakdown';
import { AdminDataConsistencyNotice } from '../features/admin/components/AdminDataConsistencyNotice';
import {
  getApplicationCountConsistency,
  getEventCountSummary,
} from '../features/admin/utils/adminMetrics';

export const AdminDashboardPage: React.FC = () => {
  const { user } = useAuth();
  const [metrics, setMetrics] = useState<AdminMetrics | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastRefreshedAt, setLastRefreshedAt] = useState<Date | null>(null);

  const fetchMetrics = useCallback(async (isRefresh = false) => {
    if (isRefresh) {
      setIsRefreshing(true);
    } else {
      setIsLoading(true);
    }
    setError(null);

    try {
      const data = await adminMetricsService.getAdminMetrics();
      setMetrics(data);
      setLastRefreshedAt(new Date());
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.getFormattedMessage());
      } else {
        setError('Failed to load administrative aggregate metrics. Please check network connection.');
      }
      // If a refresh failed, existing metrics snapshot is deliberately preserved!
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchMetrics(false);
  }, [fetchMetrics]);

  const consistency = useMemo(() => {
    return getApplicationCountConsistency(metrics);
  }, [metrics]);

  const eventCountSummary = useMemo(() => {
    return getEventCountSummary(metrics);
  }, [metrics]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* SECTION 1 — Header */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '1rem',
        }}
      >
        <div>
          <h1 style={{ fontSize: '1.75rem', fontWeight: 700, margin: 0 }}>
            Administrator Analytics
          </h1>
          <p style={{ fontWeight: 600, color: 'var(--color-text-main)', margin: '0.25rem 0' }}>
            Administrator Monitoring: {user?.full_name}
          </p>
          <p style={{ color: 'var(--color-text-muted)', fontSize: '0.875rem', margin: 0 }}>
            System-wide aggregate telemetry &bull; Privacy-preserving monitoring without individual customer PII
          </p>
        </div>
        <button
          type="button"
          className="btn btn-outline"
          onClick={() => fetchMetrics(true)}
          disabled={isLoading || isRefreshing}
          aria-label="Refresh aggregate metrics"
        >
          {isRefreshing ? 'Refreshing...' : 'Refresh Metrics'}
        </button>
      </div>

      {/* Privacy Notice Banner */}
      <div className="alert alert-info" style={{ fontSize: '0.8125rem', margin: 0 }}>
        🔒 <strong>Privacy & Telemetry Guardrail:</strong> This dashboard displays aggregate platform metrics only. Individual customer records, application IDs, loan amounts, and personal data are strictly inaccessible here.
      </div>

      {/* Error Banners */}
      {error && !metrics && (
        <ErrorMessage message={error} onRetry={() => fetchMetrics(false)} />
      )}

      {error && metrics && (
        <div
          className="alert alert-warning"
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            margin: 0,
            borderLeft: '4px solid #f59e0b',
          }}
        >
          <div>
            <strong>⚠️ Metrics Refresh Notice:</strong> Failed to fetch updated data ({error}). Displaying preserved snapshot from {lastRefreshedAt?.toLocaleTimeString()}.
          </div>
          <button
            type="button"
            className="btn btn-outline"
            onClick={() => fetchMetrics(true)}
            style={{ padding: '0.25rem 0.75rem', fontSize: '0.8125rem' }}
          >
            Retry Refresh
          </button>
        </div>
      )}

      {isLoading ? (
        <LoadingSpinner message="Aggregating platform metrics..." />
      ) : metrics ? (
        <>
          {/* SECTION 2 — Platform Totals */}
          <div>
            <h2 style={{ fontSize: '1.125rem', fontWeight: 600, marginBottom: '0.75rem' }}>
              Platform Pipeline Totals
            </h2>
            <div className="metrics-grid">
              <AdminMetricCard
                title="Total Leads"
                value={metrics.total_leads}
                description="Total prospective customer leads generated in system"
              />
              <AdminMetricCard
                title="Total Applications"
                value={metrics.total_applications}
                description="Total loan applications initiated across all statuses"
              />
              <AdminMetricCard
                title="Total Match Runs"
                value={metrics.total_match_runs}
                description="Total multi-lender policy matching executions"
              />
              <AdminMetricCard
                title="Total Offers"
                value={metrics.total_offers}
                description="Total credit offers generated across all match runs"
              />
              <AdminMetricCard
                title="Total Submissions"
                value={metrics.total_submissions}
                description="Total offer submissions dispatched to mock lenders"
              />
            </div>
          </div>

          {/* SECTION 5 — Data Consistency */}
          <AdminDataConsistencyNotice consistency={consistency} />

          {/* SECTION 3 & 4 — Breakdowns Grid */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))',
              gap: '1.5rem',
            }}
          >
            {/* SECTION 3 — Application Lifecycle */}
            <AggregateStatusBreakdown
              title="Application Lifecycle Status Breakdown"
              description="Distribution of loan applications across lifecycle stages from initial draft creation to terminal states."
              statusCounts={metrics.applications_by_status}
              emptyMessage="No loan applications recorded yet."
              statusLabelHeading="Application Status"
            />

            {/* SECTION 4 — Lender Event Processing */}
            <AggregateStatusBreakdown
              title="Lender Webhook Events by Processing Status"
              description="Audit ledger processing states for simulated lender webhook callbacks received by the platform."
              statusCounts={metrics.lender_events_by_processing_status}
              emptyMessage="No lender webhook events recorded yet."
              statusLabelHeading="Processing Status"
              footerNote={`Events represented in processing-status breakdown: ${eventCountSummary}`}
            />
          </div>

          {/* SECTION 6 — Data Freshness */}
          {lastRefreshedAt && (
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                flexWrap: 'wrap',
                gap: '0.5rem',
                padding: '0.75rem 1rem',
                backgroundColor: 'var(--color-bg-alt, #f8fafc)',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--color-border)',
                fontSize: '0.8125rem',
                color: 'var(--color-text-muted)',
              }}
            >
              <div>
                <strong>Last refreshed:</strong> {lastRefreshedAt.toLocaleTimeString()} ({lastRefreshedAt.toLocaleDateString()})
              </div>
              <div style={{ fontSize: '0.75rem' }}>
                Browser retrieval timestamp &bull; On-demand snapshot; no background polling.
              </div>
            </div>
          )}
        </>
      ) : null}
    </div>
  );
};
