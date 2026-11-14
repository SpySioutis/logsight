import { describe, expect, it } from 'vitest'
import { isErrorLike, SEVERITIES, severityRank } from './severity'

describe('severity utils', () => {
  it('lists all nine canonical severities', () => {
    expect([...SEVERITIES]).toEqual([
      'TRACE',
      'DEBUG',
      'INFO',
      'WARN',
      'WARNING',
      'ERROR',
      'FATAL',
      'CRITICAL',
      'UNKNOWN',
    ])
  })

  it('ranks severities in ascending order', () => {
    const order = ['TRACE', 'DEBUG', 'INFO', 'WARN', 'ERROR', 'FATAL', 'CRITICAL']
    const ranks = order.map(severityRank)
    expect([...ranks].sort((a, b) => a - b)).toEqual(ranks)
  })

  it('flags error-like severities', () => {
    expect(isErrorLike('ERROR')).toBe(true)
    expect(isErrorLike('FATAL')).toBe(true)
    expect(isErrorLike('CRITICAL')).toBe(true)
    expect(isErrorLike('WARN')).toBe(false)
    expect(isErrorLike('INFO')).toBe(false)
    expect(isErrorLike('UNKNOWN')).toBe(false)
  })
})
