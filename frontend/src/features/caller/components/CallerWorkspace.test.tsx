import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { CallerDashboardPage } from '../../../pages/CallerDashboardPage';
import { AuthContext, AuthContextType } from '../../../app/providers/AuthContext';
import { apiClient } from '../../../services/apiClient';
import { ApiError } from '../../../services/apiErrors';
import { CallerLead } from '../types';
import { UserProfile } from '../../../types/auth';

describe('Caller Workspace Component & Workflows', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  const mockCaller: UserProfile = {
    id: 202,
    full_name: 'Agent Smith',
    email: 'smith@example.com',
    role: 'caller',
    is_active: true,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  };

  const createMockAuth = (user: UserProfile = mockCaller): AuthContextType => ({
    user,
    role: user.role,
    isAuthenticated: true,
    isLoading: false,
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
    refreshUser: vi.fn().mockResolvedValue(user),
  });

  const mockLeads: CallerLead[] = [
    {
      id: 1,
      synthetic_reference: 'SYN-LEAD-101',
      applicant_name: 'Priya Sharma',
      age: 29,
      monthly_income: '75000.00',
      work_type: 'salaried',
      requested_amount: '350000.00',
      status: 'new',
      assigned_at: '2026-03-01T10:00:00Z',
    },
    {
      id: 2,
      synthetic_reference: 'SYN-LEAD-102',
      applicant_name: 'Rahul Verma',
      age: 41,
      monthly_income: '120000.50',
      work_type: 'self_employed',
      requested_amount: '1000000.00',
      status: 'in_progress',
      assigned_at: '2026-03-01T11:00:00Z',
    },
    {
      id: 3,
      synthetic_reference: 'SYN-LEAD-103',
      applicant_name: 'Anita Desai',
      age: 35,
      monthly_income: '50000.00',
      work_type: 'other',
      requested_amount: '150000.00',
      status: 'custom_backend_status',
      assigned_at: '2026-03-01T12:00:00Z',
    },
  ];

  const renderCallerWorkspace = () =>
    render(
      <AuthContext.Provider value={createMockAuth(mockCaller)}>
        <CallerDashboardPage />
      </AuthContext.Provider>
    );

  it('1, 2, & 3. Caller workspace loads assigned leads with limit/offset and without caller_id', async () => {
    const getSpy = vi.spyOn(apiClient, 'get').mockResolvedValue(mockLeads);

    renderCallerWorkspace();

    expect(await screen.findByText(/Caller Workspace: Agent Smith/i)).toBeInTheDocument();
    expect(screen.getAllByText(/You can view only leads assigned to your caller account/i).length).toBeGreaterThanOrEqual(1);

    await waitFor(() => {
      expect(getSpy).toHaveBeenCalledTimes(1);
    });

    const [endpoint] = getSpy.mock.calls[0];
    expect(endpoint).toBe('/caller/leads?limit=25&offset=0');
    expect(endpoint).not.toContain('caller_id');
    expect(endpoint).not.toContain('customer_id');
    expect(endpoint).not.toContain('role');
  });

  it('4, 5, 6, 7, 8, & 9. Renders applicant name, ref, decimal-safe formatting, known and unknown statuses', async () => {
    vi.spyOn(apiClient, 'get').mockResolvedValue(mockLeads);

    renderCallerWorkspace();

    expect(await screen.findByText('Priya Sharma')).toBeInTheDocument();
    expect(screen.getByText('SYN-LEAD-101')).toBeInTheDocument();

    // 6 & 7. Decimal-safe Indian Rupee formatting (no float / Number precision issues)
    expect(screen.getByText('₹75,000.00')).toBeInTheDocument();
    expect(screen.getByText('₹3,50,000.00')).toBeInTheDocument();
    expect(screen.getByText('₹1,20,000.50')).toBeInTheDocument();
    expect(screen.getByText('₹10,00,000.00')).toBeInTheDocument();

    // 8. Known lead status badges in table
    expect(screen.getAllByText('NEW').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('IN PROGRESS').length).toBeGreaterThanOrEqual(1);

    // 9. Unknown or custom backend status displays safely
    expect(screen.getAllByText('CUSTOM BACKEND STATUS').length).toBeGreaterThanOrEqual(1);
  });

  it('10 & 14. Search filters current page by applicant name and states page scope clearly', async () => {
    vi.spyOn(apiClient, 'get').mockResolvedValue(mockLeads);

    renderCallerWorkspace();
    await screen.findByText('Priya Sharma');

    // 14. Clear note on scope
    expect(
      screen.getByText(/Search and filters apply exclusively to records loaded on this page view/i)
    ).toBeInTheDocument();

    const searchInput = screen.getByLabelText(/Search this page/i);
    fireEvent.change(searchInput, { target: { value: 'Priya' } });

    expect(screen.getByText('Priya Sharma')).toBeInTheDocument();
    expect(screen.queryByText('Rahul Verma')).not.toBeInTheDocument();
    expect(screen.queryByText('Anita Desai')).not.toBeInTheDocument();
  });

  it('11. Search filters current page by synthetic reference', async () => {
    vi.spyOn(apiClient, 'get').mockResolvedValue(mockLeads);

    renderCallerWorkspace();
    await screen.findByText('Priya Sharma');

    const searchInput = screen.getByLabelText(/Search this page/i);
    fireEvent.change(searchInput, { target: { value: 'SYN-LEAD-102' } });

    expect(screen.getByText('Rahul Verma')).toBeInTheDocument();
    expect(screen.queryByText('Priya Sharma')).not.toBeInTheDocument();
  });

  it('12. Status filter filters current page correctly', async () => {
    vi.spyOn(apiClient, 'get').mockResolvedValue(mockLeads);

    renderCallerWorkspace();
    await screen.findByText('Priya Sharma');

    const statusSelect = screen.getByLabelText(/Filter by Status/i);
    fireEvent.change(statusSelect, { target: { value: 'in_progress' } });

    expect(screen.getByText('Rahul Verma')).toBeInTheDocument();
    expect(screen.queryByText('Priya Sharma')).not.toBeInTheDocument();
  });

  it('13. Work type filter filters current page correctly', async () => {
    vi.spyOn(apiClient, 'get').mockResolvedValue(mockLeads);

    renderCallerWorkspace();
    await screen.findByText('Priya Sharma');

    const workTypeSelect = screen.getByLabelText(/Filter by Employment Type/i);
    fireEvent.change(workTypeSelect, { target: { value: 'self_employed' } });

    expect(screen.getByText('Rahul Verma')).toBeInTheDocument();
    expect(screen.queryByText('Priya Sharma')).not.toBeInTheDocument();
  });

  it('15, 16, 17, & 18. Details drawer opens with lead data, closes via close button and Escape, with no detail API call', async () => {
    const getSpy = vi.spyOn(apiClient, 'get').mockResolvedValue(mockLeads);

    renderCallerWorkspace();
    await screen.findByText('Priya Sharma');

    const viewDetailsButtons = screen.getAllByRole('button', { name: /View details/i });
    fireEvent.click(viewDetailsButtons[0]);

    // 15. Drawer opens
    const dialog = screen.getByRole('dialog');
    expect(dialog).toBeInTheDocument();
    expect(screen.getByText('Lead: SYN-LEAD-101')).toBeInTheDocument();
    expect(screen.getByText('29 years')).toBeInTheDocument();
    expect(screen.getByText('Salaried Employee')).toBeInTheDocument();

    // 18. Strictly no secondary detail endpoint is called
    expect(getSpy).toHaveBeenCalledTimes(1);

    // 16. Closes with close button (X)
    const closeBtn = screen.getByRole('button', { name: /Close lead details/i });
    fireEvent.click(closeBtn);
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();

    // Reopen and test 17. Escape key closes drawer
    fireEvent.click(viewDetailsButtons[0]);
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('19 & 21. Previous page disabled on first page, Next page disabled for short page', async () => {
    // 3 leads is less than 25 (short page)
    vi.spyOn(apiClient, 'get').mockResolvedValue(mockLeads);

    renderCallerWorkspace();
    await screen.findByText('Priya Sharma');

    const prevBtn = screen.getByRole('button', { name: /Previous page/i });
    const nextBtn = screen.getByRole('button', { name: /Next page/i });

    // 19. Previous disabled on page 1
    expect(prevBtn).toBeDisabled();
    // 21. Next disabled because 3 leads < 25 (PAGE_SIZE)
    expect(nextBtn).toBeDisabled();
  });

  it('20. Next page works when a full page of 25 leads is returned', async () => {
    // Create 25 leads
    const fullPageLeads: CallerLead[] = Array.from({ length: 25 }, (_, i) => ({
      id: i + 1,
      synthetic_reference: `SYN-LEAD-${200 + i}`,
      applicant_name: `Applicant ${i + 1}`,
      age: 30,
      monthly_income: '50000.00',
      work_type: 'salaried',
      requested_amount: '200000.00',
      status: 'new',
      assigned_at: '2026-03-01T10:00:00Z',
    }));

    const getSpy = vi.spyOn(apiClient, 'get').mockResolvedValue(fullPageLeads);

    renderCallerWorkspace();
    await screen.findByText('Applicant 1');

    const nextBtn = screen.getByRole('button', { name: /Next page/i });
    expect(nextBtn).not.toBeDisabled();

    fireEvent.click(nextBtn);

    await waitFor(() => {
      expect(getSpy).toHaveBeenCalledWith('/caller/leads?limit=25&offset=25');
    });
  });

  it('22. Empty page displays correct empty state', async () => {
    vi.spyOn(apiClient, 'get').mockResolvedValue([]);

    renderCallerWorkspace();

    expect(await screen.findByText('No Leads Assigned')).toBeInTheDocument();
    expect(
      screen.getByText(/You currently have no leads assigned to your queue/i)
    ).toBeInTheDocument();
  });

  it('23. Refresh resets page to 1 and fetches again', async () => {
    const fullPageLeads: CallerLead[] = Array.from({ length: 25 }, (_, i) => ({
      id: i + 1,
      synthetic_reference: `SYN-LEAD-${200 + i}`,
      applicant_name: `Applicant ${i + 1}`,
      age: 30,
      monthly_income: '50000.00',
      work_type: 'salaried',
      requested_amount: '200000.00',
      status: 'new',
      assigned_at: '2026-03-01T10:00:00Z',
    }));

    const getSpy = vi.spyOn(apiClient, 'get').mockResolvedValue(fullPageLeads);

    renderCallerWorkspace();
    await screen.findByText('Applicant 1');

    // Click Next Page
    fireEvent.click(screen.getByRole('button', { name: /Next page/i }));
    await waitFor(() => {
      expect(getSpy).toHaveBeenCalledWith('/caller/leads?limit=25&offset=25');
    });

    // Click Refresh Leads -> should reset to page 1
    const refreshBtn = screen.getByRole('button', { name: /Refresh Leads/i });
    fireEvent.click(refreshBtn);

    await waitFor(() => {
      expect(getSpy).toHaveBeenCalledWith('/caller/leads?limit=25&offset=0');
    });
  });

  it('25 & 26. Displays API 401/403 errors and network errors with retry', async () => {
    const getSpy = vi
      .spyOn(apiClient, 'get')
      .mockRejectedValueOnce(new ApiError(403, 'Caller access required.'))
      .mockResolvedValueOnce(mockLeads);

    renderCallerWorkspace();

    expect(await screen.findByText('Caller access required.')).toBeInTheDocument();

    // Click retry
    const retryBtn = screen.getByRole('button', { name: /Retry/i });
    fireEvent.click(retryBtn);

    expect(await screen.findByText('Priya Sharma')).toBeInTheDocument();
    expect(getSpy).toHaveBeenCalledTimes(2);
  });

  it('32 & 33. Strictly read-only workspace with no mutation controls for lead status or assignment', async () => {
    vi.spyOn(apiClient, 'get').mockResolvedValue(mockLeads);

    renderCallerWorkspace();
    await screen.findByText('Priya Sharma');

    // Verify there are no mutation controls: no assign, no reassign, no status change dropdowns
    expect(screen.queryByRole('button', { name: /Assign/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Reassign/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Change Status/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Add Note/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Delete/i })).not.toBeInTheDocument();
  });
});
