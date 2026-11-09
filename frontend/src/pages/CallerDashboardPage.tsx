import React, { useEffect, useState, useMemo, useCallback } from 'react';
import { useAuth } from '../hooks/useAuth';
import { callerLeadService } from '../features/caller/services/callerLeadService';
import { CallerLead, CallerWorkspaceFilters } from '../features/caller/types';
import { Card } from '../components/ui/Card';
import { LoadingSpinner } from '../components/feedback/LoadingSpinner';
import { ErrorMessage } from '../components/feedback/ErrorMessage';
import { EmptyState } from '../components/feedback/EmptyState';
import { ApiError } from '../services/apiErrors';
import { CallerWorkspaceSummary } from '../features/caller/components/CallerWorkspaceSummary';
import { CallerLeadFilters } from '../features/caller/components/CallerLeadFilters';
import { CallerLeadTable } from '../features/caller/components/CallerLeadTable';
import { CallerLeadDetailDrawer } from '../features/caller/components/CallerLeadDetailDrawer';

const PAGE_SIZE = 25;

export const CallerDashboardPage: React.FC = () => {
  const { user } = useAuth();
  const [leads, setLeads] = useState<CallerLead[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [selectedLead, setSelectedLead] = useState<CallerLead | null>(null);

  // Filters state (scoped to the currently loaded page)
  const [filters, setFilters] = useState<CallerWorkspaceFilters>({
    searchTerm: '',
    statusFilter: '',
    workTypeFilter: '',
  });

  const fetchLeads = useCallback(async (targetPage: number) => {
    setIsLoading(true);
    setError(null);
    setSelectedLead(null);
    const offset = (targetPage - 1) * PAGE_SIZE;

    try {
      const data = await callerLeadService.getAssignedLeads(PAGE_SIZE, offset);
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
  }, []);

  useEffect(() => {
    fetchLeads(page);
  }, [page, fetchLeads]);

  const handleRefresh = () => {
    if (page === 1) {
      fetchLeads(1);
    } else {
      setPage(1);
    }
  };

  const handleClearFilters = () => {
    setFilters({
      searchTerm: '',
      statusFilter: '',
      workTypeFilter: '',
    });
  };

  const hasActiveFilters = Boolean(
    filters.searchTerm.trim() || filters.statusFilter || filters.workTypeFilter
  );

  // Extract distinct filter options from current page leads
  const availableStatuses = useMemo(() => {
    const set = new Set<string>();
    leads.forEach((l) => {
      if (l.status) set.add(l.status);
    });
    return Array.from(set).sort();
  }, [leads]);

  const availableWorkTypes = useMemo(() => {
    const set = new Set<string>();
    leads.forEach((l) => {
      if (l.work_type) set.add(l.work_type);
    });
    return Array.from(set).sort();
  }, [leads]);

  // Apply search and filters to current page leads
  const filteredLeads = useMemo(() => {
    return leads.filter((lead) => {
      // Search term matches applicant name or synthetic reference (case-insensitive)
      if (filters.searchTerm.trim()) {
        const query = filters.searchTerm.trim().toLowerCase();
        const nameMatch = (lead.applicant_name || '').toLowerCase().includes(query);
        const refMatch = (lead.synthetic_reference || '').toLowerCase().includes(query);
        if (!nameMatch && !refMatch) return false;
      }

      // Status filter
      if (filters.statusFilter) {
        if ((lead.status || '').toLowerCase() !== filters.statusFilter.toLowerCase()) {
          return false;
        }
      }

      // Work type filter
      if (filters.workTypeFilter) {
        if ((lead.work_type || '').toLowerCase() !== filters.workTypeFilter.toLowerCase()) {
          return false;
        }
      }

      return true;
    });
  }, [leads, filters]);

  const isNextDisabled = isLoading || leads.length < PAGE_SIZE;
  const isPrevDisabled = isLoading || page === 1;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Workspace Header */}
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
            Caller Workspace: {user?.full_name}
          </h1>
          <p style={{ color: 'var(--color-text-muted)', fontSize: '0.875rem', margin: '0.25rem 0 0 0' }}>
            Strict Lead Isolation Active &bull; You can view only leads assigned to your caller account.
          </p>
        </div>
        <button
          type="button"
          className="btn btn-outline"
          onClick={handleRefresh}
          disabled={isLoading}
        >
          Refresh Leads
        </button>
      </div>

      {/* Privacy Notice Banner */}
      <div className="alert alert-info" style={{ fontSize: '0.8125rem', margin: 0 }}>
        🔒 <strong>Confidentiality Notice:</strong> You can view only leads assigned to your caller account. All borrower records are subject to strict caller isolation.
      </div>

      {error && <ErrorMessage message={error} onRetry={() => fetchLeads(page)} />}

      {/* Summary Metrics for current page */}
      <CallerWorkspaceSummary leads={leads} />

      {/* Search and Filters */}
      <CallerLeadFilters
        filters={filters}
        availableStatuses={availableStatuses}
        availableWorkTypes={availableWorkTypes}
        onFilterChange={setFilters}
        onClearFilters={handleClearFilters}
        hasActiveFilters={hasActiveFilters}
      />

      {/* Main Content Card */}
      <Card title={`Assigned Leads Queue (Page ${page})`}>
        {isLoading ? (
          <LoadingSpinner message="Fetching your assigned leads..." />
        ) : leads.length === 0 ? (
          page === 1 ? (
            <EmptyState
              title="No Leads Assigned"
              description="You currently have no leads assigned to your queue. Leads assigned to other callers remain strictly isolated."
            />
          ) : (
            <div style={{ textAlign: 'center', padding: '2rem 1rem' }}>
              <p style={{ color: 'var(--color-text-muted)', marginBottom: '1rem' }}>
                No leads found on page {page}.
              </p>
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => setPage(1)}
              >
                Return to Page 1
              </button>
            </div>
          )
        ) : filteredLeads.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '2.5rem 1rem' }}>
            <p style={{ color: 'var(--color-text-muted)', marginBottom: '1rem', fontSize: '0.95rem' }}>
              No leads match the current filters on this page.
            </p>
            <button
              type="button"
              className="btn btn-outline"
              onClick={handleClearFilters}
            >
              Clear Filters
            </button>
          </div>
        ) : (
          <>
            <CallerLeadTable
              leads={filteredLeads}
              onSelectLead={setSelectedLead}
            />

            {/* Pagination Controls */}
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                flexWrap: 'wrap',
                gap: '1rem',
                marginTop: '1.25rem',
                paddingTop: '1rem',
                borderTop: '1px solid var(--color-border)',
                fontSize: '0.875rem',
              }}
            >
              <div style={{ color: 'var(--color-text-muted)' }}>
                Page {page} &bull; Showing {filteredLeads.length} of {leads.length} lead{leads.length === 1 ? '' : 's'} on this page
              </div>
              <div style={{ display: 'flex', gap: '0.5rem' }}>
                <button
                  type="button"
                  className="btn btn-outline"
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={isPrevDisabled}
                  aria-label="Previous page"
                >
                  &larr; Previous Page
                </button>
                <button
                  type="button"
                  className="btn btn-outline"
                  onClick={() => setPage((p) => p + 1)}
                  disabled={isNextDisabled}
                  aria-label="Next page"
                >
                  Next Page &rarr;
                </button>
              </div>
            </div>
          </>
        )}
      </Card>

      {/* Lead Details Drawer */}
      <CallerLeadDetailDrawer
        lead={selectedLead}
        isOpen={selectedLead !== null}
        onClose={() => setSelectedLead(null)}
      />
    </div>
  );
};
