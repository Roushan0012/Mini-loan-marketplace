import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ApplicationDetailPage } from '../pages/ApplicationDetailPage';
import { apiClient } from '../../../services/apiClient';
import { ApiError } from '../../../services/apiErrors';
import { LoanApplication } from '../types';
import { ConsentNotice, ConsentRecord } from '../../consents/types';
import { MatchRunSummary } from '../../matching/types';

describe('ApplicationDetailPage Component', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  const mockDraftApplication: LoanApplication = {
    id: 42,
    age: 28,
    monthly_income: '50000.00',
    work_type: 'salaried',
    requested_amount: '200000.00',
    status: 'draft',
    created_at: '2026-03-01T12:00:00Z',
    updated_at: '2026-03-01T12:00:00Z',
  };

  const mockNotices: ConsentNotice[] = [
    {
      purpose: 'eligibility_matching',
      title: 'Credit Assessment & Eligibility Notice',
      notice_version: 'v1.0',
      notice_text: 'Terms for eligibility evaluation.',
      required_for_matching: true,
    },
    {
      purpose: 'sharing_with_mock_lenders',
      title: 'Lender Information Sharing Notice',
      notice_version: 'v1.0',
      notice_text: 'Terms for sharing with mock lenders.',
      required_for_matching: true,
    },
  ];

  const mockConsentHistory: ConsentRecord[] = [];
  const mockMatchSummary: MatchRunSummary = { total_runs: 0, runs: [] };

  const renderComponent = (appId = '42') =>
    render(
      <MemoryRouter initialEntries={[`/customer/applications/${appId}`]}>
        <Routes>
          <Route path="/customer/applications/:applicationId" element={<ApplicationDetailPage />} />
          <Route path="/customer/dashboard" element={<div>Customer Dashboard Page</div>} />
        </Routes>
      </MemoryRouter>
    );

  it('9. Application detail loads from GET endpoint and displays data', async () => {
    vi.spyOn(apiClient, 'get').mockImplementation(async (url) => {
      if (url === '/applications/42') return mockDraftApplication;
      if (url === '/consents/notices') return mockNotices;
      if (url === '/applications/42/consents') return mockConsentHistory;
      if (url === '/applications/42/matches') return mockMatchSummary;
      throw new Error(`Unhandled endpoint: ${url}`);
    });

    renderComponent('42');

    expect(await screen.findByRole('heading', { name: /Application #42/i })).toBeInTheDocument();
    expect(screen.getAllByText('DRAFT').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByDisplayValue('28')).toBeInTheDocument();
    expect(screen.getByDisplayValue('50000.00')).toBeInTheDocument();
    expect(screen.getByDisplayValue('200000.00')).toBeInTheDocument();
  });

  it('10. Draft application allows editing form inputs', async () => {
    vi.spyOn(apiClient, 'get').mockImplementation(async (url) => {
      if (url === '/applications/42') return mockDraftApplication;
      if (url === '/consents/notices') return mockNotices;
      if (url === '/applications/42/consents') return mockConsentHistory;
      if (url === '/applications/42/matches') return mockMatchSummary;
      throw new Error(`Unhandled endpoint: ${url}`);
    });

    renderComponent('42');

    expect(await screen.findByRole('button', { name: /Save Changes/i })).toBeInTheDocument();

    const ageInput = screen.getByLabelText(/Age \(Years\)/i) as HTMLInputElement;
    fireEvent.change(ageInput, { target: { value: '35' } });
    expect(ageInput.value).toBe('35');
  });

  it('11. PATCH sends only allowed fields without customer_id or status', async () => {
    vi.spyOn(apiClient, 'get').mockImplementation(async (url) => {
      if (url === '/applications/42') return mockDraftApplication;
      if (url === '/consents/notices') return mockNotices;
      if (url === '/applications/42/consents') return mockConsentHistory;
      if (url === '/applications/42/matches') return mockMatchSummary;
      throw new Error(`Unhandled endpoint: ${url}`);
    });

    const patchSpy = vi.spyOn(apiClient, 'patch').mockResolvedValue({
      ...mockDraftApplication,
      age: 35,
      requested_amount: '250000.00',
      updated_at: '2026-03-01T13:00:00Z',
    });

    renderComponent('42');

    await screen.findByRole('heading', { name: /Application #42/i });

    fireEvent.change(screen.getByLabelText(/Age \(Years\)/i), { target: { value: '35' } });
    fireEvent.change(screen.getByLabelText(/Requested Loan Amount \(₹\)/i), { target: { value: '250000.00' } });

    fireEvent.click(screen.getByRole('button', { name: /Save Changes/i }));

    await waitFor(() => {
      expect(patchSpy).toHaveBeenCalledTimes(1);
    });

    const [endpoint, payload] = patchSpy.mock.calls[0];
    expect(endpoint).toBe('/applications/42');
    expect(payload).toEqual({
      age: 35,
      monthly_income: '50000.00',
      work_type: 'salaried',
      requested_amount: '250000.00',
    });

    const payloadKeys = Object.keys(payload as object);
    expect(payloadKeys).not.toContain('customer_id');
    expect(payloadKeys).not.toContain('status');
    expect(payloadKeys).not.toContain('id');

    expect(await screen.findByText('✓ Draft application updated successfully.')).toBeInTheDocument();
  });

  it('12. Non-draft application is strictly read-only', async () => {
    const mockMatchedApp: LoanApplication = {
      ...mockDraftApplication,
      status: 'matched',
    };

    vi.spyOn(apiClient, 'get').mockImplementation(async (url) => {
      if (url === '/applications/42') return mockMatchedApp;
      if (url === '/consents/notices') return mockNotices;
      if (url === '/applications/42/consents') return mockConsentHistory;
      if (url === '/applications/42/matches') return mockMatchSummary;
      throw new Error(`Unhandled endpoint: ${url}`);
    });

    renderComponent('42');

    expect(await screen.findByText(/is locked for editing/i)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Save Changes/i })).not.toBeInTheDocument();

    // Verify static values rendered
    expect(screen.getByText('28 years')).toBeInTheDocument();
    expect(screen.getByText('Salaried Employee')).toBeInTheDocument();
    expect(screen.getByText(/50,000\.00/)).toBeInTheDocument();
    expect(screen.getByText(/2,00,000\.00/)).toBeInTheDocument();
  });

  it('13. Displays API 409 error when draft modification is rejected', async () => {
    vi.spyOn(apiClient, 'get').mockImplementation(async (url) => {
      if (url === '/applications/42') return mockDraftApplication;
      if (url === '/consents/notices') return mockNotices;
      if (url === '/applications/42/consents') return mockConsentHistory;
      if (url === '/applications/42/matches') return mockMatchSummary;
      throw new Error(`Unhandled endpoint: ${url}`);
    });

    vi.spyOn(apiClient, 'patch').mockRejectedValue(
      new ApiError(409, 'Application is no longer in draft status and cannot be modified.')
    );

    renderComponent('42');

    await screen.findByRole('heading', { name: /Application #42/i });

    fireEvent.change(screen.getByLabelText(/Age \(Years\)/i), { target: { value: '31' } });
    fireEvent.click(screen.getByRole('button', { name: /Save Changes/i }));

    expect(
      await screen.findByText('Application is no longer in draft status and cannot be modified.')
    ).toBeInTheDocument();
  });

  it('14. Safely displays 404 when application is not found or unauthorized', async () => {
    vi.spyOn(apiClient, 'get').mockRejectedValue(
      new ApiError(404, 'Loan application not found.')
    );

    renderComponent('999');

    expect(
      await screen.findByText('Loan application not found or you do not have permission to access it.')
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Back to Dashboard/i })).toBeInTheDocument();
  });
});
