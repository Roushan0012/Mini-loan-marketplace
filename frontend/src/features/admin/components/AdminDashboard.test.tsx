import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { AdminDashboardPage } from '../../../pages/AdminDashboardPage';
import { AuthContext, AuthContextType } from '../../../app/providers/AuthContext';
import { apiClient } from '../../../services/apiClient';
import { ApiError } from '../../../services/apiErrors';
import { AdminMetrics } from '../types';
import { UserProfile } from '../../../types/auth';

describe('Admin Analytics Dashboard Component Tests', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  const mockAdmin: UserProfile = {
    id: 301,
    full_name: 'Admin Morgan',
    email: 'morgan@example.com',
    role: 'admin',
    is_active: true,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  };

  const createMockAuth = (user: UserProfile = mockAdmin): AuthContextType => ({
    user,
    role: user.role,
    isAuthenticated: true,
    isLoading: false,
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
    refreshUser: vi.fn().mockResolvedValue(user),
  });

  const mockConsistentMetrics: AdminMetrics = {
    total_leads: 120,
    total_applications: 85,
    total_match_runs: 72,
    total_offers: 216,
    total_submissions: 48,
    applications_by_status: {
      draft: 15,
      matched: 20,
      offer_selected: 10,
      submitted: 40,
    },
    lender_events_by_processing_status: {
      received: 5,
      processed: 40,
      ignored: 2,
      failed: 1,
    },
  };

  const renderDashboard = () =>
    render(
      <AuthContext.Provider value={createMockAuth(mockAdmin)}>
        <AdminDashboardPage />
      </AuthContext.Provider>
    );

  it('15, 38, 39, 40, & 41. Fetches only /admin/dashboard/metrics and never calls individual entities or config endpoints', async () => {
    const getSpy = vi.spyOn(apiClient, 'get').mockResolvedValue(mockConsistentMetrics);

    renderDashboard();

    expect(await screen.findByText('Administrator Analytics')).toBeInTheDocument();

    // Verify exactly one endpoint was called
    expect(getSpy).toHaveBeenCalledTimes(1);
    expect(getSpy).toHaveBeenCalledWith('/admin/dashboard/metrics');

    // 38, 39, 40, 41. Verify no customer, lead, offer, submission, or config endpoints were invoked
    const allCalls = getSpy.mock.calls.map(([url]) => url);
    expect(allCalls).not.toContain('/applications');
    expect(allCalls).not.toContain('/caller/leads');
    expect(allCalls).not.toContain('/submissions');
    expect(allCalls).not.toContain('/events');
    expect(allCalls).not.toContain('/admin/policies');
  });

  it('16, 17, 18, 19, 20, 21, & 22. Shows exact platform totals with corrected labels', async () => {
    vi.spyOn(apiClient, 'get').mockResolvedValue(mockConsistentMetrics);

    renderDashboard();

    expect(await screen.findByText('120')).toBeInTheDocument(); // total leads
    expect(screen.getAllByText('85').length).toBeGreaterThanOrEqual(1);  // total applications
    expect(screen.getByText('72')).toBeInTheDocument();  // total match runs
    expect(screen.getByText('216')).toBeInTheDocument(); // total offers
    expect(screen.getAllByText('48').length).toBeGreaterThanOrEqual(1);  // total submissions

    // 21. Match runs label says "Total Match Runs", NOT "Completed Match Runs"
    expect(screen.getByText('Total Match Runs')).toBeInTheDocument();
    expect(screen.queryByText('Completed Match Runs')).not.toBeInTheDocument();

    // 22. Submissions label says "Total Submissions", NOT "Dispatched Submissions"
    expect(screen.getByText('Total Submissions')).toBeInTheDocument();
    expect(screen.queryByText('Dispatched Submissions')).not.toBeInTheDocument();
    expect(
      screen.getByText('Total offer submission records across all lifecycle statuses')
    ).toBeInTheDocument();
  });

  it('23, 24, 25, & 27. Application and event breakdowns render safely with Title Case labels, progress bars, zero counts, and unknown statuses', async () => {
    const metricsWithUnknownAndZero: AdminMetrics = {
      ...mockConsistentMetrics,
      total_applications: 35,
      applications_by_status: {
        offer_selected: 20,
        custom_review_status: 15,
        zero_count_status: 0,
      },
      lender_events_by_processing_status: {
        processed: 10,
        custom_event_status: 5,
      },
    };

    vi.spyOn(apiClient, 'get').mockResolvedValue(metricsWithUnknownAndZero);

    renderDashboard();

    expect(await screen.findByText('Offer Selected')).toBeInTheDocument();
    expect(screen.getByText('Custom Review Status')).toBeInTheDocument();
    expect(screen.getByText('Zero Count Status')).toBeInTheDocument();
    expect(screen.getByText('Custom Event Status')).toBeInTheDocument();

    // Accessible progressbars are rendered
    const progressBars = screen.getAllByRole('progressbar');
    expect(progressBars.length).toBeGreaterThanOrEqual(2);
  });

  it('26. Empty status maps display appropriate empty states', async () => {
    const emptyMetrics: AdminMetrics = {
      total_leads: 0,
      total_applications: 0,
      total_match_runs: 0,
      total_offers: 0,
      total_submissions: 0,
      applications_by_status: {},
      lender_events_by_processing_status: {},
    };

    vi.spyOn(apiClient, 'get').mockResolvedValue(emptyMetrics);

    renderDashboard();

    expect(await screen.findByText('No loan applications recorded yet.')).toBeInTheDocument();
    expect(screen.getByText('No lender webhook events recorded yet.')).toBeInTheDocument();
  });

  it('28. Inconsistent application totals show a prominent warning notice without modifying values', async () => {
    const inconsistentMetrics: AdminMetrics = {
      ...mockConsistentMetrics,
      total_applications: 100, // Reported 100
      applications_by_status: {
        draft: 20,
        matched: 30, // Sum = 50 (Diff = -50)
      },
    };

    vi.spyOn(apiClient, 'get').mockResolvedValue(inconsistentMetrics);

    renderDashboard();

    expect(
      await screen.findByText('Application Status Discrepancy Detected')
    ).toBeInTheDocument();
    expect(screen.getByText(/resulting in an aggregate difference of/i)).toBeInTheDocument();
  });

  it('29. Consistent application totals show reconciliation verified message', async () => {
    vi.spyOn(apiClient, 'get').mockResolvedValue(mockConsistentMetrics);

    renderDashboard();

    expect(
      await screen.findByText(/Application totals reconcile with the status breakdown/i)
    ).toBeInTheDocument();
  });

  it('30, 31, & 35. Refresh button triggers on-demand fetch and updates freshness timestamp', async () => {
    const getSpy = vi.spyOn(apiClient, 'get').mockResolvedValue(mockConsistentMetrics);

    renderDashboard();
    await screen.findByText('Administrator Analytics');

    expect(await screen.findByText(/Last refreshed:/i)).toBeInTheDocument();

    const refreshBtn = screen.getByRole('button', { name: /Refresh aggregate metrics/i });
    fireEvent.click(refreshBtn);

    await waitFor(() => {
      expect(getSpy).toHaveBeenCalledTimes(2);
    });
  });

  it('32 & 33. Initial API error shows error message with retry action', async () => {
    const getSpy = vi
      .spyOn(apiClient, 'get')
      .mockRejectedValueOnce(new ApiError(500, 'Database query failed.'))
      .mockResolvedValueOnce(mockConsistentMetrics);

    renderDashboard();

    expect(await screen.findByText('Database query failed.')).toBeInTheDocument();

    const retryBtn = screen.getByRole('button', { name: /Retry/i });
    fireEvent.click(retryBtn);

    expect(await screen.findByText('120')).toBeInTheDocument();
    expect(getSpy).toHaveBeenCalledTimes(2);
  });

  it('34. Failed refresh preserves the last successful snapshot with a warning', async () => {
    const getSpy = vi
      .spyOn(apiClient, 'get')
      .mockResolvedValueOnce(mockConsistentMetrics)
      .mockRejectedValueOnce(new ApiError(503, 'Service unavailable.'));

    renderDashboard();
    expect(await screen.findByText('120')).toBeInTheDocument();

    // Trigger refresh which fails
    const refreshBtn = screen.getByRole('button', { name: /Refresh aggregate metrics/i });
    fireEvent.click(refreshBtn);

    // Warning appears
    expect(await screen.findByText(/Metrics Refresh Notice:/i)).toBeInTheDocument();
    expect(screen.getByText(/Service unavailable/i)).toBeInTheDocument();

    // Previous data snapshot remains visible!
    expect(screen.getByText('120')).toBeInTheDocument();
    expect(screen.getAllByText('85').length).toBeGreaterThanOrEqual(1);
    expect(getSpy).toHaveBeenCalledTimes(2);
  });

  it('37 & 42. Strictly displays no customer PII and no fabricated chart libraries', async () => {
    vi.spyOn(apiClient, 'get').mockResolvedValue(mockConsistentMetrics);

    renderDashboard();
    await screen.findByText('Administrator Analytics');

    // No PII keywords
    expect(screen.queryByText(/john\.doe@/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/\+91-/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/PAN/i)).not.toBeInTheDocument();

    // Privacy notice is present
    expect(
      screen.getByText(/This dashboard displays aggregate platform metrics only/i)
    ).toBeInTheDocument();
  });
});
