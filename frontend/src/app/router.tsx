import { createBrowserRouter, Navigate } from 'react-router-dom';
import { DashboardLayout } from '../components/layout/DashboardLayout';
import { GuestOnlyRoute, RoleRoute } from './routes/RouteGuards';
import { LoginPage } from '../pages/LoginPage';
import { RegisterPage } from '../pages/RegisterPage';
import { CustomerDashboardPage } from '../pages/CustomerDashboardPage';
import { CallerDashboardPage } from '../pages/CallerDashboardPage';
import { AdminDashboardPage } from '../pages/AdminDashboardPage';
import { UnauthorizedPage } from '../pages/UnauthorizedPage';
import { NotFoundPage } from '../pages/NotFoundPage';

export const router = createBrowserRouter([
  {
    path: '/',
    element: <DashboardLayout />,
    children: [
      {
        index: true,
        element: <Navigate to="/login" replace />,
      },
      // Guest-only routes
      {
        path: 'login',
        element: (
          <GuestOnlyRoute>
            <LoginPage />
          </GuestOnlyRoute>
        ),
      },
      {
        path: 'register',
        element: (
          <GuestOnlyRoute>
            <RegisterPage />
          </GuestOnlyRoute>
        ),
      },
      // Role-restricted protected routes
      {
        path: 'customer/dashboard',
        element: (
          <RoleRoute allowedRoles={['customer']}>
            <CustomerDashboardPage />
          </RoleRoute>
        ),
      },
      {
        path: 'caller/dashboard',
        element: (
          <RoleRoute allowedRoles={['caller']}>
            <CallerDashboardPage />
          </RoleRoute>
        ),
      },
      {
        path: 'admin/dashboard',
        element: (
          <RoleRoute allowedRoles={['admin']}>
            <AdminDashboardPage />
          </RoleRoute>
        ),
      },
      // Informational / Fallback routes
      {
        path: 'unauthorized',
        element: <UnauthorizedPage />,
      },
      {
        path: '*',
        element: <NotFoundPage />,
      },
    ],
  },
]);
