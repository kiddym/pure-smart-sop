// 文件夹类型（与后端 app/schemas/folder.py 对齐）

export interface Folder {
  id: string
  name: string
  prefix: string
  parent_id: string | null
  system: boolean
  full_path: string
  created_at: string
  updated_at: string
}

export interface FolderTreeNode extends Folder {
  procedure_count: number
  children: FolderTreeNode[]
}

export interface FolderOption {
  id: string
  name: string
  full_path: string
}

export interface FolderCreate {
  name: string
  parent_id?: string | null
  prefix?: string
  sequence_digits?: number
}

export interface FolderUpdate {
  name: string
  parent_id?: string | null
  prefix?: string
  sequence_digits?: number | null
}

export interface CheckResult {
  available: boolean
  message: string | null
}
