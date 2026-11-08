import React from 'react';
import { ConsentStatus } from '../types';

export interface ConsentStatusBadgeProps {
  status: ConsentStatus | 'not_granted';
}

export const ConsentStatusBadge: React.FC<ConsentStatusBadgeProps> = ({ status }) => {
  switch (status) {
    case 'granted':
      return <span className="badge badge-accepted">Active / Granted</span>;
    case 'revoked':
      return <span className="badge badge-declined">Revoked</span>;
    case 'pending':
      return <span className="badge badge-submitted">Pending</span>;
    case 'not_granted':
    default:
      return <span className="badge badge-status">Not Granted</span>;
  }
};
