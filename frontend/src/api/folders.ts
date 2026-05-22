import { http } from './http'
import type { BatchDeleteResult, PageResult } from '@/types/common'
import type {
  CheckResult,
  Folder,
  FolderCreate,
  FolderOption,
  FolderTreeNode,
  FolderUpdate,
} from '@/types/folder'

export const fetchFolderList = async (params?: {
  page?: number
  page_size?: number
  sort?: string
  search?: string
}): Promise<PageResult<Folder>> => (await http.get<PageResult<Folder>>('/folders', { params })).data

export const fetchFolderTree = async (): Promise<FolderTreeNode[]> =>
  (await http.get<FolderTreeNode[]>('/folders/tree')).data

export const fetchFolderOptions = async (): Promise<FolderOption[]> =>
  (await http.get<FolderOption[]>('/folders/options')).data

export const fetchFolder = async (id: string): Promise<Folder> =>
  (await http.get<Folder>(`/folders/${id}`)).data

export const createFolder = async (payload: FolderCreate): Promise<Folder> =>
  (await http.post<Folder>('/folders', payload)).data

export const updateFolder = async (id: string, payload: FolderUpdate): Promise<Folder> =>
  (await http.put<Folder>(`/folders/${id}`, payload)).data

export const deleteFolder = async (id: string): Promise<void> => {
  await http.delete(`/folders/${id}`)
}

export const batchDeleteFolders = async (ids: string[]): Promise<BatchDeleteResult> =>
  (await http.post<BatchDeleteResult>('/folders/batch-delete', { ids })).data

export const checkFolderName = async (
  name: string,
  parentId?: string | null,
  excludeId?: string,
): Promise<CheckResult> =>
  (
    await http.get<CheckResult>('/folders/check-name', {
      params: { name, parent_id: parentId ?? undefined, exclude_id: excludeId },
    })
  ).data

export const checkFolderPrefix = async (prefix: string, excludeId?: string): Promise<CheckResult> =>
  (
    await http.get<CheckResult>('/folders/check-prefix', {
      params: { prefix, exclude_id: excludeId },
    })
  ).data
