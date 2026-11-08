import { UserRole } from '../../types/auth';

export const getDashboardPathForRole = (role?: UserRole | null): string => {
  switch (role) {
    case 'customer':
      return '/customer/dashboard';
    case 'caller':
      return '/caller/dashboard';
    case 'admin':
      return '/admin/dashboard';
    default:
      return '/login';
  }
};
