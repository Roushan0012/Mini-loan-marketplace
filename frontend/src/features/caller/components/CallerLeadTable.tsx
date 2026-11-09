import React from 'react';
import { CallerLead } from '../types';
import { formatRupees } from '../../offers/utils/formatMoney';
import { CallerLeadStatusBadge } from './CallerLeadStatusBadge';

interface CallerLeadTableProps {
  leads: CallerLead[];
  onSelectLead: (lead: CallerLead) => void;
}

export const CallerLeadTable: React.FC<CallerLeadTableProps> = ({
  leads,
  onSelectLead,
}) => {
  const formatWorkType = (wt: string) => {
    switch (wt) {
      case 'salaried':
        return 'Salaried';
      case 'self_employed':
        return 'Self-Employed';
      case 'other':
        return 'Other';
      default:
        return wt.replace(/_/g, ' ');
    }
  };

  return (
    <div className="table-responsive">
      <table className="data-table" aria-label="Assigned leads table">
        <thead>
          <tr>
            <th scope="col">Ref ID</th>
            <th scope="col">Applicant Name</th>
            <th scope="col">Requested Amount</th>
            <th scope="col">Monthly Income</th>
            <th scope="col">Work Type</th>
            <th scope="col">Status</th>
            <th scope="col">Assigned Date</th>
            <th scope="col" style={{ textAlign: 'right' }}>Actions</th>
          </tr>
        </thead>
        <tbody>
          {leads.map((lead) => (
            <tr key={lead.id}>
              <td style={{ fontWeight: 600 }}>
                <code>{lead.synthetic_reference}</code>
              </td>
              <td style={{ fontWeight: 500 }}>{lead.applicant_name}</td>
              <td style={{ fontWeight: 600 }}>
                {formatRupees(lead.requested_amount)}
              </td>
              <td>{formatRupees(lead.monthly_income)}</td>
              <td>{formatWorkType(lead.work_type)}</td>
              <td>
                <CallerLeadStatusBadge status={lead.status} />
              </td>
              <td style={{ color: 'var(--color-text-muted)' }}>
                {new Date(lead.assigned_at).toLocaleDateString()}
              </td>
              <td style={{ textAlign: 'right' }}>
                <button
                  type="button"
                  className="btn btn-outline"
                  onClick={() => onSelectLead(lead)}
                  aria-label={`View details for ${lead.synthetic_reference}`}
                  style={{
                    padding: '0.35rem 0.75rem',
                    fontSize: '0.8125rem',
                  }}
                >
                  View Details
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};
