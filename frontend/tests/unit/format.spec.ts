import { describe, expect, it } from 'vitest'
import {
  LEVEL_OF_USE_LABELS,
  formatDate,
  formatDateTime,
  formatDateTimeSeconds,
} from '@/utils/format'

describe('formatDateTime', () => {
  it('formats an ISO string to YYYY-MM-DD HH:mm', () => {
    expect(formatDateTime('2026-05-21T10:23:45Z')).toMatch(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/)
  })

  it('treats a tz-less (naive UTC) string the same as one with Z', () => {
    // 核心修复：后端裸 UTC（无 Z）不能被当作本地时间，否则整体偏时区。
    expect(formatDateTime('2026-05-21T10:23:45')).toBe(formatDateTime('2026-05-21T10:23:45Z'))
  })

  it('returns dash for empty input', () => {
    expect(formatDateTime(null)).toBe('-')
    expect(formatDateTime(undefined)).toBe('-')
  })
})

describe('formatDateTimeSeconds', () => {
  it('formats to YYYY-MM-DD HH:mm:ss', () => {
    expect(formatDateTimeSeconds('2026-05-21T10:23:45Z')).toMatch(
      /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/,
    )
  })
  it('naive == with-Z', () => {
    expect(formatDateTimeSeconds('2026-05-21T10:23:45')).toBe(
      formatDateTimeSeconds('2026-05-21T10:23:45Z'),
    )
  })
  it('dash for empty', () => expect(formatDateTimeSeconds('')).toBe('-'))
})

describe('formatDate', () => {
  it('formats to YYYY-MM-DD', () => {
    expect(formatDate('2026-05-21T10:23:45Z')).toMatch(/^\d{4}-\d{2}-\d{2}$/)
  })
  it('naive == with-Z', () => {
    expect(formatDate('2026-05-21T10:23:45')).toBe(formatDate('2026-05-21T10:23:45Z'))
  })
  it('dash for empty', () => expect(formatDate(null)).toBe('-'))
})

describe('LEVEL_OF_USE_LABELS', () => {
  it('maps enum to Chinese labels', () => {
    expect(LEVEL_OF_USE_LABELS.reference).toBe('参考')
    expect(LEVEL_OF_USE_LABELS.continuous).toBe('连续使用')
    expect(LEVEL_OF_USE_LABELS.information).toBe('信息')
  })
})
