import { describe, it, expect } from 'vitest';
import {
  sumStatusCounts,
  formatAdminStatusLabel,
  getStatusBreakdownItems,
  getApplicationCountConsistency,
  getEventCountSummary,
} from './adminMetrics';
import { AdminMetrics } from '../types';

describe('Admin Metrics Utilities Unit Tests', () => {
  it('1. Sum a normal status count map', () => {
    const counts = { draft: 10, matched: 15, submitted: 25 };
    expect(sumStatusCounts(counts)).toBe(50);
  });

  it('2. Empty map returns zero', () => {
    expect(sumStatusCounts({})).toBe(0);
    expect(sumStatusCounts(null)).toBe(0);
    expect(sumStatusCounts(undefined)).toBe(0);
  });

  it('3. Negative or invalid counts are handled safely', () => {
    const counts = {
      draft: 10,
      invalid_neg: -5,
      invalid_nan: NaN,
      valid: 5,
    };
    expect(sumStatusCounts(counts)).toBe(15);
  });

  it('4. Status items sorted descending by count', () => {
    const counts = {
      draft: 10,
      accepted: 40,
      submitted: 20,
    };
    const items = getStatusBreakdownItems(counts);
    expect(items.map((i) => i.status)).toEqual(['accepted', 'submitted', 'draft']);
    expect(items.map((i) => i.count)).toEqual([40, 20, 10]);
  });

  it('5. Equal counts have deterministic label ordering (alphabetical tie-breaker)', () => {
    const counts = {
      zebra_status: 10,
      alpha_status: 10,
      beta_status: 10,
    };
    const items = getStatusBreakdownItems(counts);
    expect(items.map((i) => i.label)).toEqual([
      'Alpha Status',
      'Beta Status',
      'Zebra Status',
    ]);
  });

  it('6. Percentages calculated from the breakdown total', () => {
    const counts = {
      draft: 25,
      submitted: 75,
    };
    const items = getStatusBreakdownItems(counts);
    expect(items[0].percentage).toBe(75.0);
    expect(items[1].percentage).toBe(25.0);
  });

  it('7. Zero denominator does not create NaN or Infinity', () => {
    const counts = {
      draft: 0,
      submitted: 0,
    };
    const items = getStatusBreakdownItems(counts);
    expect(items[0].percentage).toBe(0);
    expect(items[1].percentage).toBe(0);
    expect(Number.isNaN(items[0].percentage)).toBe(false);
  });

  it('8. Unknown status formats safely', () => {
    expect(formatAdminStatusLabel('unknown_custom_policy_v2')).toBe('Unknown Custom Policy V2');
    expect(formatAdminStatusLabel('')).toBe('Unknown');
  });

  it('9. offer_selected formats to Offer Selected', () => {
    expect(formatAdminStatusLabel('offer_selected')).toBe('Offer Selected');
  });

  it('10. timed_out formats to Timed Out', () => {
    expect(formatAdminStatusLabel('timed_out')).toBe('Timed Out');
  });

  it('11. Application count consistency when totals match', () => {
    const metrics: AdminMetrics = {
      total_leads: 100,
      total_applications: 50,
      total_match_runs: 40,
      total_offers: 120,
      total_submissions: 30,
      applications_by_status: {
        draft: 20,
        matched: 10,
        offer_selected: 5,
        submitted: 15,
      },
      lender_events_by_processing_status: {
        processed: 25,
      },
    };

    const result = getApplicationCountConsistency(metrics);
    expect(result.isConsistent).toBe(true);
    expect(result.groupedTotal).toBe(50);
    expect(result.reportedTotal).toBe(50);
    expect(result.difference).toBe(0);
  });

  it('12 & 13. Application count mismatch is reported and difference calculated correctly', () => {
    const metrics: AdminMetrics = {
      total_leads: 100,
      total_applications: 55, // Reported 55
      total_match_runs: 40,
      total_offers: 120,
      total_submissions: 30,
      applications_by_status: {
        draft: 20,
        matched: 10, // Sum = 30
      },
      lender_events_by_processing_status: {},
    };

    const result = getApplicationCountConsistency(metrics);
    expect(result.isConsistent).toBe(false);
    expect(result.groupedTotal).toBe(30);
    expect(result.reportedTotal).toBe(55);
    expect(result.difference).toBe(-25);
  });

  it('14. Event count summary derived from grouped event counts', () => {
    const metrics: AdminMetrics = {
      total_leads: 10,
      total_applications: 10,
      total_match_runs: 10,
      total_offers: 10,
      total_submissions: 10,
      applications_by_status: {},
      lender_events_by_processing_status: {
        received: 4,
        processed: 12,
        ignored: 2,
        failed: 1,
      },
    };

    expect(getEventCountSummary(metrics)).toBe(19);
  });
});
