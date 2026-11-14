import { describe, expect, it } from 'vitest'
import { formatBytes, formatDateTime, formatNumber, truncate } from './format'

describe('format utils', () => {
  it('formats numbers with thousands separators', () => {
    expect(formatNumber(1234567)).toBe('1,234,567')
  })

  it('formats byte sizes', () => {
    expect(formatBytes(0)).toBe('0 B')
    expect(formatBytes(512)).toBe('512 B')
    expect(formatBytes(2048)).toBe('2.0 KB')
  })

  it('handles null and invalid dates', () => {
    expect(formatDateTime(null)).toBe('—')
    expect(formatDateTime('not-a-date')).toBe('not-a-date')
    expect(formatDateTime('2024-05-01T10:00:00Z')).toContain('2024')
  })

  it('truncates long strings', () => {
    expect(truncate('short', 10)).toBe('short')
    expect(truncate('abcdefghij', 5)).toBe('abcd…')
  })
})
