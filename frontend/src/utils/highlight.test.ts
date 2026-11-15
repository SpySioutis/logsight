import { describe, expect, it } from 'vitest'
import { sanitizeSnippet } from './highlight'

describe('sanitizeSnippet', () => {
  it('keeps mark tags', () => {
    expect(sanitizeSnippet('a <mark>slow</mark> query')).toBe('a <mark>slow</mark> query')
  })

  it('strips other tags but keeps their text', () => {
    expect(sanitizeSnippet('<b>boom</b> <script>alert(1)</script>')).toBe('boom alert(1)')
  })

  it('strips attributes from mark tags', () => {
    expect(sanitizeSnippet('<mark class="x">hit</mark>')).toBe('<mark>hit</mark>')
  })
})
