import React from 'react';
import { MatchRun } from '../types';

export interface MatchHistoryListProps {
  runs: MatchRun[];
}

export const MatchHistoryList: React.FC<MatchHistoryListProps> = ({ runs }) => {
  if (runs.length === 0) {
    return (
      <div style={{ color: 'var(--color-text-muted)', fontSize: '0.875rem', padding: '1rem 0' }}>
        No matching runs have been performed yet.
      </div>
    );
  }

  // Sort newest run first (by run_number descending or started_at descending)
  const sortedRuns = [...runs].sort((a, b) => b.run_number - a.run_number);
  const latestRunNumber = sortedRuns[0]?.run_number;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      <div style={{ fontSize: '0.875rem', color: 'var(--color-text-muted)' }}>
        Total matching executions: <strong>{runs.length}</strong>
      </div>

      {sortedRuns.map((run) => {
        const isLatest = run.run_number === latestRunNumber;

        return (
          <div
            key={run.id}
            className="card"
            style={{
              border: isLatest ? '1.5px solid var(--color-primary)' : '1px solid var(--color-border)',
              backgroundColor: '#ffffff',
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
                paddingBottom: '0.5rem',
                borderBottom: '1px solid var(--color-border)',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <h4 style={{ margin: 0, fontSize: '1rem', fontWeight: 600 }}>
                  Matching Run #{run.run_number}
                </h4>
                {isLatest && (
                  <span
                    className="badge badge-primary"
                    style={{
                      fontSize: '0.75rem',
                      backgroundColor: 'var(--color-primary)',
                      color: '#ffffff',
                    }}
                  >
                    Latest Run
                  </span>
                )}
                <span className="badge badge-status" style={{ fontSize: '0.75rem' }}>
                  {run.status.toUpperCase()}
                </span>
              </div>

              <div style={{ fontSize: '0.8125rem', color: 'var(--color-text-muted)' }}>
                Started: {new Date(run.started_at).toLocaleString()}
                {run.completed_at && (
                  <span> &bull; Completed: {new Date(run.completed_at).toLocaleString()}</span>
                )}
              </div>
            </div>

            {/* Decisions List */}
            {run.decisions.length === 0 ? (
              <p style={{ color: 'var(--color-text-muted)', fontSize: '0.875rem', margin: 0 }}>
                No lender decisions recorded for this run.
              </p>
            ) : (
              <div className="table-responsive">
                <table className="data-table" aria-label={`Decisions for Run #${run.run_number}`}>
                  <thead>
                    <tr>
                      <th>Lender</th>
                      <th>Lender Code</th>
                      <th>Policy Version</th>
                      <th>Decision</th>
                      <th>Evaluation / Reason</th>
                    </tr>
                  </thead>
                  <tbody>
                    {run.decisions.map((decision) => {
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
                              <div style={{ color: 'var(--color-danger)' }}>
                                <strong>[{decision.exclusion_reason_code || 'EXCLUDED'}]</strong>{' '}
                                {decision.exclusion_reason}
                              </div>
                            ) : (
                              <span style={{ color: 'var(--color-success)' }}>
                                Met all policy criteria
                              </span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};
