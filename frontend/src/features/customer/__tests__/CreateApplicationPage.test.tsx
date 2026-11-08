import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { CreateApplicationPage } from '../pages/CreateApplicationPage';
import { apiClient } from '../../../services/apiClient';
import { ApiError } from '../../../services/apiErrors';

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

describe('CreateApplicationPage Component', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    mockNavigate.mockReset();
  });

  const renderComponent = () =>
    render(
      <MemoryRouter>
        <CreateApplicationPage />
      </MemoryRouter>
    );

  it('1. Create form renders all required fields', () => {
    renderComponent();

    expect(screen.getByRole('heading', { name: /Start Your Loan Application/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/Age \(Years\)/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Employment Type/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Monthly Income \(₹\)/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Requested Loan Amount \(₹\)/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Create Application/i })).toBeInTheDocument();
  });

  it('2. Validates age: rejects empty, out of bounds, and non-integer inputs', async () => {
    renderComponent();

    const submitBtn = screen.getByRole('button', { name: /Create Application/i });

    // Submit with empty fields
    fireEvent.click(submitBtn);
    expect(await screen.findByText('Age is required.')).toBeInTheDocument();

    // Invalid age 0
    fireEvent.change(screen.getByLabelText(/Age \(Years\)/i), { target: { value: '0' } });
    fireEvent.click(submitBtn);
    expect(await screen.findByText('Age must be a valid whole number between 1 and 120.')).toBeInTheDocument();

    // Invalid age > 120
    fireEvent.change(screen.getByLabelText(/Age \(Years\)/i), { target: { value: '125' } });
    fireEvent.click(submitBtn);
    expect(await screen.findByText('Age must be a valid whole number between 1 and 120.')).toBeInTheDocument();

    // Non-integer age
    fireEvent.change(screen.getByLabelText(/Age \(Years\)/i), { target: { value: '25.5' } });
    fireEvent.click(submitBtn);
    expect(await screen.findByText('Age must be a valid whole number between 1 and 120.')).toBeInTheDocument();
  });

  it('3. Validates monthly income decimal input', async () => {
    renderComponent();

    const submitBtn = screen.getByRole('button', { name: /Create Application/i });
    fireEvent.change(screen.getByLabelText(/Age \(Years\)/i), { target: { value: '30' } });

    // Empty income
    fireEvent.click(submitBtn);
    expect(await screen.findByText('Monthly income is required.')).toBeInTheDocument();

    // Negative income
    fireEvent.change(screen.getByLabelText(/Monthly Income \(₹\)/i), { target: { value: '-500' } });
    fireEvent.click(submitBtn);
    expect(
      await screen.findByText('Monthly income must be a valid non-negative number with at most 2 decimal places.')
    ).toBeInTheDocument();

    // More than 2 decimal places
    fireEvent.change(screen.getByLabelText(/Monthly Income \(₹\)/i), { target: { value: '50000.123' } });
    fireEvent.click(submitBtn);
    expect(
      await screen.findByText('Monthly income must be a valid non-negative number with at most 2 decimal places.')
    ).toBeInTheDocument();
  });

  it('4. Validates requested loan amount decimal input', async () => {
    renderComponent();

    const submitBtn = screen.getByRole('button', { name: /Create Application/i });
    fireEvent.change(screen.getByLabelText(/Age \(Years\)/i), { target: { value: '30' } });
    fireEvent.change(screen.getByLabelText(/Monthly Income \(₹\)/i), { target: { value: '60000.00' } });

    // Empty requested amount
    fireEvent.click(submitBtn);
    expect(await screen.findByText('Requested loan amount is required.')).toBeInTheDocument();

    // Zero requested amount
    fireEvent.change(screen.getByLabelText(/Requested Loan Amount \(₹\)/i), { target: { value: '0' } });
    fireEvent.click(submitBtn);
    expect(
      await screen.findByText('Requested loan amount must be a positive number with at most 2 decimal places.')
    ).toBeInTheDocument();

    // More than 2 decimal places
    fireEvent.change(screen.getByLabelText(/Requested Loan Amount \(₹\)/i), { target: { value: '150000.999' } });
    fireEvent.click(submitBtn);
    expect(
      await screen.findByText('Requested loan amount must be a positive number with at most 2 decimal places.')
    ).toBeInTheDocument();
  });

  it('5. Allows selecting valid employment type', () => {
    renderComponent();

    const select = screen.getByLabelText(/Employment Type/i) as HTMLSelectElement;
    expect(select.value).toBe('salaried');

    fireEvent.change(select, { target: { value: 'self_employed' } });
    expect(select.value).toBe('self_employed');

    fireEvent.change(select, { target: { value: 'other' } });
    expect(select.value).toBe('other');
  });

  it('6 & 7. Submits valid draft payload without customer_id or role', async () => {
    const postSpy = vi.spyOn(apiClient, 'post').mockResolvedValue({
      id: 88,
      age: 32,
      monthly_income: '75000.00',
      work_type: 'salaried',
      requested_amount: '400000.00',
      status: 'draft',
      created_at: '2026-03-01T10:00:00Z',
      updated_at: '2026-03-01T10:00:00Z',
    });

    renderComponent();

    fireEvent.change(screen.getByLabelText(/Age \(Years\)/i), { target: { value: '32' } });
    fireEvent.change(screen.getByLabelText(/Monthly Income \(₹\)/i), { target: { value: '75000.00' } });
    fireEvent.change(screen.getByLabelText(/Requested Loan Amount \(₹\)/i), { target: { value: '400000.00' } });

    fireEvent.click(screen.getByRole('button', { name: /Create Application/i }));

    await waitFor(() => {
      expect(postSpy).toHaveBeenCalledTimes(1);
    });

    const [endpoint, payload] = postSpy.mock.calls[0];
    expect(endpoint).toBe('/applications');
    expect(payload).toEqual({
      age: 32,
      monthly_income: '75000.00',
      work_type: 'salaried',
      requested_amount: '400000.00',
    });

    // Strictly ensure no customer_id, user_id, or role is sent
    const payloadKeys = Object.keys(payload as object);
    expect(payloadKeys).not.toContain('customer_id');
    expect(payloadKeys).not.toContain('user_id');
    expect(payloadKeys).not.toContain('role');
  });

  it('8. Navigates to returned application detail page on successful creation', async () => {
    vi.spyOn(apiClient, 'post').mockResolvedValue({
      id: 99,
      age: 29,
      monthly_income: '50000.00',
      work_type: 'salaried',
      requested_amount: '200000.00',
      status: 'draft',
      created_at: '2026-03-01T10:00:00Z',
      updated_at: '2026-03-01T10:00:00Z',
    });

    renderComponent();

    fireEvent.change(screen.getByLabelText(/Age \(Years\)/i), { target: { value: '29' } });
    fireEvent.change(screen.getByLabelText(/Monthly Income \(₹\)/i), { target: { value: '50000.00' } });
    fireEvent.change(screen.getByLabelText(/Requested Loan Amount \(₹\)/i), { target: { value: '200000.00' } });

    fireEvent.click(screen.getByRole('button', { name: /Create Application/i }));

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/customer/applications/99');
    });
  });

  it('Displays API error message if application creation fails', async () => {
    vi.spyOn(apiClient, 'post').mockRejectedValue(
      new ApiError(400, 'Invalid applicant income')
    );

    renderComponent();

    fireEvent.change(screen.getByLabelText(/Age \(Years\)/i), { target: { value: '29' } });
    fireEvent.change(screen.getByLabelText(/Monthly Income \(₹\)/i), { target: { value: '50000.00' } });
    fireEvent.change(screen.getByLabelText(/Requested Loan Amount \(₹\)/i), { target: { value: '200000.00' } });

    fireEvent.click(screen.getByRole('button', { name: /Create Application/i }));

    expect(await screen.findByText('Invalid applicant income')).toBeInTheDocument();
  });
});
