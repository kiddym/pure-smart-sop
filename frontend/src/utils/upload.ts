// 上传体积分档 + 字节格式化（Q352）。MAX 对齐后端 settings.upload_max_size_mb。

export const MAX_UPLOAD_MB = 50
const MB = 1024 * 1024

export type SizeTier = 'ok' | 'info' | 'warning' | 'error'

export interface SizeTierResult {
  tier: SizeTier
  message: string
}

// <20MB 正常；20–40MB 提示；40–50MB 警告；>50MB 阻断（前端不发请求，对齐 PARSE_FILE_TOO_LARGE）。
export function uploadSizeTier(bytes: number): SizeTierResult {
  if (bytes > MAX_UPLOAD_MB * MB) {
    return { tier: 'error', message: `文件超过 ${MAX_UPLOAD_MB}MB 上限，无法上传，请拆分后重试` }
  }
  if (bytes >= 40 * MB) {
    return { tier: 'warning', message: '文件很大，解析可能较慢（可能触发 30 秒超时）' }
  }
  if (bytes >= 20 * MB) {
    return { tier: 'info', message: '文件较大，上传与解析可能需要一些时间' }
  }
  return { tier: 'ok', message: '' }
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < MB) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / MB).toFixed(1)} MB`
}
