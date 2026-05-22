import { describe, expect, it } from 'vitest'
import { MAX_UPLOAD_MB, formatBytes, uploadSizeTier } from '@/utils/upload'

const MB = 1024 * 1024

describe('uploadSizeTier 三档预警', () => {
  it('<20MB 正常', () => {
    expect(uploadSizeTier(5 * MB).tier).toBe('ok')
  })
  it('20–40MB info', () => {
    expect(uploadSizeTier(25 * MB).tier).toBe('info')
  })
  it('40–50MB warning', () => {
    expect(uploadSizeTier(45 * MB).tier).toBe('warning')
  })
  it('>50MB 阻断 error', () => {
    expect(uploadSizeTier((MAX_UPLOAD_MB + 1) * MB).tier).toBe('error')
  })
  it('边界 20MB 计入 info，40MB 计入 warning，50MB 仍允许', () => {
    expect(uploadSizeTier(20 * MB).tier).toBe('info')
    expect(uploadSizeTier(40 * MB).tier).toBe('warning')
    expect(uploadSizeTier(50 * MB).tier).toBe('warning')
  })
  it('每档都带可读文案', () => {
    expect(uploadSizeTier(60 * MB).message).toContain('50')
  })
})

describe('formatBytes', () => {
  it('格式化为可读单位', () => {
    expect(formatBytes(0)).toBe('0 B')
    expect(formatBytes(1536)).toBe('1.5 KB')
    expect(formatBytes(5 * MB)).toBe('5.0 MB')
  })
})
