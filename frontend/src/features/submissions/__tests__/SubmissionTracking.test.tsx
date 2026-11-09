import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { SubmissionStatusPanel } from '../components/SubmissionStatusPanel';
import { LenderEventTimeline } from '../components/LenderEventTimeline';
import { OfferResponse } from '../../offers/types';
import {
  LenderEventHistoryItem,
  OfferSubmissionResponse,
  OfferSubmissionStatusResponse,
} from '../types';
import { apiClient } from '../../../services/apiClient';

describe('SubmissionStatusPanel & Event Timeline Components', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    sessionStorage.clear();
  });

  const mockSelectedOffer: OfferResponse = {
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
    status: 'selected',
    created_at: '2026-03-01T12:05:00Z',
    valid_until: null,
  };

  const mockExistingSubmission: OfferSubmissionStatusResponse = {
    id: 55,
    application_id: 10,
    offer_id: 101,
    lender_code: 'APEX_FINANCIAL',
    lender_name: 'Apex Financial',
    policy_version: 'v1.0',
    status: 'submitted',
    mock_reference: 'MOCK-TXN-999',
    submitted_at: '2026-03-01T12:10:00Z',
    created_at: '2026-03-01T12:10:00Z',
    updated_at: '2026-03-01T12:10:00Z',
  };

  const mockEvents: LenderEventHistoryItem[] = [
    {
      id: 1,
      event_id: 'evt-001',
      event_type: 'lender.accepted',
      sequence_number: 1,
      processing_status: 'processed',
      occurred_at: '2026-03-01T12:15:00Z',
      received_at: '2026-03-01T12:15:01Z',
      event_payload: { reason_code: 'AUTO_APPROVAL' },
    },
  ];

  it('34. Ready to submit state renders Submit button when status is offer_selected and no submission exists', async () => {
    const onSubmissionComplete = vi.fn();
    const mockCreatedSub: OfferSubmissionResponse = {
      ...mockExistingSubmission,
      submission_result: 'created',
    };

    vi.spyOn(apiClient, 'post').mockResolvedValue(mockCreatedSub);

    render(
      <SubmissionStatusPanel
        applicationId={10}
        applicationStatus="offer_selected"
        selectedOffer={mockSelectedOffer}
        submission={null}
        events={[]}
        onSubmissionComplete={onSubmissionComplete}
        onRefresh={vi.fn()}
      />
    );

    const submitBtn = screen.getByRole('button', { name: /Submit to Mock Lender/i });
    expect(submitBtn).toBeInTheDocument();

    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(onSubmissionComplete).toHaveBeenCalledWith(mockCreatedSub);
    });
  });

  it('34 & 37. Existing submission displays status details and prevents creating another submission attempt', () => {
    render(
      <SubmissionStatusPanel
        applicationId={10}
        applicationStatus="submitted"
        selectedOffer={mockSelectedOffer}
        submission={mockExistingSubmission}
        events={[]}
        onSubmissionComplete={vi.fn()}
        onRefresh={vi.fn()}
      />
    );

    // No submit button should be rendered
    expect(screen.queryByRole('button', { name: /Submit to Mock Lender/i })).not.toBeInTheDocument();

    // Submission details rendered
    expect(screen.getByText('Apex Financial')).toBeInTheDocument();
    expect(screen.getByText('MOCK-TXN-999')).toBeInTheDocument();
    expect(screen.getByText('SUBMITTED (DISPATCHED)')).toBeInTheDocument();
  });

  it('Displays terminal outcome explanation banners correctly (accepted, declined, etc.)', () => {
    const acceptedSubmission: OfferSubmissionStatusResponse = {
      ...mockExistingSubmission,
      status: 'accepted',
    };

    const { unmount } = render(
      <SubmissionStatusPanel
        applicationId={10}
        applicationStatus="accepted"
        selectedOffer={mockSelectedOffer}
        submission={acceptedSubmission}
        events={mockEvents}
        onSubmissionComplete={vi.fn()}
        onRefresh={vi.fn()}
      />
    );

    expect(screen.getByText(/Simulated Offer Accepted/i)).toBeInTheDocument();
    expect(screen.getByText(/This is a fictional simulation for training purposes only/i)).toBeInTheDocument();
    unmount();

    // Declined
    const declinedSubmission: OfferSubmissionStatusResponse = {
      ...mockExistingSubmission,
      status: 'declined',
    };

    render(
      <SubmissionStatusPanel
        applicationId={10}
        applicationStatus="declined"
        selectedOffer={mockSelectedOffer}
        submission={declinedSubmission}
        events={mockEvents}
        onSubmissionComplete={vi.fn()}
        onRefresh={vi.fn()}
      />
    );

    expect(screen.getByText(/Simulated Offer Declined/i)).toBeInTheDocument();
  });

  it('39, 40, & 41. LenderEventTimeline displays event sequence, types, and contains no signatures or secrets', () => {
    render(
      <LenderEventTimeline
        events={mockEvents}
        onRefresh={vi.fn()}
      />
    );

    expect(screen.getByText('Simulated Lender Event Ledger')).toBeInTheDocument();
    expect(screen.getByText('#1')).toBeInTheDocument();
    expect(screen.getByText('lender.accepted')).toBeInTheDocument();
    expect(screen.getByText('PROCESSED')).toBeInTheDocument();
    expect(screen.getByText('AUTO_APPROVAL')).toBeInTheDocument();

    // Strictly ensure no secrets or HMAC signatures are displayed
    expect(screen.queryByText(/hmac/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/secret/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/signature/i)).not.toBeInTheDocument();
  });

  it('42. Manual refresh button triggers onRefresh callback', () => {
    const onRefresh = vi.fn();

    render(
      <SubmissionStatusPanel
        applicationId={10}
        applicationStatus="submitted"
        selectedOffer={mockSelectedOffer}
        submission={mockExistingSubmission}
        events={mockEvents}
        onSubmissionComplete={vi.fn()}
        onRefresh={onRefresh}
      />
    );

    const refreshBtn = screen.getByRole('button', { name: /↻ Refresh Status/i });
    fireEvent.click(refreshBtn);
    expect(onRefresh).toHaveBeenCalledTimes(1);
  });
});
