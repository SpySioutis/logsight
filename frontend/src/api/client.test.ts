import { describe, expect, it } from 'vitest'
import { toParams } from './client'

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
