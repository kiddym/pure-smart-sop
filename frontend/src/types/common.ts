// 通用类型（与后端 app/schemas/common.py 对齐）

export interface PageResult<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface BatchFailure {
  id: string
  code: string
  message: string
}

export interface BatchDeleteResult {
  deleted_ids: string[]
  failed: BatchFailure[]
}

export interface ListQuery {
  page?: number
  page_size?: number
  sort?: string
  search?: string
}
