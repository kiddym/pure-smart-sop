import { http } from './http'
import type { FieldDetailOut, FieldCreate, FieldUpdate } from '@/types/field'
import type { BatchDeleteResult } from '@/types/common'

// 后端路由前缀为 /procedure-fields（见 backend/app/routers/fields.py）；批量操作一律 POST 子路径。
export const listFields = (params?: { field_type?: string; status?: string }) =>
  http.get<FieldDetailOut[]>('/procedure-fields', { params }).then(r => r.data)

export const createField = (payload: FieldCreate) =>
  http.post<FieldDetailOut>('/procedure-fields', payload).then(r => r.data)

export const updateField = (id: string, payload: FieldUpdate) =>
  http.put<FieldDetailOut>(`/procedure-fields/${id}`, payload).then(r => r.data)

export const deleteField = (id: string) =>
  http.delete(`/procedure-fields/${id}`).then(() => undefined)

export const updateFieldsStatus = (ids: string[], status: 'active' | 'archived') =>
  http
    .post<{ updated_ids: string[] }>('/procedure-fields/update-status', { ids, status })
    .then(r => r.data)

export const batchDeleteFields = (ids: string[]) =>
  http.post<BatchDeleteResult>('/procedure-fields/batch-delete', { ids }).then(r => r.data)

export const reorderFields = (ordered_ids: string[]) =>
  http.post<FieldDetailOut[]>('/procedure-fields/reorder', { ordered_ids }).then(r => r.data)
