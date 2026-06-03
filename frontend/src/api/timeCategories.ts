import { http } from './http'
import type { TimeCategoryRead } from '@/types/workOrder'

export const listTimeCategories = () =>
  http.get<TimeCategoryRead[]>('/time-categories').then((r) => r.data)
