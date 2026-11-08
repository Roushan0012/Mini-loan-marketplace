import React from 'react';
import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '../providers/AuthContext';
import { UserRole } from '../../types/auth';
import { LoadingSpinner } from '../../components/feedback/LoadingSpinner';
import { getDashboardPathForRole } from './routeUtils';

/**
 * Route guard that only permits unauthenticated guests.
 * If authenticated, redirects to the role-specific dashboard.
 */
export const GuestOnlyRoute: React.FC<{ children?: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated, isLoading, user } = useAuth();

  if (isLoading) {
    return <LoadingSpinner message="Checking authentication..." fullScreen />;
  }

  if (isAuthenticated && user) {
    return <Navigate to={getDashboardPathForRole(user.role)} replace />;
  }

  return children ? <>{children}</> : <Outlet />;
};

/**
 * Route guard that requires an authenticated user of any role.
 * If unauthenticated, redirects to /login.
 */
export const ProtectedRoute: React.FC<{ children?: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return <LoadingSpinner message="Validating credentials..." fullScreen />;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return children ? <>{children}</> : <Outlet />;
};

/**
 * Route guard that restricts access strictly to specified user roles.
 * Redirects unauthenticated users to /login and unauthorized roles to /unauthorized.
 */
export const RoleRoute: React.FC<{
  allowedRoles: UserRole[];
  children?: React.ReactNode;
}> = ({ allowedRoles, children }) => {
  const { isAuthenticated, isLoading, user } = useAuth();

  if (isLoading) {
    return <LoadingSpinner message="Verifying role permissions..." fullScreen />;
  }

  if (!isAuthenticated || !user) {
    return <Navigate to="/login" replace />;
  }

  if (!allowedRoles.includes(user.role)) {
    return <Navigate to="/unauthorized" replace />;
  }

  return children ? <>{children}</> : <Outlet />;
};
