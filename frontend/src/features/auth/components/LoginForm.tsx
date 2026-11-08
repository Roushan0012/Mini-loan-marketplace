import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { Input } from '../../../components/ui/Input';
import { Button } from '../../../components/ui/Button';
import { ErrorMessage } from '../../../components/feedback/ErrorMessage';
import { getDashboardPathForRole } from '../../../app/routes/routeUtils';
import { ApiError } from '../../../services/apiErrors';

export const LoginForm: React.FC = () => {
  const { login } = useAuth();
  const navigate = useNavigate();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [errors, setErrors] = useState<{ email?: string; password?: string }>({});
  const [apiError, setApiError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const validate = (): boolean => {
    const newErrors: { email?: string; password?: string } = {};

    if (!email.trim()) {
      newErrors.email = 'Email address is required.';
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
      newErrors.email = 'Please enter a valid email address.';
    }

    if (!password) {
      newErrors.password = 'Password is required.';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setApiError(null);

    if (!validate()) {
      return;
    }

    setIsLoading(true);
    try {
      const user = await login({ email: email.trim(), password });
      navigate(getDashboardPathForRole(user.role), { replace: true });
    } catch (err) {
      if (err instanceof ApiError) {
        setApiError(err.getFormattedMessage());
      } else {
        setApiError('Unable to sign in. Please verify your credentials and network connection.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} noValidate style={{ maxWidth: '420px', width: '100%', margin: '0 auto' }}>
      <ErrorMessage message={apiError || undefined} />

      <Input
        id="login-email"
        name="email"
        label="Email Address"
        type="email"
        autoComplete="username"
        value={email}
        onChange={(e) => {
          setEmail(e.target.value);
          if (errors.email) setErrors((prev) => ({ ...prev, email: undefined }));
        }}
        error={errors.email}
        disabled={isLoading}
        required
      />

      <Input
        id="login-password"
        name="password"
        label="Password"
        type="password"
        autoComplete="current-password"
        showPasswordToggle
        value={password}
        onChange={(e) => {
          setPassword(e.target.value);
          if (errors.password) setErrors((prev) => ({ ...prev, password: undefined }));
        }}
        error={errors.password}
        disabled={isLoading}
        required
      />

      <div style={{ marginTop: '1.5rem' }}>
        <Button
          type="submit"
          variant="primary"
          isLoading={isLoading}
          style={{ width: '100%' }}
        >
          Sign In
        </Button>
      </div>

      <p style={{ marginTop: '1.25rem', textAlign: 'center', fontSize: '0.875rem', color: 'var(--color-text-muted)' }}>
        Don't have an account?{' '}
        <Link to="/register" style={{ fontWeight: 600 }}>
          Register as Customer
        </Link>
      </p>
    </form>
  );
};
