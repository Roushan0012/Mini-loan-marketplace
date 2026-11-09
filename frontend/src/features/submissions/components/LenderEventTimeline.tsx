import React from 'react';
import { LenderEventHistoryItem } from '../types';

export interface LenderEventTimelineProps {
  events: LenderEventHistoryItem[];
  onRefresh?: () => void;
  isRefreshing?: boolean;
}

export const LenderEventTimeline: React.FC<LenderEventTimelineProps> = ({
  events,
  onRefresh,
  isRefreshing = false,
}) => {
  return (
    <div className="card" style={{ marginTop: '1.5rem' }}>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '0.75rem',
          marginBottom: '1rem',
          paddingBottom: '0.5rem',
          borderBottom: '1px solid var(--color-border)',
        }}
      >
        <div>
          <h4 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 600 }}>
            Simulated Lender Event Ledger
          </h4>
          <p style={{ margin: '0.2rem 0 0 0', fontSize: '0.8125rem', color: 'var(--color-text-muted)' }}>
            Immutable webhook event audit stream received from the fictional lender integration.
          </p>
        </div>

        {onRefresh && (
          <button
            type="button"
            className="btn btn-outline"
            style={{ fontSize: '0.8125rem', padding: '0.35rem 0.75rem' }}
            onClick={onRefresh}
            disabled={isRefreshing}
          >
            {isRefreshing ? 'Refreshing...' : '↻ Refresh Events'}
          </button>
        )}
      </div>

      {events.length === 0 ? (
        <div style={{ padding: '1rem 0', color: 'var(--color-text-muted)', fontSize: '0.875rem' }}>
          No webhook events recorded yet. Simulated lender response events will be audited here once dispatched.
        </div>
      ) : (
        <div className="table-responsive">
          <table className="data-table" aria-label="Mock Lender Webhook Events">
            <thead>
              <tr>
                <th>Seq #</th>
                <th>Event Type</th>
                <th>Processing Status</th>
                <th>Reason Code</th>
                <th>Occurred At</th>
                <th>Received At</th>
              </tr>
            </thead>
            <tbody>
              {events.map((evt) => {
                const reasonCode =
                  evt.event_payload && typeof evt.event_payload === 'object' && 'reason_code' in evt.event_payload
                    ? String((evt.event_payload as Record<string, unknown>).reason_code || '')
                    : '';

                const isProcessed = evt.processing_status === 'processed';
                const isIgnored = evt.processing_status === 'ignored';

                return (
                  <tr key={evt.id}>
                    <td style={{ fontWeight: 600 }}>
                      #{evt.sequence_number ?? evt.id}
                    </td>
                    <td>
                      <code>{evt.event_type}</code>
                    </td>
                    <td>
                      <span
                        className={`badge badge-${isProcessed ? 'accepted' : isIgnored ? 'status' : 'declined'}`}
                        style={{ fontSize: '0.75rem' }}
                      >
                        {evt.processing_status.toUpperCase()}
                      </span>
                    </td>
                    <td style={{ fontSize: '0.8125rem' }}>
                      {reasonCode ? <code>{reasonCode}</code> : '—'}
                    </td>
                    <td style={{ fontSize: '0.8125rem', color: 'var(--color-text-muted)' }}>
                      {new Date(evt.occurred_at).toLocaleString()}
                    </td>
                    <td style={{ fontSize: '0.8125rem', color: 'var(--color-text-muted)' }}>
                      {new Date(evt.received_at).toLocaleString()}
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
};
