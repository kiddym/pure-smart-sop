import { describe, expect, it } from 'vitest'
import { LEVEL_OF_USE_LABELS, formatDateTime } from '@/utils/format'

describe('formatDateTime', () => {
  it('formats an ISO string to YYYY-MM-DD HH:mm', () => {
    expect(formatDateTime('2026-05-21T10:23:45Z')).toMatch(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/)
  })

  it('returns dash for empty input', () => {
    expect(formatDateTime(null)).toBe('-')
    expect(formatDateTime(undefined)).toBe('-')
  })
})

describe('LEVEL_OF_USE_LABELS', () => {
  it('maps enum to Chinese labels', () => {
    expect(LEVEL_OF_USE_LABELS.reference).toBe('参考')
    expect(LEVEL_OF_USE_LABELS.continuous).toBe('连续使用')
    expect(LEVEL_OF_USE_LABELS.information).toBe('信息')
  })
})
