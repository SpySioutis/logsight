import { describe, expect, it } from 'vitest'
import { apiParams, exportUrl, isoToLocalInput, localInputToIso, toParams } from './client'

describe('toParams', () => {
  it('omits empty values but keeps severity arrays', () => {
    expect(
      toParams({ q: 'boom', severity: ['ERROR', 'WARN'], page: 2, page_size: 50 }),
    ).toEqual({ q: 'boom', severity: ['ERROR', 'WARN'], page: '2', page_size: '50' })
  })

  it('returns an empty object for an empty query', () => {
    expect(toParams({})).toEqual({})
  })
})

describe('date conversion', () => {
  it('converts datetime-local values to the UTC instant the user meant', () => {
    const local = '2024-05-01T10:30'
    expect(localInputToIso(local)).toBe(new Date(2024, 4, 1, 10, 30).toISOString())
  })

  it('passes values with an explicit offset through unchanged', () => {
    expect(localInputToIso('2024-05-01T10:30:00Z')).toBe('2024-05-01T10:30:00Z')
    expect(localInputToIso('not a date')).toBe('not a date')
  })

  it('round-trips through isoToLocalInput', () => {
    const local = '2024-12-31T23:59'
    expect(isoToLocalInput(localInputToIso(local))).toBe(local)
  })
})

describe('apiParams / exportUrl', () => {
  it('converts dates for the API but toParams keeps the local form', () => {
    const q = { date_from: '2024-05-01T10:30', q: 'x' }
    expect(toParams(q).date_from).toBe('2024-05-01T10:30')
    expect(apiParams(q).date_from).toBe(new Date(2024, 4, 1, 10, 30).toISOString())
  })

  it('builds an export URL without paging and with repeated severities', () => {
    const url = exportUrl({ severity: ['ERROR', 'WARN'], page: 3, page_size: 50, sort: 'timestamp' }, 'jsonl')
    expect(url.startsWith('/api/logs/export?')).toBe(true)
    const params = new URLSearchParams(url.split('?')[1])
    expect(params.getAll('severity')).toEqual(['ERROR', 'WARN'])
    expect(params.get('format')).toBe('jsonl')
    expect(params.has('page')).toBe(false)
    expect(params.has('page_size')).toBe(false)
  })
})
