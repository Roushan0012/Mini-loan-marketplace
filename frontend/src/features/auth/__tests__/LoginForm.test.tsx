import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { LoginForm } from '../components/LoginForm';
import { AuthProvider } from '../../../app/providers/AuthProvider';
import { authService } from '../services/authService';
import { ApiError } from '../../../services/apiErrors';
import { AuthTokens } from '../../../types/auth';

describe('LoginForm Component', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    sessionStorage.clear();
  });

  const renderWithProviders = () => {
    return render(
      <MemoryRouter initialEntries={['/login']}>
        <AuthProvider>
          <Routes>
            <Route path="/login" element={<LoginForm />} />
            <Route path="/customer/dashboard" element={<div>Customer Dashboard Destination</div>} />
            <Route path="/caller/dashboard" element={<div>Caller Dashboard Destination</div>} />
            <Route path="/admin/dashboard" element={<div>Admin Dashboard Destination</div>} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>
    );
  };

  it('5. Login form renders correctly with email, password, and sign in button', () => {
    renderWithProviders();

    expect(screen.getByLabelText(/Email Address/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^Password/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Sign In/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Register as Customer/i })).toBeInTheDocument();
  });

  it('6. Login form validates required inputs before submission', async () => {
    const user = userEvent.setup();
    renderWithProviders();

    const submitBtn = screen.getByRole('button', { name: /Sign In/i });
    await user.click(submitBtn);

    expect(await screen.findByText(/Email address is required/i)).toBeInTheDocument();
    expect(screen.getByText(/Password is required/i)).toBeInTheDocument();
  });

  it('7. Successful customer login redirects to customer dashboard', async () => {
    const user = userEvent.setup();
    vi.spyOn(authService, 'login').mockResolvedValue({
      access_token: 'mock-customer-token',
      token_type: 'bearer',
      expires_in: 1800,
    });
    vi.spyOn(authService, 'getCurrentUser').mockResolvedValue({
      id: 1,
      full_name: 'Jane Customer',
      email: 'jane@example.com',
      role: 'customer',
      is_active: true,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    });

    renderWithProviders();

    await user.type(screen.getByLabelText(/Email Address/i), 'jane@example.com');
    await user.type(screen.getByLabelText(/^Password/i), 'SecurePassword123!');
    await user.click(screen.getByRole('button', { name: /Sign In/i }));

    expect(await screen.findByText('Customer Dashboard Destination')).toBeInTheDocument();
  });

  it('8. Caller login redirects to caller dashboard', async () => {
    const user = userEvent.setup();
    vi.spyOn(authService, 'login').mockResolvedValue({
      access_token: 'mock-caller-token',
      token_type: 'bearer',
      expires_in: 1800,
    });
    vi.spyOn(authService, 'getCurrentUser').mockResolvedValue({
      id: 2,
      full_name: 'Caller Agent Bob',
      email: 'caller.bob@example.com',
      role: 'caller',
      is_active: true,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    });

    renderWithProviders();

    await user.type(screen.getByLabelText(/Email Address/i), 'caller.bob@example.com');
    await user.type(screen.getByLabelText(/^Password/i), 'SecurePassword123!');
    await user.click(screen.getByRole('button', { name: /Sign In/i }));

    expect(await screen.findByText('Caller Dashboard Destination')).toBeInTheDocument();
  });

  it('9. Admin login redirects to admin dashboard', async () => {
    const user = userEvent.setup();
    vi.spyOn(authService, 'login').mockResolvedValue({
      access_token: 'mock-admin-token',
      token_type: 'bearer',
      expires_in: 1800,
    });
    vi.spyOn(authService, 'getCurrentUser').mockResolvedValue({
      id: 3,
      full_name: 'Administrator Alice',
      email: 'admin.alice@example.com',
      role: 'admin',
      is_active: true,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    });

    renderWithProviders();

    await user.type(screen.getByLabelText(/Email Address/i), 'admin.alice@example.com');
    await user.type(screen.getByLabelText(/^Password/i), 'SecurePassword123!');
    await user.click(screen.getByRole('button', { name: /Sign In/i }));

    expect(await screen.findByText('Admin Dashboard Destination')).toBeInTheDocument();
  });

  it('21. Displays clear API error on invalid credentials', async () => {
    const user = userEvent.setup();
    vi.spyOn(authService, 'login').mockRejectedValue(
      new ApiError(401, 'Invalid email or password.')
    );

    renderWithProviders();

    await user.type(screen.getByLabelText(/Email Address/i), 'wrong@example.com');
    await user.type(screen.getByLabelText(/^Password/i), 'WrongPassword123!');
    await user.click(screen.getByRole('button', { name: /Sign In/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent(/Invalid email or password/i);
  });

  it('22. Displays loading state while sign in request is in flight', async () => {
    const user = userEvent.setup();
    let resolveLogin: (val: AuthTokens) => void = () => {};
    const pendingPromise = new Promise<AuthTokens>((resolve) => {
      resolveLogin = resolve;
    });

    vi.spyOn(authService, 'login').mockImplementation(() => pendingPromise);

    renderWithProviders();

    await user.type(screen.getByLabelText(/Email Address/i), 'test@example.com');
    await user.type(screen.getByLabelText(/^Password/i), 'ValidPassword123!');
    await user.click(screen.getByRole('button', { name: /Sign In/i }));

    expect(screen.getByRole('button', { name: /Loading/i })).toBeDisabled();

    // Resolve login to cleanup cleanly
    resolveLogin({ access_token: 'token', token_type: 'bearer', expires_in: 1800 });
  });
});
