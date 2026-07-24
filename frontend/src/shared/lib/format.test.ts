import { describe, expect, it } from 'vitest'

import {
  dateInputToIsoNextDay,
  dateInputToIsoStart,
  formatConfidence,
  formatFileSize,
  formatJson,
  formatNullable,
  getConfidenceTone,
  isDateInputRangeValid,
} from './format'

describe('format helpers', () => {
  it('formats nullable strings', () => {
    expect(formatNullable('value')).toBe('value')
    expect(formatNullable('')).toBe('—')
    expect(formatNullable(null)).toBe('—')
  })

  it('formats confidence and tones', () => {
    expect(formatConfidence(0.91)).toBe('91%')
    expect(formatConfidence(null)).toBe('нет оценки')
    expect(getConfidenceTone(0.91)).toBe('success')
    expect(getConfidenceTone(0.6)).toBe('warning')
    expect(getConfidenceTone(0.4)).toBe('danger')
    expect(getConfidenceTone(null)).toBe('neutral')
  })

  it('formats file sizes', () => {
    expect(formatFileSize(512)).toBe('512 Б')
    expect(formatFileSize(2048)).toBe('2 КБ')
  })

  it('formats JSON with indentation', () => {
    expect(formatJson({ value: 1 })).toBe('{\n  "value": 1\n}')
  })

  it('converts only valid date inputs to API boundaries', () => {
    expect(dateInputToIsoStart('2026-07-17')).toBe('2026-07-17T00:00:00.000Z')
    expect(dateInputToIsoNextDay('2026-07-17')).toBe('2026-07-18T00:00:00.000Z')
    expect(dateInputToIsoStart('2026-02-30')).toBeNull()
  })

  it('validates raw date input order', () => {
    expect(isDateInputRangeValid('2026-07-01', '2026-07-31')).toBe(true)
    expect(isDateInputRangeValid('2026-07-31', '2026-07-01')).toBe(false)
    expect(isDateInputRangeValid('2026-02-30', '2026-07-01')).toBe(false)
  })
})
