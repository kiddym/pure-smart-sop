import { http } from './http'
import type { UserRead, SelfProfileUpdate } from '@/types/platform'

// 当前登录用户的自助资料（任意认证用户可读/改自己）。
export const getMyProfile = () => http.get<UserRead>('/users/me').then((r) => r.data)

export const updateMyProfile = (payload: SelfProfileUpdate) =>
  http.patch<UserRead>('/users/me', payload).then((r) => r.data)
