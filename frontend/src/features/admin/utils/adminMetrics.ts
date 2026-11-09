import { AdminMetrics, ApplicationConsistencyResult, StatusBreakdownItem } from '../types';

/**
 * Sum a dictionary of status counts, validating that values are non-negative integers.
 * Ignores invalid, negative, or non-finite numbers safely.
 */
export function sumStatusCounts(counts: Record<string, number> | null | undefined): number {
  if (!counts || typeof counts !== 'object') {
    return 0;
  }

  let total = 0;
  for (const key of Object.keys(counts)) {
    const rawVal = counts[key];
    if (typeof rawVal === 'number' && Number.isFinite(rawVal) && rawVal > 0) {
      total += Math.floor(rawVal);
    }
  }
  return total;
}

/**
 * Convert snake_case status keys into readable Title Case labels.
 *
 * Examples:
 *   "offer_selected" -> "Offer Selected"
 *   "timed_out"      -> "Timed Out"
 *   "in_progress"    -> "In Progress"
 */
export function formatAdminStatusLabel(status: string): string {
  if (!status || typeof status !== 'string') {
    return 'Unknown';
  }

  return status
    .trim()
    .split('_')
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(' ');
}

/**
 * Transform a status count mapping into an ordered array of breakdown items
 * sorted descending by count, with stable alphabetical tie-breaking on label.
 *
 * Percentages are calculated from the sum of this breakdown's own counts.
 * Returns 0% if the breakdown total is 0 (preventing NaN / Infinity).
 */
export function getStatusBreakdownItems(
  counts: Record<string, number> | null | undefined
): StatusBreakdownItem[] {
  if (!counts || typeof counts !== 'object') {
    return [];
  }

  const totalSum = sumStatusCounts(counts);

  const entries = Object.entries(counts).map(([rawStatus, rawCount]) => {
    const validCount =
      typeof rawCount === 'number' && Number.isFinite(rawCount) && rawCount >= 0
        ? Math.floor(rawCount)
        : 0;

    const percentage = totalSum > 0 ? (validCount / totalSum) * 100 : 0;

    return {
      status: rawStatus,
      label: formatAdminStatusLabel(rawStatus),
      count: validCount,
      percentage: Number(percentage.toFixed(1)),
    };
  });

  // Sort descending by count, tie-break ascending by label
  return entries.sort((a, b) => {
    if (b.count !== a.count) {
      return b.count - a.count;
    }
    return a.label.localeCompare(b.label);
  });
}

/**
 * Compare the sum of applications_by_status against the reported total_applications.
 * Never silently modifies or overwrites API values.
 */
export function getApplicationCountConsistency(
  metrics: AdminMetrics | null | undefined
): ApplicationConsistencyResult {
  const groupedTotal = sumStatusCounts(metrics?.applications_by_status);
  const reportedTotal =
    typeof metrics?.total_applications === 'number' &&
    Number.isFinite(metrics.total_applications) &&
    metrics.total_applications >= 0
      ? Math.floor(metrics.total_applications)
      : 0;

  const isConsistent = groupedTotal === reportedTotal;
  const difference = groupedTotal - reportedTotal;

  return {
    isConsistent,
    groupedTotal,
    reportedTotal,
    difference,
  };
}

/**
 * Calculate the total number of webhook events represented in the processing-status breakdown.
 * Accurately labeled as events represented in the breakdown, not platform-wide totals.
 */
export function getEventCountSummary(metrics: AdminMetrics | null | undefined): number {
  return sumStatusCounts(metrics?.lender_events_by_processing_status);
}
