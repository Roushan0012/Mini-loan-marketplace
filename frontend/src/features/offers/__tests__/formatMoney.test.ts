import { describe, it, expect } from 'vitest';
import { formatRupees, formatApr } from '../utils/formatMoney';

describe('formatRupees utility', () => {
  it('17. Formats Indian numbering system grouping correctly', () => {
    expect(formatRupees('200000.00')).toBe('₹2,00,000.00');
    expect(formatRupees('150000.50')).toBe('₹1,50,000.50');
    expect(formatRupees('1000.00')).toBe('₹1,000.00');
    expect(formatRupees('10000.00')).toBe('₹10,000.00');
    expect(formatRupees('10000000.00')).toBe('₹1,00,00,000.00');
  });

  it('18. Preserves exact cents without floating-point distortion', () => {
    expect(formatRupees('0.00')).toBe('₹0.00');
    expect(formatRupees('0.01')).toBe('₹0.01');
    expect(formatRupees('1234.5')).toBe('₹1,234.50');
    expect(formatRupees('9999999999.99')).toBe('₹9,99,99,99,999.99');
  });

  it('19. Handles invalid, empty, or negative values safely', () => {
    expect(formatRupees('')).toBe('₹0.00');
    expect(formatRupees('   ')).toBe('₹0.00');
    expect(formatRupees('invalid')).toBe('₹0.00');
    expect(formatRupees('-5000.00')).toBe('-₹5,000.00');
  });
});

describe('formatApr utility', () => {
  it('formats APR percentage strings cleanly without float arithmetic', () => {
    expect(formatApr('12.5000')).toBe('12.5%');
    expect(formatApr('20.0000')).toBe('20%');
    expect(formatApr('14.75')).toBe('14.75%');
    expect(formatApr('0.0000')).toBe('0%');
    expect(formatApr('0')).toBe('0%');
    expect(formatApr('')).toBe('0%');
  });
});
