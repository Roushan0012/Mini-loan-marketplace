import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { OfferSelectionPanel } from '../components/OfferSelectionPanel';
import { OfferResponse, OfferSelectionResponse } from '../types';
import { apiClient } from '../../../services/apiClient';
import { ApiError } from '../../../services/apiErrors';

describe('OfferSelectionPanel Component', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  const mockAvailableOffer: OfferResponse = {
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
    valid_until: null,
  };

  const mockSelectionResult: OfferSelectionResponse = {
    application_id: 10,
    application_status: 'offer_selected',
    selected_offer: { ...mockAvailableOffer, status: 'selected' },
    withdrawn_offer_count: 2,
    selection_result: 'selected',
  };

  it('22 & 23. Requires user confirmation before calling select endpoint', async () => {
    const postSpy = vi.spyOn(apiClient, 'post').mockResolvedValue(mockSelectionResult);
    const onSuccess = vi.fn();
    const onCancel = vi.fn();

    render(
      <OfferSelectionPanel
        applicationId={10}
        pendingOffer={mockAvailableOffer}
        isOpen={true}
        onCancel={onCancel}
        onSuccess={onSuccess}
      />
    );

    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(screen.getByText('Confirm Loan Offer Selection')).toBeInTheDocument();
    expect(screen.getByText(/Selecting this offer will automatically/i)).toBeInTheDocument();

    const confirmBtn = screen.getByRole('button', { name: /Confirm Selection/i });
    fireEvent.click(confirmBtn);

    await waitFor(() => {
      expect(postSpy).toHaveBeenCalledWith('/applications/10/offers/101/select');
    });

    await waitFor(() => {
      expect(onSuccess).toHaveBeenCalledWith(mockSelectionResult);
    });
  });

  it('25. Displays API 409 conflict error when offer selection is rejected', async () => {
    vi.spyOn(apiClient, 'post').mockRejectedValue(
      new ApiError(409, 'Another offer was already selected for this application.')
    );

    render(
      <OfferSelectionPanel
        applicationId={10}
        pendingOffer={mockAvailableOffer}
        isOpen={true}
        onCancel={vi.fn()}
        onSuccess={vi.fn()}
      />
    );

    const confirmBtn = screen.getByRole('button', { name: /Confirm Selection/i });
    fireEvent.click(confirmBtn);

    expect(
      await screen.findByText('Another offer was already selected for this application.')
    ).toBeInTheDocument();
  });

  it('Can be cancelled by user without submitting', () => {
    const onCancel = vi.fn();

    render(
      <OfferSelectionPanel
        applicationId={10}
        pendingOffer={mockAvailableOffer}
        isOpen={true}
        onCancel={onCancel}
        onSuccess={vi.fn()}
      />
    );

    const cancelBtn = screen.getByRole('button', { name: /Cancel/i });
    fireEvent.click(cancelBtn);
    expect(onCancel).toHaveBeenCalledTimes(1);
  });
});
