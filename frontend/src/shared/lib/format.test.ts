import { describe, expect, it } from 'vitest'

import {
  formatConfidence,
  formatFileSize,
  formatJson,
  formatNullable,
  getConfidenceTone,
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
})
