import { http } from './http'
import type { CurrentUser, LoginPayload, RegisterPayload, TokenPair } from '@/types/auth'

export const login = async (payload: LoginPayload): Promise<TokenPair> =>
  (await http.post<TokenPair>('/auth/login', payload)).data

export const register = async (payload: RegisterPayload): Promise<TokenPair> =>
  (await http.post<TokenPair>('/auth/register', payload)).data

export const refresh = async (refreshToken: string): Promise<TokenPair> =>
  (await http.post<TokenPair>('/auth/refresh', { refresh_token: refreshToken })).data

export const fetchMe = async (): Promise<CurrentUser> =>
  (await http.get<CurrentUser>('/auth/me')).data
