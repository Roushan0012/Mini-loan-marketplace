import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import { getDashboardPathForRole } from '../../app/routes/routeUtils';

export const Navbar: React.FC = () => {
  const { user, isAuthenticated, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <header className="navbar" role="banner">
      <div className="navbar-brand">
        <Link to={isAuthenticated && user ? getDashboardPathForRole(user.role) : '/login'}>
          🏦 Mini Loan Marketplace
        </Link>
      </div>
      <nav aria-label="Main Navigation">
        <ul className="navbar-nav">
          {isAuthenticated && user ? (
            <>
              <li>
                <div className="nav-user-info">
                  <span style={{ fontWeight: 600 }}>{user.full_name}</span>
                  <span className={`badge badge-${user.role}`}>{user.role}</span>
                </div>
              </li>
              <li>
                <button
                  type="button"
                  className="btn btn-outline"
                  onClick={handleLogout}
                  style={{ padding: '0.35rem 0.75rem', fontSize: '0.8125rem' }}
                >
                  Sign Out
                </button>
              </li>
            </>
          ) : (
            <>
              <li>
                <Link to="/login" className="nav-link">
                  Sign In
                </Link>
              </li>
              <li>
                <Link to="/register" className="btn btn-primary" style={{ padding: '0.35rem 0.75rem' }}>
                  Register
                </Link>
              </li>
            </>
          )}
        </ul>
      </nav>
    </header>
  );
};
