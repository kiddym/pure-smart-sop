import dayjs from 'dayjs'

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return '-'
  return dayjs(value).format('YYYY-MM-DD HH:mm')
}

export const LEVEL_OF_USE_LABELS: Record<string, string> = {
  reference: '参考',
  continuous: '连续使用',
  information: '信息',
}
