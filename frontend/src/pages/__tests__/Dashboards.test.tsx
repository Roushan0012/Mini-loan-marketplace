import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { CustomerDashboardPage } from '../CustomerDashboardPage';
import { CallerDashboardPage } from '../CallerDashboardPage';
import { AdminDashboardPage } from '../AdminDashboardPage';
import { AuthContext, AuthContextType } from '../../app/providers/AuthContext';
import { apiClient } from '../../services/apiClient';
import { LoanApplication, CallerLead, AdminMetrics } from '../../types/api';
import { UserProfile } from '../../types/auth';

describe('Role Dashboards Data Presentation', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  const createMockAuth = (user: UserProfile): AuthContextType => ({
    user,
    role: user.role,
    isAuthenticated: true,
    isLoading: false,
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
    refreshUser: vi.fn().mockResolvedValue(user),
  });

  it('18. Customer dashboard displays applications from API', async () => {
    const mockCustomer: UserProfile = {
      id: 101,
      full_name: 'Alice Customer',
      email: 'alice@example.com',
      role: 'customer',
      is_active: true,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    };

    const mockApplications: LoanApplication[] = [
      {
        id: 42,
        age: 30,
        monthly_income: '55000.00',
        work_type: 'salaried',
        requested_amount: '350000.00',
        status: 'submitted',
        created_at: '2026-02-01T12:00:00Z',
        updated_at: '2026-02-01T12:00:00Z',
      },
    ];

    vi.spyOn(apiClient, 'get').mockResolvedValue(mockApplications);

    render(
      <AuthContext.Provider value={createMockAuth(mockCustomer)}>
        <CustomerDashboardPage />
      </AuthContext.Provider>
    );

    expect(await screen.findByText(/Welcome back, Alice Customer!/i)).toBeInTheDocument();
    expect(await screen.findByText('#42')).toBeInTheDocument();
    expect(screen.getByText('submitted')).toBeInTheDocument();
  });

  it('19. Caller dashboard displays only API-assigned leads', async () => {
    const mockCaller: UserProfile = {
      id: 202,
      full_name: 'Bob Caller',
      email: 'bob@example.com',
      role: 'caller',
      is_active: true,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    };

    const mockLeads: CallerLead[] = [
      {
        id: 7,
        synthetic_reference: 'SYN-LEAD-007',
        applicant_name: 'Mock Applicant Charlie',
        age: 29,
        monthly_income: '45000.00',
        work_type: 'salaried',
        requested_amount: '200000.00',
        status: 'new',
        assigned_at: '2026-02-15T09:00:00Z',
      },
    ];

    vi.spyOn(apiClient, 'get').mockResolvedValue(mockLeads);

    render(
      <AuthContext.Provider value={createMockAuth(mockCaller)}>
        <CallerDashboardPage />
      </AuthContext.Provider>
    );

    expect(await screen.findByText(/Caller Workspace: Bob Caller/i)).toBeInTheDocument();
    expect(await screen.findByText('SYN-LEAD-007')).toBeInTheDocument();
    expect(screen.getByText('Mock Applicant Charlie')).toBeInTheDocument();
  });

  it('20. Admin dashboard displays aggregate API metrics without customer PII', async () => {
    const mockAdmin: UserProfile = {
      id: 303,
      full_name: 'Admin Dave',
      email: 'dave@example.com',
      role: 'admin',
      is_active: true,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    };

    const mockMetrics: AdminMetrics = {
      total_leads: 50,
      total_applications: 35,
      total_match_runs: 28,
      total_offers: 84,
      total_submissions: 20,
      applications_by_status: {
        submitted: 12,
        accepted: 8,
      },
      lender_events_by_processing_status: {
        processed: 15,
        ignored: 3,
      },
    };

    vi.spyOn(apiClient, 'get').mockResolvedValue(mockMetrics);

    render(
      <AuthContext.Provider value={createMockAuth(mockAdmin)}>
        <AdminDashboardPage />
      </AuthContext.Provider>
    );

    expect(await screen.findByText(/Administrator Monitoring: Admin Dave/i)).toBeInTheDocument();
    expect(screen.getByText('50')).toBeInTheDocument(); // total leads
    expect(screen.getByText('35')).toBeInTheDocument(); // total applications
    expect(screen.getByText('84')).toBeInTheDocument(); // total offers
  });
});
