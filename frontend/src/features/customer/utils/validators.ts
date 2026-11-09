/**
 * String-based decimal validation utilities.
 * Validates monetary and decimal inputs without JavaScript floating-point conversions.
 */

const DECIMAL_FORMAT_REGEX = /^\d+(\.\d{1,2})?$/;

/**
 * Checks whether a given string is a strictly positive decimal (> 0) with at most 2 decimal places.
 * Does not use parseFloat or Number to prevent floating-point precision issues.
 */
export function isPositiveDecimal(value: string): boolean {
  const trimmed = value.trim();
  if (!trimmed) {
    return false;
  }

  // Must match numeric format with up to 2 decimal places (strictly non-negative characters)
  if (!DECIMAL_FORMAT_REGEX.test(trimmed)) {
    return false;
  }

  // Must contain at least one non-zero digit (1-9) to be strictly positive
  return /[1-9]/.test(trimmed);
}

/**
 * Checks whether a given string is a valid non-negative decimal (>= 0) with at most 2 decimal places.
 */
export function isNonNegativeDecimal(value: string): boolean {
  const trimmed = value.trim();
  if (!trimmed) {
    return false;
  }
  return DECIMAL_FORMAT_REGEX.test(trimmed);
}
