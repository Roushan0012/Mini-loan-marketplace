import React from 'react';
import { CallerWorkspaceFilters } from '../types';

interface CallerLeadFiltersProps {
  filters: CallerWorkspaceFilters;
  availableStatuses: string[];
  availableWorkTypes: string[];
  onFilterChange: (filters: CallerWorkspaceFilters) => void;
  onClearFilters: () => void;
  hasActiveFilters: boolean;
}

export const CallerLeadFilters: React.FC<CallerLeadFiltersProps> = ({
  filters,
  availableStatuses,
  availableWorkTypes,
  onFilterChange,
  onClearFilters,
  hasActiveFilters,
}) => {
  const formatWorkTypeLabel = (wt: string) => {
    switch (wt) {
      case 'salaried':
        return 'Salaried';
      case 'self_employed':
        return 'Self-Employed';
      case 'other':
        return 'Other';
      default:
        return wt.replace(/_/g, ' ');
    }
  };

  const formatStatusLabel = (s: string) => {
    return s.replace(/_/g, ' ').toUpperCase();
  };

  return (
    <div
      className="card"
      style={{
        padding: '1.25rem',
        marginBottom: '1.5rem',
        backgroundColor: '#ffffff',
      }}
    >
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
          gap: '1rem',
          alignItems: 'flex-end',
        }}
      >
        {/* Search input */}
        <div className="form-group" style={{ margin: 0 }}>
          <label htmlFor="caller-search-input" className="form-label" style={{ fontSize: '0.8125rem' }}>
            Search this page
          </label>
          <input
            id="caller-search-input"
            type="text"
            className="form-input"
            placeholder="Search by applicant name or ref..."
            value={filters.searchTerm}
            onChange={(e) => onFilterChange({ ...filters, searchTerm: e.target.value })}
            style={{ width: '100%', fontSize: '0.875rem' }}
          />
        </div>

        {/* Status filter dropdown */}
        <div className="form-group" style={{ margin: 0 }}>
          <label htmlFor="caller-status-filter" className="form-label" style={{ fontSize: '0.8125rem' }}>
            Filter by Status
          </label>
          <select
            id="caller-status-filter"
            className="form-input"
            value={filters.statusFilter}
            onChange={(e) => onFilterChange({ ...filters, statusFilter: e.target.value })}
            style={{ width: '100%', fontSize: '0.875rem' }}
          >
            <option value="">All Statuses</option>
            {availableStatuses.map((st) => (
              <option key={st} value={st}>
                {formatStatusLabel(st)}
              </option>
            ))}
          </select>
        </div>

        {/* Work type filter dropdown */}
        <div className="form-group" style={{ margin: 0 }}>
          <label htmlFor="caller-work-type-filter" className="form-label" style={{ fontSize: '0.8125rem' }}>
            Filter by Employment Type
          </label>
          <select
            id="caller-work-type-filter"
            className="form-input"
            value={filters.workTypeFilter}
            onChange={(e) => onFilterChange({ ...filters, workTypeFilter: e.target.value })}
            style={{ width: '100%', fontSize: '0.875rem' }}
          >
            <option value="">All Work Types</option>
            {availableWorkTypes.map((wt) => (
              <option key={wt} value={wt}>
                {formatWorkTypeLabel(wt)}
              </option>
            ))}
          </select>
        </div>

        {/* Clear Filters button */}
        {hasActiveFilters && (
          <div>
            <button
              type="button"
              className="btn btn-outline"
              onClick={onClearFilters}
              style={{ fontSize: '0.8125rem', padding: '0.625rem 1rem', height: '40px' }}
            >
              Clear Filters
            </button>
          </div>
        )}
      </div>

      <div style={{ marginTop: '0.625rem', fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>
        Note: Search and filters apply exclusively to records loaded on this page view.
      </div>
    </div>
  );
};
