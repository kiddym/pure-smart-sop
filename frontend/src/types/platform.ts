// 平台管理类型（与后端 app/schemas 平台相关 schema 对齐）。

export type UserStatus = 'active' | 'disabled'

export interface UserRead {
  id: string
  email: string
  name: string
  status: UserStatus
  role_id: string | null
  locale: string
  phone: string | null
  job_title: string | null
  rate: string | null
  avatar_url: string | null
  email_verified?: boolean
  last_login_at: string | null
  created_at: string
}

// 自助资料编辑（仅白名单字段，对齐后端 SelfProfileUpdate）。
export interface SelfProfileUpdate {
  name?: string
  phone?: string | null
  job_title?: string | null
  avatar_url?: string | null
  locale?: string
}
