import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MatchingSection } from '../components/MatchingSection';
import { MatchHistoryList } from '../components/MatchHistoryList';
import { MatchRun } from '../types';
import { apiClient } from '../../../services/apiClient';
import { ApiError } from '../../../services/apiErrors';

describe('Matching Workflow & History UI Tests', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  const mockRun1: MatchRun = {
    id: 101,
    application_id: 5,
    run_number: 1,
    status: 'completed',
    started_at: '2026-03-01T12:00:00Z',
    completed_at: '2026-03-01T12:00:02Z',
    decisions: [
      {
        id: 1,
        lender_code: 'ALPHA_BANK',
        lender_name: 'Alpha Bank Mock Policy',
        policy_version_snapshot: 'v1.0.0',
        decision_status: 'eligible',
        exclusion_reason_code: null,
        exclusion_reason: null,
        evaluated_at: '2026-03-01T12:00:01Z',
      },
      {
        id: 2,
        lender_code: 'BETA_FINANCE',
        lender_name: 'Beta Finance Mock Policy',
        policy_version_snapshot: 'v1.0.0',
        decision_status: 'ineligible',
        exclusion_reason_code: 'MIN_INCOME_NOT_MET',
        exclusion_reason: 'Monthly income below threshold of 30,000.',
        evaluated_at: '2026-03-01T12:00:01Z',
      },
      {
        id: 3,
        lender_code: 'GAMMA_CAPITAL',
        lender_name: 'Gamma Capital Mock Policy',
        policy_version_snapshot: 'v1.0.0',
        decision_status: 'eligible',
        exclusion_reason_code: null,
        exclusion_reason: null,
        evaluated_at: '2026-03-01T12:00:01Z',
      },
    ],
  };

  const mockRun2: MatchRun = {
    id: 102,
    application_id: 5,
    run_number: 2,
    status: 'completed',
    started_at: '2026-03-01T14:00:00Z',
    completed_at: '2026-03-01T14:00:02Z',
    decisions: [
      {
        id: 4,
        lender_code: 'ALPHA_BANK',
        lender_name: 'Alpha Bank Mock Policy',
        policy_version_snapshot: 'v1.0.0',
        decision_status: 'eligible',
        exclusion_reason_code: null,
        exclusion_reason: null,
        evaluated_at: '2026-03-01T14:00:01Z',
      },
    ],
  };

  it('32. Matching button is disabled when consent readiness is not fulfilled', () => {
    const onMatchSuccess = vi.fn();

    render(
      <MatchingSection
        applicationId={5}
        applicationStatus="draft"
        consentReadiness={{
          isReady: false,
          missingPurposes: ['sharing_with_mock_lenders'],
          grantedPurposes: ['eligibility_matching'],
        }}
        onMatchingSuccess={onMatchSuccess}
      />
    );

    const matchBtn = screen.getByRole('button', { name: /Run Lender Matching/i });
    expect(matchBtn).toBeDisabled();
    expect(screen.getByText(/Consent Required/i)).toBeInTheDocument();
    expect(screen.getByText('sharing_with_mock_lenders')).toBeInTheDocument();
  });

  it('33. Matching button is disabled for non-supported application status', () => {
    const onMatchSuccess = vi.fn();

    render(
      <MatchingSection
        applicationId={5}
        applicationStatus="submitted"
        consentReadiness={{
          isReady: true,
          missingPurposes: [],
          grantedPurposes: ['eligibility_matching', 'sharing_with_mock_lenders'],
        }}
        onMatchingSuccess={onMatchSuccess}
      />
    );

    const matchBtn = screen.getByRole('button', { name: /Run Lender Matching/i });
    expect(matchBtn).toBeDisabled();
    expect(
      screen.getByText(/Matching can only be performed/i)
    ).toBeInTheDocument();
  });

  it('34 & 35. Matching executes POST /applications/{id}/match without customer ID in body', async () => {
    const onMatchSuccess = vi.fn();
    const postSpy = vi.spyOn(apiClient, 'post').mockResolvedValue(mockRun1);

    render(
      <MatchingSection
        applicationId={5}
        applicationStatus="draft"
        consentReadiness={{
          isReady: true,
          missingPurposes: [],
          grantedPurposes: ['eligibility_matching', 'sharing_with_mock_lenders'],
        }}
        onMatchingSuccess={onMatchSuccess}
      />
    );

    const matchBtn = screen.getByRole('button', { name: /Run Lender Matching/i });
    expect(matchBtn).toBeEnabled();

    fireEvent.click(matchBtn);

    await waitFor(() => {
      expect(postSpy).toHaveBeenCalledTimes(1);
    });

    const [endpoint, payload] = postSpy.mock.calls[0];
    expect(endpoint).toBe('/applications/5/match');
    // POST to match endpoint sends no body or undefined
    expect(payload).toBeUndefined();
    expect(onMatchSuccess).toHaveBeenCalledWith(mockRun1);
  });

  it('37 & 38. Renders real lender decisions with name, code, policy snapshot, status, and exclusion reasons', async () => {
    vi.spyOn(apiClient, 'post').mockResolvedValue(mockRun1);

    render(
      <MatchingSection
        applicationId={5}
        applicationStatus="draft"
        consentReadiness={{
          isReady: true,
          missingPurposes: [],
          grantedPurposes: ['eligibility_matching', 'sharing_with_mock_lenders'],
        }}
        onMatchingSuccess={vi.fn()}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /Run Lender Matching/i }));

    expect(await screen.findByText('Alpha Bank Mock Policy')).toBeInTheDocument();
    expect(screen.getByText('ALPHA_BANK')).toBeInTheDocument();
    expect(screen.getByText('Beta Finance Mock Policy')).toBeInTheDocument();
    expect(screen.getByText('BETA_FINANCE')).toBeInTheDocument();

    // Verify eligible and ineligible badges
    expect(screen.getAllByText('ELIGIBLE').length).toBe(2);
    expect(screen.getByText('INELIGIBLE')).toBeInTheDocument();

    // Verify exclusion reason displayed
    expect(screen.getByText(/MIN_INCOME_NOT_MET/)).toBeInTheDocument();
    expect(screen.getByText(/Monthly income below threshold of 30,000/)).toBeInTheDocument();

    // 45. Confirm no offers, APR, EMI, or KFS is rendered
    expect(screen.queryByText(/APR/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/EMI/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Key Facts Statement/i)).not.toBeInTheDocument();
  });

  it('39 & 40. Displays 409 error on consent conflict and triggers consent refresh callback', async () => {
    const onConsentConflict = vi.fn();
    vi.spyOn(apiClient, 'post').mockRejectedValue(
      new ApiError(409, 'Active consent missing for purpose: sharing_with_mock_lenders')
    );

    render(
      <MatchingSection
        applicationId={5}
        applicationStatus="draft"
        consentReadiness={{
          isReady: true,
          missingPurposes: [],
          grantedPurposes: ['eligibility_matching', 'sharing_with_mock_lenders'],
        }}
        onMatchingSuccess={vi.fn()}
        onConsentConflict={onConsentConflict}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /Run Lender Matching/i }));

    expect(
      await screen.findByText(/Active consent missing for purpose: sharing_with_mock_lenders/i)
    ).toBeInTheDocument();
    expect(onConsentConflict).toHaveBeenCalledTimes(1);
  });

  it('41, 42, 43, & 44. MatchHistoryList preserves historical runs, sorts newest first, and labels latest run', () => {
    // 44. Empty state when no runs
    const { unmount } = render(<MatchHistoryList runs={[]} />);
    expect(screen.getByText('No matching runs have been performed yet.')).toBeInTheDocument();
    unmount();

    // 41, 42, 43. Multi-run history
    render(<MatchHistoryList runs={[mockRun1, mockRun2]} />);

    expect(screen.getByText('Total matching executions:')).toBeInTheDocument();
    expect(screen.getByText('2')).toBeInTheDocument();

    const runCards = screen.getAllByRole('heading', { level: 4 });
    // Run #2 is newer than Run #1, so it should be listed first
    expect(runCards[0]).toHaveTextContent('Matching Run #2');
    expect(runCards[1]).toHaveTextContent('Matching Run #1');

    // "Latest Run" badge on Run #2 only
    expect(screen.getByText('Latest Run')).toBeInTheDocument();
  });
});
