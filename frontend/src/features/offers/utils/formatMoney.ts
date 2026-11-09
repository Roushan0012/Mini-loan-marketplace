/**
 * Decimal-safe monetary and rate formatting utilities.
 * Uses strict string manipulation without JavaScript floating-point conversions.
 */

/**
 * Formats a decimal numeric string as Indian Rupees (₹) with proper Indian digit grouping
 * (e.g. ₹2,00,000.00) while strictly preserving exact cents without using parseFloat/Number.
 *
 * Examples:
 *   "200000.00" -> "₹2,00,000.00"
 *   "150000.50" -> "₹1,50,000.50"
 *   "0.00"      -> "₹0.00"
 */
export function formatRupees(amount: string): string {
  const trimmed = (amount || '').trim();

  // Validate format: optional leading minus, digits, optional decimal dot with digits
  if (!trimmed || !/^-?\d+(\.\d+)?$/.test(trimmed)) {
    return '₹0.00';
  }

  const isNegative = trimmed.startsWith('-');
  const cleanAmount = isNegative ? trimmed.slice(1) : trimmed;

  const parts = cleanAmount.split('.');
  let intPart = parts[0] || '0';
  // Strip leading redundant zeros from intPart unless it is single zero
  intPart = intPart.replace(/^0+(?=\d)/, '');

  let decPart = parts[1] || '00';
  // Normalize decimal places to at least 2 digits (e.g. .5 -> .50)
  if (decPart.length === 1) {
    decPart = `${decPart}0`;
  } else if (decPart.length > 2) {
    // Preserve first 2 decimal digits for rupee display
    decPart = decPart.slice(0, 2);
  }

  // Format integer part with Indian digit grouping:
  // Rightmost 3 digits, then groups of 2 digits
  let formattedInt = intPart;
  if (intPart.length > 3) {
    const lastThree = intPart.slice(-3);
    const leading = intPart.slice(0, -3);
    const groupedLeading = leading.replace(/\B(?=(\d{2})+(?!\d))/g, ',');
    formattedInt = `${groupedLeading},${lastThree}`;
  }

  const sign = isNegative ? '-' : '';
  return `${sign}₹${formattedInt}.${decPart}`;
}

/**
 * Formats an annual percentage rate (APR) decimal string safely without floating-point arithmetic.
 *
 * Examples:
 *   "12.5000" -> "12.5%"
 *   "20.0000" -> "20%"
 *   "14.75"   -> "14.75%"
 */
export function formatApr(apr: string): string {
  const trimmed = (apr || '').trim();
  if (!trimmed || !/^\d+(\.\d+)?$/.test(trimmed)) {
    return '0%';
  }

  const parts = trimmed.split('.');
  const intPart = parts[0] || '0';
  const decPart = parts[1] || '';

  if (!decPart) {
    return `${intPart}%`;
  }

  const cleanDec = decPart.replace(/0+$/, '');
  return cleanDec.length > 0 ? `${intPart}.${cleanDec}%` : `${intPart}%`;
}
