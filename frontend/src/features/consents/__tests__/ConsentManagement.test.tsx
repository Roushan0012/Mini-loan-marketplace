import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ConsentNoticeCard } from '../components/ConsentNoticeCard';
import { ConsentHistoryList } from '../components/ConsentHistoryList';
import { getConsentReadiness } from '../utils/consentReadiness';
import { ConsentNotice, ConsentRecord } from '../types';

describe('Consent Management & Readiness Tests', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  const mockNotice1: ConsentNotice = {
    purpose: 'eligibility_matching',
    title: 'Eligibility Evaluation Notice',
    notice_version: 'v1.0',
    notice_text: 'Explicit terms authorizing multi-lender credit and eligibility calculations.',
    required_for_matching: true,
  };

  const mockNotice2: ConsentNotice = {
    purpose: 'sharing_with_mock_lenders',
    title: 'Mock Lender Data Sharing Notice',
    notice_version: 'v1.0',
    notice_text: 'Explicit terms authorizing transmitting financial parameters to mock lenders.',
    required_for_matching: true,
  };

  const mockGrantedRecord: ConsentRecord = {
    id: 10,
    application_id: 1,
    purpose: 'eligibility_matching',
    notice_version: 'v1.0',
    status: 'granted',
    granted_at: '2026-03-01T12:00:00Z',
    revoked_at: null,
    created_at: '2026-03-01T12:00:00Z',
  };

  const mockRevokedRecord: ConsentRecord = {
    id: 11,
    application_id: 1,
    purpose: 'eligibility_matching',
    notice_version: 'v1.0',
    status: 'revoked',
    granted_at: '2026-03-01T12:00:00Z',
    revoked_at: '2026-03-01T14:00:00Z',
    created_at: '2026-03-01T12:00:00Z',
  };

  it('18, 19, & 20. Displays notice title, purpose code, version v1.0, and checkbox is unchecked by default', () => {
    const onGrant = vi.fn();
    const onRevoke = vi.fn();

    render(
      <ConsentNoticeCard
        notice={mockNotice1}
        onGrant={onGrant}
        onRevoke={onRevoke}
      />
    );

    expect(screen.getByRole('heading', { name: 'Eligibility Evaluation Notice' })).toBeInTheDocument();
    expect(screen.getByText('eligibility_matching')).toBeInTheDocument();
    expect(screen.getByText('v1.0')).toBeInTheDocument();
    expect(screen.getByText('(Required for Matching)')).toBeInTheDocument();

    const checkbox = screen.getByRole('checkbox') as HTMLInputElement;
    expect(checkbox.checked).toBe(false);

    // Grant button should be disabled until checkbox is checked
    const grantBtn = screen.getByRole('button', { name: /Grant Consent/i });
    expect(grantBtn).toBeDisabled();
  });

  it('21, 22, & 23. User explicitly checks and grants consent with purpose and version, without customer ID or role', async () => {
    const onGrant = vi.fn().mockResolvedValue(undefined);
    const onRevoke = vi.fn();

    render(
      <ConsentNoticeCard
        notice={mockNotice1}
        onGrant={onGrant}
        onRevoke={onRevoke}
      />
    );

    const checkbox = screen.getByRole('checkbox');
    const grantBtn = screen.getByRole('button', { name: /Grant Consent/i });

    fireEvent.click(checkbox);
    expect(grantBtn).toBeEnabled();

    fireEvent.click(grantBtn);

    await waitFor(() => {
      expect(onGrant).toHaveBeenCalledTimes(1);
    });

    expect(onGrant).toHaveBeenCalledWith('eligibility_matching', 'v1.0');
  });

  it('25. Existing granted current-version consent appears active with status badge and revoke button', () => {
    const onGrant = vi.fn();
    const onRevoke = vi.fn();

    render(
      <ConsentNoticeCard
        notice={mockNotice1}
        activeConsent={mockGrantedRecord}
        onGrant={onGrant}
        onRevoke={onRevoke}
      />
    );

    expect(screen.getByText('Active / Granted')).toBeInTheDocument();
    expect(screen.getByText(/✓ Consent active/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Revoke Consent/i })).toBeInTheDocument();
    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument();
  });

  it('26 & 30. Revoked consent shows Revoked badge and informs user that a newly published version is required', () => {
    const onGrant = vi.fn();
    const onRevoke = vi.fn();

    render(
      <ConsentNoticeCard
        notice={mockNotice1}
        revokedConsent={mockRevokedRecord}
        onGrant={onGrant}
        onRevoke={onRevoke}
      />
    );

    expect(screen.getByText('Revoked')).toBeInTheDocument();
    expect(screen.getByText(/Consent Revoked for this Version/i)).toBeInTheDocument();
    expect(
      screen.getByText(/a newly published notice version is required before this consent can be granted again/i)
    ).toBeInTheDocument();
    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument();
  });

  it('28 & 29. Revocation requires explicit confirmation before calling onRevoke', async () => {
    const onGrant = vi.fn();
    const onRevoke = vi.fn().mockResolvedValue(undefined);

    render(
      <ConsentNoticeCard
        notice={mockNotice1}
        activeConsent={mockGrantedRecord}
        onGrant={onGrant}
        onRevoke={onRevoke}
      />
    );

    const revokeBtn = screen.getByRole('button', { name: /Revoke Consent/i });
    fireEvent.click(revokeBtn);

    // Confirmation warning must appear
    expect(screen.getByText(/⚠️ Are you sure you want to revoke this consent\?/i)).toBeInTheDocument();
    expect(onRevoke).not.toHaveBeenCalled();

    // Confirm
    const confirmBtn = screen.getByRole('button', { name: /Confirm Revocation/i });
    fireEvent.click(confirmBtn);

    await waitFor(() => {
      expect(onRevoke).toHaveBeenCalledWith(10);
    });
  });

  it('24. Consent history list displays audit records chronologically newest first', () => {
    const olderRecord: ConsentRecord = {
      id: 1,
      application_id: 1,
      purpose: 'eligibility_matching',
      notice_version: 'v0.9',
      status: 'granted',
      granted_at: '2026-01-01T10:00:00Z',
      revoked_at: null,
      created_at: '2026-01-01T10:00:00Z',
    };

    const newerRecord: ConsentRecord = {
      id: 2,
      application_id: 1,
      purpose: 'sharing_with_mock_lenders',
      notice_version: 'v1.0',
      status: 'granted',
      granted_at: '2026-02-01T10:00:00Z',
      revoked_at: null,
      created_at: '2026-02-01T10:00:00Z',
    };

    render(<ConsentHistoryList history={[olderRecord, newerRecord]} />);

    const rows = screen.getAllByRole('row');
    // Header row + 2 data rows
    expect(rows).toHaveLength(3);
    // Newer record (#2) should come before older (#1)
    expect(rows[1]).toHaveTextContent('#2');
    expect(rows[2]).toHaveTextContent('#1');
  });

  it('31. getConsentReadiness helper evaluates full readiness matrix correctly', () => {
    const notices = [mockNotice1, mockNotice2];

    // Case A: No consent granted
    const resA = getConsentReadiness(notices, []);
    expect(resA.isReady).toBe(false);
    expect(resA.missingPurposes).toEqual(['eligibility_matching', 'sharing_with_mock_lenders']);
    expect(resA.grantedPurposes).toEqual([]);

    // Case B: Only one granted
    const resB = getConsentReadiness(notices, [mockGrantedRecord]);
    expect(resB.isReady).toBe(false);
    expect(resB.missingPurposes).toEqual(['sharing_with_mock_lenders']);
    expect(resB.grantedPurposes).toEqual(['eligibility_matching']);

    // Case C: Both granted on current version v1.0
    const mockGrantedRecord2: ConsentRecord = {
      id: 12,
      application_id: 1,
      purpose: 'sharing_with_mock_lenders',
      notice_version: 'v1.0',
      status: 'granted',
      granted_at: '2026-03-01T12:05:00Z',
      revoked_at: null,
      created_at: '2026-03-01T12:05:00Z',
    };
    const resC = getConsentReadiness(notices, [mockGrantedRecord, mockGrantedRecord2]);
    expect(resC.isReady).toBe(true);
    expect(resC.missingPurposes).toEqual([]);
    expect(resC.grantedPurposes).toHaveLength(2);

    // Case D: Older version v0.9 granted (does NOT fulfill v1.0)
    const oldVersionRecord: ConsentRecord = {
      ...mockGrantedRecord,
      notice_version: 'v0.9',
    };
    const resD = getConsentReadiness(notices, [oldVersionRecord, mockGrantedRecord2]);
    expect(resD.isReady).toBe(false);
    expect(resD.missingPurposes).toEqual(['eligibility_matching']);

    // Case E: Revoked record (does NOT fulfill readiness)
    const resE = getConsentReadiness(notices, [mockRevokedRecord, mockGrantedRecord2]);
    expect(resE.isReady).toBe(false);
    expect(resE.missingPurposes).toEqual(['eligibility_matching']);
  });
});
