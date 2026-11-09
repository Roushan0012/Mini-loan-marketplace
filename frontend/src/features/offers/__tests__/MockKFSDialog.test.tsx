import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MockKFSDialog } from '../components/MockKFSDialog';
import { MockKFSResponse } from '../types';
import { apiClient } from '../../../services/apiClient';
import { ApiError } from '../../../services/apiErrors';

describe('MockKFSDialog Component', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  const mockKFSData: MockKFSResponse = {
    document_type: 'TRAINING_ONLY_MOCK_KFS',
    document_version: 'training-v1',
    mock_kfs_reference: 'KFS-APEX-998877',
    offer_id: 101,
    application_id: 10,
    lender_code: 'APEX_FINANCIAL',
    lender_name: 'Apex Financial',
    policy_version: 'v1.0',
    offer_status: 'available',
    offer_created_at: '2026-03-01T12:05:00Z',
    valid_until: '2026-03-15T12:05:00Z',
    loan_amount: '200000.00',
    nominal_annual_apr_percent: '14.5000',
    term_months: 24,
    number_of_installments: 24,
    payment_frequency: 'Monthly',
    monthly_installment: '9648.50',
    estimated_total_repayment: '231564.00',
    estimated_total_interest: '31564.00',
    amortization_method: 'Monthly reducing-balance',
    fee_disclosure: 'Zero processing fee during demo simulation.',
    calculation_disclosure: 'Calculated using standard reducing balance formula.',
    training_disclosure: 'Pure training simulation document.',
  };

  it('10, 11, 12, & 13. Calls KFS endpoint and renders financial terms, lender info, and training disclosure', async () => {
    const getSpy = vi.spyOn(apiClient, 'get').mockResolvedValue(mockKFSData);

    render(
      <MockKFSDialog
        applicationId={10}
        offerId={101}
        isOpen={true}
        onClose={vi.fn()}
      />
    );

    await waitFor(() => {
      expect(getSpy).toHaveBeenCalledWith('/applications/10/offers/101/kfs');
    });

    expect(await screen.findByRole('dialog')).toBeInTheDocument();
    expect(screen.getByText('Mock Key Facts Statement (KFS)')).toBeInTheDocument();
    expect(screen.getByText('KFS-APEX-998877')).toBeInTheDocument();
    expect(screen.getByText('Apex Financial')).toBeInTheDocument();

    // Financial values rendered using decimal-safe formatRupees and formatApr
    expect(screen.getByText('₹2,00,000.00')).toBeInTheDocument();
    expect(screen.getByText('14.5%')).toBeInTheDocument();
    expect(screen.getByText('24 Months (24 Installments)')).toBeInTheDocument();
    expect(screen.getByText('₹9,648.50')).toBeInTheDocument();
    expect(screen.getByText('₹2,31,564.00')).toBeInTheDocument();
    expect(screen.getByText('₹31,564.00')).toBeInTheDocument();

    // 13. Training disclosure is visible
    expect(
      screen.getByText(/This is a fictional software-training document only/i)
    ).toBeInTheDocument();
  });

  it('14. Handles API errors and loading states', async () => {
    vi.spyOn(apiClient, 'get').mockRejectedValue(
      new ApiError(404, 'Key Facts Statement not found.')
    );

    render(
      <MockKFSDialog
        applicationId={10}
        offerId={101}
        isOpen={true}
        onClose={vi.fn()}
      />
    );

    expect(await screen.findByText('Key Facts Statement not found.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Retry/i })).toBeInTheDocument();
  });

  it('15. Escape key and close button dismiss the dialog', async () => {
    vi.spyOn(apiClient, 'get').mockResolvedValue(mockKFSData);
    const onClose = vi.fn();

    render(
      <MockKFSDialog
        applicationId={10}
        offerId={101}
        isOpen={true}
        onClose={onClose}
      />
    );

    await screen.findByRole('dialog');

    // Close button click
    const closeBtn = screen.getByRole('button', { name: /Close dialog/i });
    fireEvent.click(closeBtn);
    expect(onClose).toHaveBeenCalledTimes(1);

    // Escape key
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(onClose).toHaveBeenCalledTimes(2);
  });

  it('16. Strictly does not render or initiate PDF download', async () => {
    vi.spyOn(apiClient, 'get').mockResolvedValue(mockKFSData);

    render(
      <MockKFSDialog
        applicationId={10}
        offerId={101}
        isOpen={true}
        onClose={vi.fn()}
      />
    );

    await screen.findByRole('dialog');
    expect(screen.queryByText(/Download PDF/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/\.pdf/i)).not.toBeInTheDocument();
  });
});
