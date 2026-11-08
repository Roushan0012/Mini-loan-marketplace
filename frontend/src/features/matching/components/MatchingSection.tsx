import React, { useState } from 'react';
import { LoanApplicationStatus } from '../../customer/types';
import { ConsentReadiness } from '../../consents/types';
import { MatchRun } from '../types';
import { matchingService } from '../services/matchingService';
import { Button } from '../../../components/ui/Button';
import { ApiError } from '../../../services/apiErrors';

export interface MatchingSectionProps {
  applicationId: number;
  applicationStatus: LoanApplicationStatus;
  consentReadiness: ConsentReadiness;
  onMatchingSuccess: (newRun: MatchRun) => void;
  onConsentConflict?: () => void;
}

export const MatchingSection: React.FC<MatchingSectionProps> = ({
  applicationId,
  applicationStatus,
  consentReadiness,
  onMatchingSuccess,
  onConsentConflict,
}) => {
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [latestRun, setLatestRun] = useState<MatchRun | null>(null);

  const isStatusAllowed = applicationStatus === 'draft' || applicationStatus === 'matched';
  const canRunMatching = isStatusAllowed && consentReadiness.isReady && !isRunning;

  const handleRunMatching = async () => {
    if (!canRunMatching) return;

    setIsRunning(true);
    setError(null);

    try {
      const run = await matchingService.runMatching(applicationId);
      setLatestRun(run);
      onMatchingSuccess(run);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.getFormattedMessage());
        if (err.status === 409 && onConsentConflict) {
          onConsentConflict();
        }
      } else {
        setError('An unexpected error occurred while executing matching.');
      }
    } finally {
      setIsRunning(false);
    }
  };

  return (
    <div className="card" style={{ marginBottom: '1.5rem' }}>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '0.75rem',
          marginBottom: '1rem',
        }}
      >
        <div>
          <h3 style={{ fontSize: '1.125rem', fontWeight: 600, margin: 0 }}>
            Mock Lender Eligibility Matching
          </h3>
          <p style={{ fontSize: '0.8125rem', color: 'var(--color-text-muted)', margin: '0.25rem 0 0 0' }}>
            Deterministic multi-lender rule evaluation based on your application profile and active consents.
          </p>
        </div>

        <div>
          <span className="badge badge-status" style={{ fontSize: '0.8125rem' }}>
            Application Status: <strong>{applicationStatus.toUpperCase()}</strong>
          </span>
        </div>
      </div>

      {/* Consent Readiness Notice */}
      {!consentReadiness.isReady ? (
        <div className="alert alert-warning" style={{ fontSize: '0.875rem', marginBottom: '1rem' }}>
          <strong>⚠️ Consent Required:</strong> Matching cannot proceed until all required consents are actively granted.
          {consentReadiness.missingPurposes.length > 0 && (
            <div style={{ marginTop: '0.25rem' }}>
              Pending required consents: {consentReadiness.missingPurposes.map((p) => <code key={p} style={{ marginRight: '0.25rem' }}>{p}</code>)}
            </div>
          )}
        </div>
      ) : (
        <div className="alert alert-success" style={{ fontSize: '0.875rem', marginBottom: '1rem' }}>
          ✓ All required consents are actively granted. This application is ready for eligibility evaluation.
        </div>
      )}

      {/* Status Warning if not draft or matched */}
      {!isStatusAllowed && (
        <div className="alert alert-info" style={{ fontSize: '0.875rem', marginBottom: '1rem' }}>
          ℹ️ Matching can only be performed when the application is in <strong>DRAFT</strong> or <strong>MATCHED</strong> status. Current status: <code>{applicationStatus}</code>.
        </div>
      )}

      {/* Error Banner */}
      {error && (
        <div className="alert alert-danger" style={{ fontSize: '0.875rem', marginBottom: '1rem' }}>
          {error}
        </div>
      )}

      {/* Matching Action Button */}
      <div style={{ marginBottom: latestRun ? '1.5rem' : '0.5rem' }}>
        <Button
          type="button"
          variant="primary"
          onClick={handleRunMatching}
          disabled={!canRunMatching}
          isLoading={isRunning}
        >
          {applicationStatus === 'matched' ? 'Re-run Lender Matching' : 'Run Lender Matching'}
        </Button>
      </div>

      {/* Latest Evaluation Result Display (if just executed or passed) */}
      {latestRun && (
        <div
          style={{
            padding: '1rem',
            backgroundColor: 'var(--color-bg-alt, #f8fafc)',
            border: '1px solid var(--color-border)',
            borderRadius: 'var(--radius-sm)',
            marginTop: '1rem',
          }}
        >
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              flexWrap: 'wrap',
              gap: '0.5rem',
              marginBottom: '0.75rem',
            }}
          >
            <h4 style={{ margin: 0, fontSize: '0.9375rem', fontWeight: 600 }}>
              Latest Execution Results (Run #{latestRun.run_number})
            </h4>
            <span className="badge badge-accepted" style={{ fontSize: '0.75rem' }}>
              Execution {latestRun.status.toUpperCase()}
            </span>
          </div>

          <div className="table-responsive">
            <table className="data-table" aria-label="Latest Matching Run Decisions">
              <thead>
                <tr>
                  <th>Lender</th>
                  <th>Code</th>
                  <th>Policy Version</th>
                  <th>Eligibility</th>
                  <th>Evaluation Detail</th>
                </tr>
              </thead>
              <tbody>
                {latestRun.decisions.map((decision) => {
                  const isEligible = decision.decision_status === 'eligible';
                  return (
                    <tr key={decision.id}>
                      <td style={{ fontWeight: 500 }}>{decision.lender_name}</td>
                      <td>
                        <code>{decision.lender_code}</code>
                      </td>
                      <td>{decision.policy_version_snapshot}</td>
                      <td>
                        {isEligible ? (
                          <span className="badge badge-accepted">ELIGIBLE</span>
                        ) : (
                          <span className="badge badge-declined">INELIGIBLE</span>
                        )}
                      </td>
                      <td style={{ fontSize: '0.8125rem' }}>
                        {decision.exclusion_reason ? (
                          <span style={{ color: 'var(--color-danger)' }}>
                            <strong>[{decision.exclusion_reason_code || 'EXCLUDED'}]</strong>{' '}
                            {decision.exclusion_reason}
                          </span>
                        ) : (
                          <span style={{ color: 'var(--color-success)' }}>
                            Passed all eligibility criteria
                          </span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};
