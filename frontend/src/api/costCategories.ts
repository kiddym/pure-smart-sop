import { http } from './http'
import type { CostCategoryRead } from '@/types/workOrder'

export const listCostCategories = () =>
  http.get<CostCategoryRead[]>('/cost-categories').then((r) => r.data)
