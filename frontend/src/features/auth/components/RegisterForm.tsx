import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { Input } from '../../../components/ui/Input';
import { Button } from '../../../components/ui/Button';
import { ErrorMessage } from '../../../components/feedback/ErrorMessage';
import { ApiError } from '../../../services/apiErrors';

export const RegisterForm: React.FC = () => {
  const { register, login } = useAuth();
  const navigate = useNavigate();

  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [errors, setErrors] = useState<{
    fullName?: string;
    email?: string;
    password?: string;
    confirmPassword?: string;
  }>({});
  const [apiError, setApiError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const validate = (): boolean => {
    const newErrors: {
      fullName?: string;
      email?: string;
      password?: string;
      confirmPassword?: string;
    } = {};

    const trimmedName = fullName.trim();
    if (!trimmedName) {
      newErrors.fullName = 'Full name is required.';
    } else if (trimmedName.length < 2) {
      newErrors.fullName = 'Full name must be at least 2 characters.';
    } else if (trimmedName.length > 150) {
      newErrors.fullName = 'Full name cannot exceed 150 characters.';
    }

    const trimmedEmail = email.trim();
    if (!trimmedEmail) {
      newErrors.email = 'Email address is required.';
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(trimmedEmail)) {
      newErrors.email = 'Please enter a valid email address.';
    }

    if (!password) {
      newErrors.password = 'Password is required.';
    } else if (password.length < 12) {
      newErrors.password = 'Password must be at least 12 characters.';
    } else if (password.length > 128) {
      newErrors.password = 'Password cannot exceed 128 characters.';
    }

    if (!confirmPassword) {
      newErrors.confirmPassword = 'Please confirm your password.';
    } else if (password !== confirmPassword) {
      newErrors.confirmPassword = 'Passwords do not match.';
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
      // NOTE: Strictly no role is passed in request payload; backend defaults to 'customer'
      await register({
        full_name: fullName.trim(),
        email: email.trim(),
        password,
      });

      // Seamlessly sign in newly registered customer
      try {
        await login({ email: email.trim(), password });
        navigate('/customer/dashboard', { replace: true });
      } catch {
        navigate('/login?registered=true', { replace: true });
      }
    } catch (err) {
      if (err instanceof ApiError) {
        setApiError(err.getFormattedMessage());
      } else {
        setApiError('Registration failed. Please check your inputs and try again.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} noValidate style={{ maxWidth: '440px', width: '100%', margin: '0 auto' }}>
      <ErrorMessage message={apiError || undefined} />

      <Input
        id="register-fullname"
        name="full_name"
        label="Full Name"
        type="text"
        autoComplete="name"
        value={fullName}
        onChange={(e) => {
          setFullName(e.target.value);
          if (errors.fullName) setErrors((prev) => ({ ...prev, fullName: undefined }));
        }}
        error={errors.fullName}
        disabled={isLoading}
        required
      />

      <Input
        id="register-email"
        name="email"
        label="Email Address"
        type="email"
        autoComplete="email"
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
        id="register-password"
        name="password"
        label="Password (min 12 characters)"
        type="password"
        autoComplete="new-password"
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

      <Input
        id="register-confirm-password"
        name="confirm_password"
        label="Confirm Password"
        type="password"
        autoComplete="new-password"
        showPasswordToggle
        value={confirmPassword}
        onChange={(e) => {
          setConfirmPassword(e.target.value);
          if (errors.confirmPassword) setErrors((prev) => ({ ...prev, confirmPassword: undefined }));
        }}
        error={errors.confirmPassword}
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
          Create Customer Account
        </Button>
      </div>

      <p style={{ marginTop: '1.25rem', textAlign: 'center', fontSize: '0.875rem', color: 'var(--color-text-muted)' }}>
        Already have an account?{' '}
        <Link to="/login" style={{ fontWeight: 600 }}>
          Sign In
        </Link>
      </p>
    </form>
  );
};
