import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Card } from '../../../components/ui/Card';
import { Input } from '../../../components/ui/Input';
import { Button } from '../../../components/ui/Button';
import { LoadingSpinner } from '../../../components/feedback/LoadingSpinner';
import { ErrorMessage } from '../../../components/feedback/ErrorMessage';
import { applicationService } from '../services/applicationService';
import { consentService } from '../../consents/services/consentService';
import { matchingService } from '../../matching/services/matchingService';
import { LoanApplication, WorkType } from '../types';
import { ConsentNotice, ConsentRecord } from '../../consents/types';
import { MatchRun } from '../../matching/types';
import { getConsentReadiness } from '../../consents/utils/consentReadiness';
import { ConsentNoticeCard } from '../../consents/components/ConsentNoticeCard';
import { ConsentHistoryList } from '../../consents/components/ConsentHistoryList';
import { MatchingSection } from '../../matching/components/MatchingSection';
import { MatchHistoryList } from '../../matching/components/MatchHistoryList';
import { ApiError } from '../../../services/apiErrors';

const DECIMAL_REGEX = /^\d+(\.\d{1,2})?$/;

export const ApplicationDetailPage: React.FC = () => {
  const { applicationId } = useParams<{ applicationId: string }>();
  const navigate = useNavigate();

  const appId = applicationId ? parseInt(applicationId, 10) : NaN;

  const [application, setApplication] = useState<LoanApplication | null>(null);
  const [notices, setNotices] = useState<ConsentNotice[]>([]);
  const [consentHistory, setConsentHistory] = useState<ConsentRecord[]>([]);
  const [matchRuns, setMatchRuns] = useState<MatchRun[]>([]);

  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  // Draft form editing state
  const [age, setAge] = useState('');
  const [monthlyIncome, setMonthlyIncome] = useState('');
  const [workType, setWorkType] = useState<WorkType>('salaried');
  const [requestedAmount, setRequestedAmount] = useState('');

  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [isSavingDraft, setIsSavingDraft] = useState(false);
  const [saveSuccessMessage, setSaveSuccessMessage] = useState<string | null>(null);
  const [saveErrorMessage, setSaveErrorMessage] = useState<string | null>(null);

  // Consent submission state
  const [isConsentSubmitting, setIsConsentSubmitting] = useState(false);
  const [consentError, setConsentError] = useState<string | null>(null);

  const populateForm = (app: LoanApplication) => {
    setAge(String(app.age));
    setMonthlyIncome(app.monthly_income);
    setWorkType(app.work_type);
    setRequestedAmount(app.requested_amount);
  };

  const loadData = useCallback(async () => {
    if (isNaN(appId) || appId <= 0) {
      setLoadError('Invalid application ID.');
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    setLoadError(null);

    try {
      const [appData, noticeData, consentData, matchData] = await Promise.all([
        applicationService.getApplication(appId),
        consentService.getCurrentConsentNotices(),
        consentService.getApplicationConsentHistory(appId),
        matchingService.getMatchHistory(appId),
      ]);

      setApplication(appData);
      populateForm(appData);
      setNotices(noticeData);
      setConsentHistory(consentData);
      setMatchRuns(matchData.runs || []);
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 404) {
          setLoadError('Loan application not found or you do not have permission to access it.');
        } else {
          setLoadError(err.getFormattedMessage());
        }
      } else {
        setLoadError('Unable to load application details. Please check your network connection.');
      }
    } finally {
      setIsLoading(false);
    }
  }, [appId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const refreshConsents = async () => {
    if (isNaN(appId) || appId <= 0) return;
    try {
      const history = await consentService.getApplicationConsentHistory(appId);
      setConsentHistory(history);
    } catch {
      // Ignore background refresh failure
    }
  };

  const handleGrantConsent = async (purpose: string, noticeVersion: string) => {
    setIsConsentSubmitting(true);
    setConsentError(null);

    try {
      await consentService.grantApplicationConsent(appId, {
        purpose,
        notice_version: noticeVersion,
        accepted: true,
      });
      await refreshConsents();
    } catch (err) {
      if (err instanceof ApiError) {
        setConsentError(err.getFormattedMessage());
      } else {
        setConsentError('Failed to grant consent. Please try again.');
      }
    } finally {
      setIsConsentSubmitting(false);
    }
  };

  const handleRevokeConsent = async (consentId: number) => {
    setIsConsentSubmitting(true);
    setConsentError(null);

    try {
      await consentService.revokeApplicationConsent(appId, consentId);
      await refreshConsents();
    } catch (err) {
      if (err instanceof ApiError) {
        setConsentError(err.getFormattedMessage());
      } else {
        setConsentError('Failed to revoke consent. Please try again.');
      }
    } finally {
      setIsConsentSubmitting(false);
    }
  };

  const validateEditForm = (): boolean => {
    const errors: Record<string, string> = {};

    const ageNum = Number(age.trim());
    if (!age.trim()) {
      errors.age = 'Age is required.';
    } else if (!Number.isInteger(ageNum) || ageNum < 1 || ageNum > 120) {
      errors.age = 'Age must be a valid whole number between 1 and 120.';
    }

    const incomeTrimmed = monthlyIncome.trim();
    if (!incomeTrimmed) {
      errors.monthlyIncome = 'Monthly income is required.';
    } else if (!DECIMAL_REGEX.test(incomeTrimmed)) {
      errors.monthlyIncome = 'Monthly income must be a valid non-negative number with at most 2 decimal places.';
    } else if (incomeTrimmed.replace('.', '').length > 12) {
      errors.monthlyIncome = 'Monthly income cannot exceed 12 digits.';
    }

    const amountTrimmed = requestedAmount.trim();
    if (!amountTrimmed) {
      errors.requestedAmount = 'Requested loan amount is required.';
    } else if (!DECIMAL_REGEX.test(amountTrimmed) || parseFloat(amountTrimmed) <= 0) {
      errors.requestedAmount = 'Requested loan amount must be a positive number with at most 2 decimal places.';
    } else if (amountTrimmed.replace('.', '').length > 12) {
      errors.requestedAmount = 'Requested loan amount cannot exceed 12 digits.';
    }

    if (!workType || !['salaried', 'self_employed', 'other'].includes(workType)) {
      errors.workType = 'Please select a valid employment type.';
    }

    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSaveDraft = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaveSuccessMessage(null);
    setSaveErrorMessage(null);

    if (!validateEditForm()) {
      return;
    }

    setIsSavingDraft(true);

    try {
      const updatedApp = await applicationService.updateApplication(appId, {
        age: parseInt(age.trim(), 10),
        monthly_income: monthlyIncome.trim(),
        work_type: workType,
        requested_amount: requestedAmount.trim(),
      });

      setApplication(updatedApp);
      populateForm(updatedApp);
      setSaveSuccessMessage('Draft application updated successfully.');
    } catch (err) {
      if (err instanceof ApiError) {
        setSaveErrorMessage(err.getFormattedMessage());
      } else {
        setSaveErrorMessage('Failed to update draft application. Please try again.');
      }
    } finally {
      setIsSavingDraft(false);
    }
  };

  const handleMatchingSuccess = async (newRun: MatchRun) => {
    try {
      const [appData, matchData] = await Promise.all([
        applicationService.getApplication(appId),
        matchingService.getMatchHistory(appId),
      ]);
      setApplication(appData);
      setMatchRuns(matchData.runs || [newRun]);
    } catch {
      // If refresh fails, append latest run directly
      setMatchRuns((prev) => [newRun, ...prev.filter((r) => r.id !== newRun.id)]);
    }
  };

  if (isLoading) {
    return <LoadingSpinner message="Loading application details..." />;
  }

  if (loadError || !application) {
    return (
      <div style={{ maxWidth: '640px', margin: '2rem auto' }}>
        <ErrorMessage message={loadError || 'Application not found.'} />
        <div style={{ marginTop: '1.5rem', textAlign: 'center' }}>
          <Button variant="primary" onClick={() => navigate('/customer/dashboard')}>
            Back to Dashboard
          </Button>
        </div>
      </div>
    );
  }

  const isDraft = application.status === 'draft';
  const consentReadiness = getConsentReadiness(notices, consentHistory);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
        {/* Navigation & Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
          <div>
            <button
              type="button"
              className="btn btn-outline"
              style={{ fontSize: '0.8125rem', padding: '0.35rem 0.75rem', marginBottom: '0.5rem' }}
              onClick={() => navigate('/customer/dashboard')}
            >
              &larr; Back to Dashboard
            </button>
            <h2 style={{ fontSize: '1.5rem', fontWeight: 700, margin: 0 }}>
              Application #{application.id}
            </h2>
            <div style={{ fontSize: '0.8125rem', color: 'var(--color-text-muted)', marginTop: '0.25rem' }}>
              Created on {new Date(application.created_at).toLocaleString()} &bull; Last updated {new Date(application.updated_at).toLocaleString()}
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span style={{ fontSize: '0.875rem', color: 'var(--color-text-muted)' }}>Lifecycle Status:</span>
            <span
              className={`badge badge-${
                application.status === 'draft'
                  ? 'draft'
                  : application.status === 'matched'
                  ? 'status'
                  : application.status === 'accepted'
                  ? 'accepted'
                  : application.status === 'declined'
                  ? 'declined'
                  : 'submitted'
              }`}
              style={{ fontSize: '0.875rem', padding: '0.35rem 0.75rem' }}
            >
              {application.status.toUpperCase()}
            </span>
          </div>
        </div>

        {/* SECTION 1: Application Profile & Editing */}
        <Card title={isDraft ? 'Application Profile (Editable Draft)' : 'Application Profile (Read-Only)'}>
          {!isDraft ? (
            <div>
              <div className="alert alert-info" style={{ fontSize: '0.875rem', marginBottom: '1.25rem' }}>
                ℹ️ This application is in <strong>{application.status.toUpperCase()}</strong> status and is locked for editing. Only draft applications can be modified.
              </div>

              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                  gap: '1.5rem',
                  padding: '1rem 0',
                }}
              >
                <div>
                  <div style={{ fontSize: '0.8125rem', color: 'var(--color-text-muted)' }}>Age</div>
                  <div style={{ fontSize: '1.125rem', fontWeight: 600 }}>{application.age} years</div>
                </div>

                <div>
                  <div style={{ fontSize: '0.8125rem', color: 'var(--color-text-muted)' }}>Employment Type</div>
                  <div style={{ fontSize: '1.125rem', fontWeight: 600 }}>
                    {application.work_type === 'salaried'
                      ? 'Salaried Employee'
                      : application.work_type === 'self_employed'
                      ? 'Self-Employed'
                      : 'Other'}
                  </div>
                </div>

                <div>
                  <div style={{ fontSize: '0.8125rem', color: 'var(--color-text-muted)' }}>Monthly Income</div>
                  <div style={{ fontSize: '1.125rem', fontWeight: 600 }}>
                    ₹ {Number(application.monthly_income).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </div>
                </div>

                <div>
                  <div style={{ fontSize: '0.8125rem', color: 'var(--color-text-muted)' }}>Requested Amount</div>
                  <div style={{ fontSize: '1.125rem', fontWeight: 600, color: 'var(--color-primary)' }}>
                    ₹ {Number(application.requested_amount).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div>
              <p style={{ color: 'var(--color-text-muted)', fontSize: '0.875rem', marginBottom: '1.25rem' }}>
                You can adjust your profile information and requested loan amount while your application is in draft status.
              </p>

              {saveSuccessMessage && (
                <div className="alert alert-success" style={{ fontSize: '0.875rem', marginBottom: '1rem' }}>
                  ✓ {saveSuccessMessage}
                </div>
              )}

              {saveErrorMessage && (
                <div style={{ marginBottom: '1rem' }}>
                  <ErrorMessage message={saveErrorMessage} />
                </div>
              )}

              <form onSubmit={handleSaveDraft} noValidate>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '1rem' }}>
                  <Input
                    id="edit_age"
                    name="age"
                    label="Age (Years)"
                    type="number"
                    min="1"
                    max="120"
                    value={age}
                    onChange={(e) => setAge(e.target.value)}
                    error={fieldErrors.age}
                    disabled={isSavingDraft}
                    required
                  />

                  <div className="form-group">
                    <label htmlFor="edit_work_type" className="form-label">
                      Employment Type
                    </label>
                    <select
                      id="edit_work_type"
                      name="work_type"
                      className={`form-input ${fieldErrors.workType ? 'form-input-error' : ''}`}
                      value={workType}
                      onChange={(e) => setWorkType(e.target.value as WorkType)}
                      disabled={isSavingDraft}
                      aria-invalid={Boolean(fieldErrors.workType)}
                      aria-describedby={fieldErrors.workType ? 'edit_work_type-error' : undefined}
                      required
                    >
                      <option value="salaried">Salaried Employee</option>
                      <option value="self_employed">Self-Employed / Business Owner</option>
                      <option value="other">Other</option>
                    </select>
                    {fieldErrors.workType && (
                      <p id="edit_work_type-error" className="form-error-text" role="alert">
                        {fieldErrors.workType}
                      </p>
                    )}
                  </div>

                  <Input
                    id="edit_monthly_income"
                    name="monthly_income"
                    label="Monthly Income (₹)"
                    type="text"
                    value={monthlyIncome}
                    onChange={(e) => setMonthlyIncome(e.target.value)}
                    error={fieldErrors.monthlyIncome}
                    disabled={isSavingDraft}
                    required
                  />

                  <Input
                    id="edit_requested_amount"
                    name="requested_amount"
                    label="Requested Loan Amount (₹)"
                    type="text"
                    value={requestedAmount}
                    onChange={(e) => setRequestedAmount(e.target.value)}
                    error={fieldErrors.requestedAmount}
                    disabled={isSavingDraft}
                    required
                  />
                </div>

                <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '1.25rem' }}>
                  <Button
                    type="submit"
                    variant="primary"
                    isLoading={isSavingDraft}
                    disabled={isSavingDraft}
                  >
                    Save Changes
                  </Button>
                </div>
              </form>
            </div>
          )}
        </Card>

        {/* SECTION 2: Consent Management */}
        <div>
          <div style={{ marginBottom: '1rem' }}>
            <h3 style={{ fontSize: '1.25rem', fontWeight: 600, margin: 0 }}>
              Data Privacy & Lending Consents
            </h3>
            <p style={{ fontSize: '0.875rem', color: 'var(--color-text-muted)', margin: '0.25rem 0 0 0' }}>
              To evaluate eligibility across mock lenders, explicit consent is required for each distinct processing purpose. Consents are strictly purpose-specific and tied to published notice versions.
            </p>
          </div>

          {consentError && (
            <div style={{ marginBottom: '1rem' }}>
              <ErrorMessage message={consentError} />
            </div>
          )}

          {notices.length === 0 ? (
            <p style={{ color: 'var(--color-text-muted)', fontSize: '0.875rem' }}>
              No consent notices are currently published.
            </p>
          ) : (
            notices.map((notice) => {
              const activeConsent = consentHistory.find(
                (c) =>
                  c.purpose === notice.purpose &&
                  c.notice_version === notice.notice_version &&
                  c.status === 'granted' &&
                  !c.revoked_at
              );

              const revokedConsent = consentHistory.find(
                (c) =>
                  c.purpose === notice.purpose &&
                  c.notice_version === notice.notice_version &&
                  c.status === 'revoked'
              );

              return (
                <ConsentNoticeCard
                  key={`${notice.purpose}-${notice.notice_version}`}
                  notice={notice}
                  activeConsent={activeConsent}
                  revokedConsent={revokedConsent}
                  onGrant={handleGrantConsent}
                  onRevoke={handleRevokeConsent}
                  isSubmitting={isConsentSubmitting}
                />
              );
            })
          )}

          {/* Consent History Audit Log */}
          <div style={{ marginTop: '1.5rem' }}>
            <Card title="Consent Event Audit History">
              <p style={{ fontSize: '0.8125rem', color: 'var(--color-text-muted)', marginBottom: '1rem' }}>
                Immutable chronological log of all consent grant and revocation actions recorded for this application.
              </p>
              <ConsentHistoryList history={consentHistory} />
            </Card>
          </div>
        </div>

        {/* SECTION 3: Multi-Lender Eligibility Matching */}
        <div>
          <MatchingSection
            applicationId={application.id}
            applicationStatus={application.status}
            consentReadiness={consentReadiness}
            onMatchingSuccess={handleMatchingSuccess}
            onConsentConflict={refreshConsents}
          />
        </div>

        {/* SECTION 4: Matching History */}
        <div>
          <Card title="Historical Matching Runs">
            <p style={{ fontSize: '0.8125rem', color: 'var(--color-text-muted)', marginBottom: '1rem' }}>
              Chronological log of multi-lender eligibility evaluations performed for this application. Each run preserves the lender policies active at evaluation time.
            </p>
            <MatchHistoryList runs={matchRuns} />
          </Card>
        </div>
      </div>
  );
};
