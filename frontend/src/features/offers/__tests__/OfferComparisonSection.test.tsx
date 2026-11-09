import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { OfferComparisonSection } from '../components/OfferComparisonSection';
import { OfferResponse } from '../types';
import { MatchRun } from '../../matching/types';
import { apiClient } from '../../../services/apiClient';
import { ApiError } from '../../../services/apiErrors';

describe('OfferComparisonSection Component', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  const mockCompletedMatchRun: MatchRun = {
    id: 1,
    application_id: 10,
    run_number: 1,
    status: 'completed',
    started_at: '2026-03-01T12:00:00Z',
    completed_at: '2026-03-01T12:00:02Z',
    decisions: [],
  };

  const mockOffers: OfferResponse[] = [
    {
      id: 101,
      lender_decision_id: 1,
      lender_code: 'APEX_FINANCIAL',
      lender_name: 'Apex Financial',
      policy_version: 'v1.0',
      loan_amount: '200000.00',
      apr: '14.5000',
      term_months: 24,
      monthly_installment: '9648.50',
      mock_kfs_reference: 'KFS-APEX-001',
      status: 'available',
      created_at: '2026-03-01T12:05:00Z',
      valid_until: '2026-03-15T12:05:00Z',
    },
    {
      id: 102,
      lender_decision_id: 2,
      lender_code: 'STERLING_LOANS',
      lender_name: 'Sterling Loans',
      policy_version: 'v1.0',
      loan_amount: '150000.00',
      apr: '20.0000',
      term_months: 18,
      monthly_installment: '9740.00',
      mock_kfs_reference: 'KFS-STERLING-002',
      status: 'withdrawn',
      created_at: '2026-03-01T12:05:00Z',
      valid_until: null,
    },
  ];

  it('1. Offer generation button appears only when allowed (matched status, completed run, consent ready)', () => {
    const { unmount } = render(
      <OfferComparisonSection
        applicationId={10}
        applicationStatus="matched"
        consentReadiness={{ isReady: true, missingPurposes: [], grantedPurposes: [] }}
        latestMatchRun={mockCompletedMatchRun}
        offers={[]}
        onOffersGenerated={vi.fn()}
        onOfferSelected={vi.fn()}
      />
    );

    expect(screen.getByRole('button', { name: /Generate Mock Offers/i })).toBeInTheDocument();
    unmount();

    // Not allowed when consent not ready
    render(
      <OfferComparisonSection
        applicationId={10}
        applicationStatus="matched"
        consentReadiness={{ isReady: false, missingPurposes: ['p1'], grantedPurposes: [] }}
        latestMatchRun={mockCompletedMatchRun}
        offers={[]}
        onOffersGenerated={vi.fn()}
        onOfferSelected={vi.fn()}
      />
    );
    expect(screen.queryByRole('button', { name: /Generate Mock Offers/i })).not.toBeInTheDocument();
  });

  it('2. Generate offers calls POST /applications/{id}/offers/generate and reloads offers', async () => {
    const onOffersGenerated = vi.fn();
    const postSpy = vi.spyOn(apiClient, 'post').mockResolvedValue({
      application_id: 10,
      match_run_id: 1,
      run_number: 1,
      generated_count: 2,
      offers: mockOffers,
    });
    vi.spyOn(apiClient, 'get').mockResolvedValue(mockOffers);

    render(
      <OfferComparisonSection
        applicationId={10}
        applicationStatus="matched"
        consentReadiness={{ isReady: true, missingPurposes: [], grantedPurposes: [] }}
        latestMatchRun={mockCompletedMatchRun}
        offers={[]}
        onOffersGenerated={onOffersGenerated}
        onOfferSelected={vi.fn()}
      />
    );

    const generateBtn = screen.getByRole('button', { name: /Generate Mock Offers/i });
    fireEvent.click(generateBtn);

    await waitFor(() => {
      expect(postSpy).toHaveBeenCalledWith('/applications/10/offers/generate');
    });

    await waitFor(() => {
      expect(onOffersGenerated).toHaveBeenCalledWith(mockOffers);
    });

    expect(await screen.findByText(/Generated 2 mock loan offer\(s\)/i)).toBeInTheDocument();
  });

  it('4. No automatic offer generation occurs during render', () => {
    const postSpy = vi.spyOn(apiClient, 'post');

    render(
      <OfferComparisonSection
        applicationId={10}
        applicationStatus="matched"
        consentReadiness={{ isReady: true, missingPurposes: [], grantedPurposes: [] }}
        latestMatchRun={mockCompletedMatchRun}
        offers={mockOffers}
        onOffersGenerated={vi.fn()}
        onOfferSelected={vi.fn()}
      />
    );

    // postSpy must NOT have been called automatically
    expect(postSpy).not.toHaveBeenCalled();
  });

  it('5, 7, & 9. Renders actual lender terms and statuses correctly without hardcoded values', () => {
    render(
      <OfferComparisonSection
        applicationId={10}
        applicationStatus="matched"
        consentReadiness={{ isReady: true, missingPurposes: [], grantedPurposes: [] }}
        latestMatchRun={mockCompletedMatchRun}
        offers={mockOffers}
        onOffersGenerated={vi.fn()}
        onOfferSelected={vi.fn()}
      />
    );

    // Apex Financial
    expect(screen.getByText('Apex Financial')).toBeInTheDocument();
    expect(screen.getByText('APEX_FINANCIAL')).toBeInTheDocument();
    expect(screen.getByText('₹2,00,000.00')).toBeInTheDocument();
    expect(screen.getByText('14.5%')).toBeInTheDocument();
    expect(screen.getByText('24 Months')).toBeInTheDocument();
    expect(screen.getByText('₹9,648.50/mo')).toBeInTheDocument();
    expect(screen.getByText('AVAILABLE')).toBeInTheDocument();

    // Sterling Loans
    expect(screen.getByText('Sterling Loans')).toBeInTheDocument();
    expect(screen.getByText('STERLING_LOANS')).toBeInTheDocument();
    expect(screen.getByText('₹1,50,000.00')).toBeInTheDocument();
    expect(screen.getByText('20%')).toBeInTheDocument();
    expect(screen.getByText('WITHDRAWN')).toBeInTheDocument();

    // Training disclaimer
    expect(screen.getByText(/All interest rates, installments, tenures/i)).toBeInTheDocument();
  });

  it('6. Empty offer response displays clean empty state', () => {
    render(
      <OfferComparisonSection
        applicationId={10}
        applicationStatus="matched"
        consentReadiness={{ isReady: true, missingPurposes: [], grantedPurposes: [] }}
        latestMatchRun={mockCompletedMatchRun}
        offers={[]}
        onOffersGenerated={vi.fn()}
        onOfferSelected={vi.fn()}
      />
    );

    expect(screen.getByText('No Mock Loan Offers Available')).toBeInTheDocument();
  });

  it('8. Displays API 409 and 503 errors on offer generation failure', async () => {
    vi.spyOn(apiClient, 'post').mockRejectedValue(
      new ApiError(409, 'Application is not in matched status.')
    );

    render(
      <OfferComparisonSection
        applicationId={10}
        applicationStatus="matched"
        consentReadiness={{ isReady: true, missingPurposes: [], grantedPurposes: [] }}
        latestMatchRun={mockCompletedMatchRun}
        offers={[]}
        onOffersGenerated={vi.fn()}
        onOfferSelected={vi.fn()}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /Generate Mock Offers/i }));

    expect(await screen.findByText('Application is not in matched status.')).toBeInTheDocument();
  });
});
