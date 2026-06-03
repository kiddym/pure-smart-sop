import type { WorkOrderStatus } from '@/types/workOrder'

export const WO_STATUS_LABELS: Record<WorkOrderStatus, string> = {
  OPEN: '待处理',
  IN_PROGRESS: '进行中',
  ON_HOLD: '挂起',
  COMPLETE: '已完成',
  CANCELED: '已取消',
}

export const WO_STATUS_TAG: Record<WorkOrderStatus, string> = {
  OPEN: 'info',
  IN_PROGRESS: 'primary',
  ON_HOLD: 'warning',
  COMPLETE: 'success',
  CANCELED: 'danger',
}
