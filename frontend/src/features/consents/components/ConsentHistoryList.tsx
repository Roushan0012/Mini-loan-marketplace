import React from 'react';
import { ConsentRecord } from '../types';
import { ConsentStatusBadge } from './ConsentStatusBadge';

export interface ConsentHistoryListProps {
  history: ConsentRecord[];
}

export const ConsentHistoryList: React.FC<ConsentHistoryListProps> = ({ history }) => {
  if (history.length === 0) {
    return (
      <p style={{ color: 'var(--color-text-muted)', fontSize: '0.875rem' }}>
        No consent events recorded for this application yet.
      </p>
    );
  }

  // Display newest consent actions first
  const sortedHistory = [...history].sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  );

  return (
    <div className="table-responsive">
      <table className="data-table" aria-label="Consent event audit history">
        <thead>
          <tr>
            <th>ID</th>
            <th>Purpose</th>
            <th>Version</th>
            <th>Status</th>
            <th>Granted Date</th>
            <th>Revoked Date</th>
            <th>Recorded At</th>
          </tr>
        </thead>
        <tbody>
          {sortedHistory.map((record) => (
            <tr key={record.id}>
              <td>#{record.id}</td>
              <td><code>{record.purpose}</code></td>
              <td>{record.notice_version}</td>
              <td>
                <ConsentStatusBadge status={record.status} />
              </td>
              <td>
                {record.granted_at ? new Date(record.granted_at).toLocaleString() : '—'}
              </td>
              <td>
                {record.revoked_at ? (
                  <span style={{ color: 'var(--color-danger)' }}>
                    {new Date(record.revoked_at).toLocaleString()}
                  </span>
                ) : (
                  '—'
                )}
              </td>
              <td style={{ color: 'var(--color-text-muted)' }}>
                {new Date(record.created_at).toLocaleString()}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};
