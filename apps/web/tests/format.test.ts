import { describe, expect, it } from 'vitest'
import { compactCurrency, dueLabel, initials, relativeTime, signedDelta } from '@/lib/format'

const now = new Date('2026-09-28T12:00:00Z')

describe('relativeTime', () => {
  it('formats hours, days, weeks', () => {
    expect(relativeTime('2026-09-28T09:00:00Z', now)).toBe('3h ago')
    expect(relativeTime('2026-09-26T12:00:00Z', now)).toBe('2d ago')
    expect(relativeTime('2026-09-07T12:00:00Z', now)).toBe('3 weeks ago')
    expect(relativeTime('2026-09-30T12:00:00Z', now)).toBe('in 2d')
    expect(relativeTime(null, now)).toBe('never')
  })
})

describe('dueLabel', () => {
  it('says overdue with a day count', () => {
    expect(dueLabel('2026-09-19T12:00:00Z', now)).toBe('overdue 9 days')
    expect(dueLabel('2026-09-30T12:00:00Z', now)).toBe('due in 2 days')
    expect(dueLabel('2026-09-28T18:00:00Z', now)).toBe('due today')
  })
})

describe('compactCurrency', () => {
  it('formats cents compactly', () => {
    expect(compactCurrency(250_000_000)).toBe('$2.5M')
    expect(compactCurrency(820_000_00)).toBe('$820K')
    expect(compactCurrency(0)).toBe('$0')
  })
})

describe('initials', () => {
  it('drops honorifics', () => {
    expect(initials('Col. Michael Johnson')).toBe('MJ')
    expect(initials('Emily Rodriguez')).toBe('ER')
    expect(initials('Madonna')).toBe('M')
  })
})

describe('signedDelta', () => {
  it('adds a plus sign for positive numbers', () => {
    expect(signedDelta(12)).toBe('+12')
    expect(signedDelta(-3, '%')).toBe('-3%')
  })
})
