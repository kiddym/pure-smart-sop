import { http } from './http'
import type {
  WorkOrderCategoryRead,
  WorkOrderCategoryCreate,
  WorkOrderCategoryUpdate,
} from '@/types/workOrder'

export const listWorkOrderCategories = () =>
  http.get<WorkOrderCategoryRead[]>('/work-order-categories').then((r) => r.data)
export const createWorkOrderCategory = (p: WorkOrderCategoryCreate) =>
  http.post<WorkOrderCategoryRead>('/work-order-categories', p).then((r) => r.data)
export const updateWorkOrderCategory = (id: string, p: WorkOrderCategoryUpdate) =>
  http.patch<WorkOrderCategoryRead>(`/work-order-categories/${id}`, p).then((r) => r.data)
export const deleteWorkOrderCategory = (id: string) =>
  http.delete(`/work-order-categories/${id}`).then(() => undefined)
