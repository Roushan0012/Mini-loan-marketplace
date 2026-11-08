import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { RegisterForm } from '../components/RegisterForm';
import { AuthProvider } from '../../../app/providers/AuthProvider';
import { authService } from '../services/authService';
import { ApiError } from '../../../services/apiErrors';

describe('RegisterForm Component', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    sessionStorage.clear();
  });

  const renderWithProviders = () => {
    return render(
      <MemoryRouter initialEntries={['/register']}>
        <AuthProvider>
          <Routes>
            <Route path="/register" element={<RegisterForm />} />
            <Route path="/customer/dashboard" element={<div>Customer Dashboard Destination</div>} />
            <Route path="/login" element={<div>Login Page Destination</div>} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>
    );
  };

  it('10 & 11. Registration sends the correct payload and strictly does not send a role', async () => {
    const user = userEvent.setup();
    const registerSpy = vi.spyOn(authService, 'register').mockResolvedValue({
      id: 10,
      full_name: 'John Doe',
      email: 'john.doe@example.com',
      role: 'customer',
      is_active: true,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    });
    vi.spyOn(authService, 'login').mockResolvedValue({
      access_token: 'token',
      token_type: 'bearer',
      expires_in: 1800,
    });
    vi.spyOn(authService, 'getCurrentUser').mockResolvedValue({
      id: 10,
      full_name: 'John Doe',
      email: 'john.doe@example.com',
      role: 'customer',
      is_active: true,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    });

    renderWithProviders();

    await user.type(screen.getByLabelText(/Full Name/i), 'John Doe');
    await user.type(screen.getByLabelText(/Email Address/i), 'john.doe@example.com');
    await user.type(screen.getByLabelText(/^Password/i), 'SuperSecurePassword123!');
    await user.type(screen.getByLabelText(/Confirm Password/i), 'SuperSecurePassword123!');
    await user.click(screen.getByRole('button', { name: /Create Customer Account/i }));

    expect(registerSpy).toHaveBeenCalledTimes(1);
    const payload = registerSpy.mock.calls[0][0];

    // 10. Correct payload fields
    expect(payload.full_name).toBe('John Doe');
    expect(payload.email).toBe('john.doe@example.com');
    expect(payload.password).toBe('SuperSecurePassword123!');

    // 11. Strictly does not include role
    expect(payload).not.toHaveProperty('role');
    expect('role' in (payload as unknown as Record<string, unknown>)).toBe(false);
  });

  it('Validates password minimum length of 12 characters and matching confirmation', async () => {
    const user = userEvent.setup();
    renderWithProviders();

    await user.type(screen.getByLabelText(/Full Name/i), 'Valid Name');
    await user.type(screen.getByLabelText(/Email Address/i), 'valid@example.com');
    await user.type(screen.getByLabelText(/^Password/i), 'short123');
    await user.type(screen.getByLabelText(/Confirm Password/i), 'mismatch123');
    await user.click(screen.getByRole('button', { name: /Create Customer Account/i }));

    expect(await screen.findByText(/Password must be at least 12 characters/i)).toBeInTheDocument();
    expect(screen.getByText(/Passwords do not match/i)).toBeInTheDocument();
  });

  it('Displays duplicate-email conflict error from API', async () => {
    const user = userEvent.setup();
    vi.spyOn(authService, 'register').mockRejectedValue(
      new ApiError(409, 'Email is already registered.')
    );

    renderWithProviders();

    await user.type(screen.getByLabelText(/Full Name/i), 'Duplicate User');
    await user.type(screen.getByLabelText(/Email Address/i), 'existing@example.com');
    await user.type(screen.getByLabelText(/^Password/i), 'ValidPassword123456!');
    await user.type(screen.getByLabelText(/Confirm Password/i), 'ValidPassword123456!');
    await user.click(screen.getByRole('button', { name: /Create Customer Account/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent(/Email is already registered/i);
  });
});
