import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { AuthProvider } from '../providers/AuthProvider';
import { GuestOnlyRoute, ProtectedRoute, RoleRoute } from '../routes/RouteGuards';
import { authService } from '../../features/auth/services/authService';
import { UserProfile, UserRole } from '../../types/auth';

describe('Route Guards and Role-Based Protection', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    sessionStorage.clear();
  });

  const setupMockUser = (role: UserRole | null) => {
    if (!role) {
      vi.spyOn(authService, 'hasToken').mockReturnValue(false);
      vi.spyOn(authService, 'getCurrentUser').mockRejectedValue(new Error('Unauthenticated'));
      return;
    }

    vi.spyOn(authService, 'hasToken').mockReturnValue(true);
    vi.spyOn(authService, 'getCurrentUser').mockResolvedValue({
      id: 99,
      full_name: `${role.toUpperCase()} User`,
      email: `${role}@example.com`,
      role: role,
      is_active: true,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    } as UserProfile);
  };

  const renderGuardedApp = (initialRoute: string) => {
    return render(
      <MemoryRouter initialEntries={[initialRoute]}>
        <AuthProvider>
          <Routes>
            <Route path="/login" element={<div>Login Page View</div>} />
            <Route path="/unauthorized" element={<div>403 Unauthorized View</div>} />

            <Route element={<GuestOnlyRoute />}>
              <Route path="/guest-welcome" element={<div>Guest Welcome View</div>} />
            </Route>

            <Route element={<ProtectedRoute />}>
              <Route path="/protected-common" element={<div>Protected Common View</div>} />
            </Route>

            <Route element={<RoleRoute allowedRoles={['customer']} />}>
              <Route path="/customer/dashboard" element={<div>Customer Dashboard View</div>} />
              <Route path="/customer/applications/new" element={<div>Create Application View</div>} />
              <Route path="/customer/applications/:applicationId" element={<div>Application Detail View</div>} />
            </Route>

            <Route element={<RoleRoute allowedRoles={['caller']} />}>
              <Route path="/caller/dashboard" element={<div>Caller Dashboard View</div>} />
            </Route>

            <Route element={<RoleRoute allowedRoles={['admin']} />}>
              <Route path="/admin/dashboard" element={<div>Admin Dashboard View</div>} />
            </Route>
          </Routes>
        </AuthProvider>
      </MemoryRouter>
    );
  };

  it('13. Unauthenticated user visiting protected route is redirected to /login', async () => {
    setupMockUser(null);
    renderGuardedApp('/protected-common');

    expect(await screen.findByText('Login Page View')).toBeInTheDocument();
  });

  it('14. Customer cannot access caller dashboard (redirected to /unauthorized)', async () => {
    setupMockUser('customer');
    renderGuardedApp('/caller/dashboard');

    expect(await screen.findByText('403 Unauthorized View')).toBeInTheDocument();
  });

  it('15. Caller cannot access admin dashboard (redirected to /unauthorized)', async () => {
    setupMockUser('caller');
    renderGuardedApp('/admin/dashboard');

    expect(await screen.findByText('403 Unauthorized View')).toBeInTheDocument();
  });

  it('16. Admin cannot access customer dashboard (redirected to /unauthorized)', async () => {
    setupMockUser('admin');
    renderGuardedApp('/customer/dashboard');

    expect(await screen.findByText('403 Unauthorized View')).toBeInTheDocument();
  });

  it('17. Role from /auth/me accurately grants access to own dashboard', async () => {
    // 17a. Customer accesses customer dashboard
    setupMockUser('customer');
    const { unmount } = renderGuardedApp('/customer/dashboard');
    expect(await screen.findByText('Customer Dashboard View')).toBeInTheDocument();
    unmount();

    // 17b. Caller accesses caller dashboard
    setupMockUser('caller');
    const { unmount: unmountCaller } = renderGuardedApp('/caller/dashboard');
    expect(await screen.findByText('Caller Dashboard View')).toBeInTheDocument();
    unmountCaller();

    // 17c. Admin accesses admin dashboard
    setupMockUser('admin');
    renderGuardedApp('/admin/dashboard');
    expect(await screen.findByText('Admin Dashboard View')).toBeInTheDocument();
  });

  it('Authenticated user visiting guest route (/login) is redirected to their role dashboard', async () => {
    setupMockUser('customer');
    renderGuardedApp('/guest-welcome');

    expect(await screen.findByText('Customer Dashboard View')).toBeInTheDocument();
  });

  it('46. Customer can access application creation and detail views', async () => {
    setupMockUser('customer');
    const { unmount } = renderGuardedApp('/customer/applications/new');
    expect(await screen.findByText('Create Application View')).toBeInTheDocument();
    unmount();

    renderGuardedApp('/customer/applications/42');
    expect(await screen.findByText('Application Detail View')).toBeInTheDocument();
  });

  it('47 & 48. Caller and Admin cannot access customer application views', async () => {
    // Caller blocked from customer application details
    setupMockUser('caller');
    const { unmount } = renderGuardedApp('/customer/applications/42');
    expect(await screen.findByText('403 Unauthorized View')).toBeInTheDocument();
    unmount();

    // Admin blocked from customer application details
    setupMockUser('admin');
    renderGuardedApp('/customer/applications/42');
    expect(await screen.findByText('403 Unauthorized View')).toBeInTheDocument();
  });
});
