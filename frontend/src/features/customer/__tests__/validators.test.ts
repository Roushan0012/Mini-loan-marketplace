import { describe, it, expect } from 'vitest';
import { isPositiveDecimal, isNonNegativeDecimal } from '../utils/validators';

describe('isPositiveDecimal helper', () => {
  it('rejects "0"', () => {
    expect(isPositiveDecimal('0')).toBe(false);
  });

  it('rejects "0.00"', () => {
    expect(isPositiveDecimal('0.00')).toBe(false);
  });

  it('accepts "0.01"', () => {
    expect(isPositiveDecimal('0.01')).toBe(true);
  });

  it('accepts "200000.00"', () => {
    expect(isPositiveDecimal('200000.00')).toBe(true);
  });

  it('rejects "-1"', () => {
    expect(isPositiveDecimal('-1')).toBe(false);
  });

  it('rejects "100.123"', () => {
    expect(isPositiveDecimal('100.123')).toBe(false);
  });

  it('rejects empty strings and non-numeric inputs', () => {
    expect(isPositiveDecimal('')).toBe(false);
    expect(isPositiveDecimal('   ')).toBe(false);
    expect(isPositiveDecimal('abc')).toBe(false);
    expect(isPositiveDecimal('12.3.4')).toBe(false);
    expect(isPositiveDecimal('00.00')).toBe(false);
  });

  it('accepts integer and decimal positive amounts', () => {
    expect(isPositiveDecimal('5000')).toBe(true);
    expect(isPositiveDecimal('5000.5')).toBe(true);
    expect(isPositiveDecimal('5000.50')).toBe(true);
  });
});

describe('isNonNegativeDecimal helper', () => {
  it('accepts zero values', () => {
    expect(isNonNegativeDecimal('0')).toBe(true);
    expect(isNonNegativeDecimal('0.00')).toBe(true);
  });

  it('rejects negative values and excessive decimals', () => {
    expect(isNonNegativeDecimal('-0.01')).toBe(false);
    expect(isNonNegativeDecimal('10.999')).toBe(false);
  });
});
