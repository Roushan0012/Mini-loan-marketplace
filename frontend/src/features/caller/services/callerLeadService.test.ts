import { describe, it, expect, vi, beforeEach } from 'vitest';
import { callerLeadService } from './callerLeadService';
import { apiClient } from '../../../services/apiClient';
import { ApiError } from '../../../services/apiErrors';
import { CallerLead } from '../types';

describe('CallerLeadService Unit Tests', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  const mockLeads: CallerLead[] = [
    {
      id: 1,
      synthetic_reference: 'SYN-LEAD-001',
      applicant_name: 'John Doe',
      age: 32,
      monthly_income: '60000.00',
      work_type: 'salaried',
      requested_amount: '300000.00',
      status: 'new',
      assigned_at: '2026-03-01T10:00:00Z',
    },
  ];

  it('Calls GET /caller/leads with default limit=25 and offset=0', async () => {
    const getSpy = vi.spyOn(apiClient, 'get').mockResolvedValue(mockLeads);

    const result = await callerLeadService.getAssignedLeads();

    expect(getSpy).toHaveBeenCalledTimes(1);
    expect(getSpy).toHaveBeenCalledWith('/caller/leads?limit=25&offset=0');
    expect(result).toEqual(mockLeads);
  });

  it('Supports custom pagination parameters without passing caller_id or role', async () => {
    const getSpy = vi.spyOn(apiClient, 'get').mockResolvedValue([]);

    await callerLeadService.getAssignedLeads(50, 100);

    expect(getSpy).toHaveBeenCalledWith('/caller/leads?limit=50&offset=100');
    const [endpoint] = getSpy.mock.calls[0];
    expect(endpoint).not.toContain('caller_id');
    expect(endpoint).not.toContain('customer_id');
    expect(endpoint).not.toContain('role');
  });

  it('Propagates API errors correctly', async () => {
    vi.spyOn(apiClient, 'get').mockRejectedValue(
      new ApiError(403, 'Caller access required.')
    );

    await expect(callerLeadService.getAssignedLeads()).rejects.toThrow('Caller access required.');
  });
});
