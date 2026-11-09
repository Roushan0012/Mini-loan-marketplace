import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card } from '../../../components/ui/Card';
import { Input } from '../../../components/ui/Input';
import { Button } from '../../../components/ui/Button';
import { ErrorMessage } from '../../../components/feedback/ErrorMessage';
import { applicationService } from '../services/applicationService';
import { WorkType } from '../types';
import { isNonNegativeDecimal, isPositiveDecimal } from '../utils/validators';
import { ApiError } from '../../../services/apiErrors';

export const CreateApplicationPage: React.FC = () => {
  const navigate = useNavigate();

  const [age, setAge] = useState('');
  const [monthlyIncome, setMonthlyIncome] = useState('');
  const [workType, setWorkType] = useState<WorkType>('salaried');
  const [requestedAmount, setRequestedAmount] = useState('');

  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [generalError, setGeneralError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const validate = (): boolean => {
    const errors: Record<string, string> = {};

    // Age validation
    const ageNum = Number(age.trim());
    if (!age.trim()) {
      errors.age = 'Age is required.';
    } else if (!Number.isInteger(ageNum) || ageNum < 1 || ageNum > 120) {
      errors.age = 'Age must be a valid whole number between 1 and 120.';
    }

    // Monthly Income validation
    const incomeTrimmed = monthlyIncome.trim();
    if (!incomeTrimmed) {
      errors.monthlyIncome = 'Monthly income is required.';
    } else if (!isNonNegativeDecimal(incomeTrimmed)) {
      errors.monthlyIncome = 'Monthly income must be a valid non-negative number with at most 2 decimal places.';
    } else if (incomeTrimmed.replace('.', '').length > 12) {
      errors.monthlyIncome = 'Monthly income cannot exceed 12 digits.';
    }

    // Requested Amount validation
    const amountTrimmed = requestedAmount.trim();
    if (!amountTrimmed) {
      errors.requestedAmount = 'Requested loan amount is required.';
    } else if (!isPositiveDecimal(amountTrimmed)) {
      errors.requestedAmount = 'Requested loan amount must be a positive number with at most 2 decimal places.';
    } else if (amountTrimmed.replace('.', '').length > 12) {
      errors.requestedAmount = 'Requested loan amount cannot exceed 12 digits.';
    }

    // Work type validation
    if (!workType || !['salaried', 'self_employed', 'other'].includes(workType)) {
      errors.workType = 'Please select a valid employment type.';
    }

    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setGeneralError(null);

    if (!validate()) {
      return;
    }

    setIsLoading(true);

    try {
      const createdApp = await applicationService.createApplication({
        age: parseInt(age.trim(), 10),
        monthly_income: monthlyIncome.trim(),
        work_type: workType,
        requested_amount: requestedAmount.trim(),
      });

      // Navigate directly to the newly created application detail page
      navigate(`/customer/applications/${createdApp.id}`);
    } catch (err) {
      if (err instanceof ApiError) {
        setGeneralError(err.getFormattedMessage());
      } else {
        setGeneralError('An unexpected network error occurred while submitting your application.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: '640px', margin: '0 auto' }}>
        <Card title="Start Your Loan Application">
          <p style={{ color: 'var(--color-text-muted)', marginBottom: '1.5rem', fontSize: '0.875rem' }}>
            Provide your employment and income details to initialize a draft application. You will be able to review versioned consent terms and perform mock lender matching on the next screen.
          </p>

          {generalError && (
            <div style={{ marginBottom: '1.25rem' }}>
              <ErrorMessage message={generalError} />
            </div>
          )}

          <form onSubmit={handleSubmit} noValidate>
            <Input
              id="age"
              name="age"
              label="Age (Years)"
              type="number"
              min="1"
              max="120"
              placeholder="e.g. 28"
              value={age}
              onChange={(e) => setAge(e.target.value)}
              error={fieldErrors.age}
              disabled={isLoading}
              required
            />

            <div className="form-group">
              <label htmlFor="work_type" className="form-label">
                Employment Type
              </label>
              <select
                id="work_type"
                name="work_type"
                className={`form-input ${fieldErrors.workType ? 'form-input-error' : ''}`}
                value={workType}
                onChange={(e) => setWorkType(e.target.value as WorkType)}
                disabled={isLoading}
                aria-invalid={Boolean(fieldErrors.workType)}
                aria-describedby={fieldErrors.workType ? 'work_type-error' : undefined}
                required
              >
                <option value="salaried">Salaried Employee</option>
                <option value="self_employed">Self-Employed / Business Owner</option>
                <option value="other">Other</option>
              </select>
              {fieldErrors.workType && (
                <p id="work_type-error" className="form-error-text" role="alert">
                  {fieldErrors.workType}
                </p>
              )}
            </div>

            <Input
              id="monthly_income"
              name="monthly_income"
              label="Monthly Income (₹)"
              type="text"
              placeholder="e.g. 50000.00"
              value={monthlyIncome}
              onChange={(e) => setMonthlyIncome(e.target.value)}
              error={fieldErrors.monthlyIncome}
              disabled={isLoading}
              required
            />

            <Input
              id="requested_amount"
              name="requested_amount"
              label="Requested Loan Amount (₹)"
              type="text"
              placeholder="e.g. 200000.00"
              value={requestedAmount}
              onChange={(e) => setRequestedAmount(e.target.value)}
              error={fieldErrors.requestedAmount}
              disabled={isLoading}
              required
            />

            <div style={{ display: 'flex', gap: '0.75rem', marginTop: '1.5rem', justifyContent: 'flex-end' }}>
              <Button
                type="button"
                variant="outline"
                onClick={() => navigate('/customer/dashboard')}
                disabled={isLoading}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                variant="primary"
                isLoading={isLoading}
                disabled={isLoading}
              >
                Create Application
              </Button>
            </div>
          </form>
        </Card>
      </div>
  );
};
