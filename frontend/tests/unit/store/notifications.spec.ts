import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

const api = vi.hoisted(() => ({
  listNotifications: vi.fn(),
  getUnreadCount: vi.fn(),
  markRead: vi.fn(),
  markAllRead: vi.fn(),
  getPreference: vi.fn(),
  putPreference: vi.fn(),
}))
vi.mock('@/api/notifications', () => api)

import { useNotificationStore } from '@/store/notifications'

function notif(over = {}) {
  return {
    id: 'n1', type: 'WO_ASSIGNED', entity_type: 'work_order', entity_id: 'wo1',
    params: {}, actor_user_id: null, is_read: false, read_at: null,
    created_at: '2026-06-05T00:00:00', ...over,
  }
}

describe('useNotificationStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    api.getUnreadCount.mockReset().mockResolvedValue({ count: 3 })
    api.listNotifications.mockReset().mockResolvedValue({ items: [notif()], total: 1, page: 1, page_size: 10, total_pages: 1 })
    api.markRead.mockReset().mockResolvedValue(notif({ is_read: true }))
    api.markAllRead.mockReset().mockResolvedValue({ updated: 3 })
    api.getPreference.mockReset().mockResolvedValue({ email_enabled: true, disabled_types: [] })
    api.putPreference.mockReset().mockImplementation(async (p) => p)
  })
  afterEach(() => vi.useRealTimers())

  it('fetchUnread 写 unreadCount', async () => {
    const s = useNotificationStore()
    await s.fetchUnread()
    expect(s.unreadCount).toBe(3)
  })

  it('fetchRecent 写 recent', async () => {
    const s = useNotificationStore()
    await s.fetchRecent()
    expect(s.recent).toHaveLength(1)
  })

  it('markRead 乐观：本地置已读 + unreadCount 递减', async () => {
    const s = useNotificationStore()
    await s.fetchUnread()
    await s.fetchRecent()
    await s.markRead('n1')
    expect(s.recent[0].is_read).toBe(true)
    expect(s.unreadCount).toBe(2)
    expect(api.markRead).toHaveBeenCalledWith('n1')
  })

  it('markRead 失败回滚（重新拉未读数）', async () => {
    const s = useNotificationStore()
    await s.fetchUnread()
    api.markRead.mockRejectedValueOnce(new Error('x'))
    api.getUnreadCount.mockResolvedValueOnce({ count: 9 })
    await s.markRead('n1')
    expect(s.unreadCount).toBe(9)
  })

  it('markAllRead 清零', async () => {
    const s = useNotificationStore()
    await s.fetchUnread()
    await s.fetchRecent()
    await s.markAllRead()
    expect(s.unreadCount).toBe(0)
    expect(s.recent.every((n) => n.is_read)).toBe(true)
  })

  it('startPolling 立即拉一次并定时；stopPolling 清', async () => {
    vi.useFakeTimers()
    const s = useNotificationStore()
    s.startPolling()
    await vi.advanceTimersByTimeAsync(0)
    expect(api.getUnreadCount).toHaveBeenCalledTimes(1)
    await vi.advanceTimersByTimeAsync(60000)
    expect(api.getUnreadCount).toHaveBeenCalledTimes(2)
    s.stopPolling()
    await vi.advanceTimersByTimeAsync(120000)
    expect(api.getUnreadCount).toHaveBeenCalledTimes(2)
  })

  it('startPolling 幂等（重复 start 不叠定时器）', async () => {
    vi.useFakeTimers()
    const s = useNotificationStore()
    s.startPolling(); s.startPolling()
    await vi.advanceTimersByTimeAsync(60000)
    s.stopPolling()
    expect(api.getUnreadCount.mock.calls.length).toBeLessThanOrEqual(3)
  })

  it('loadPrefs / savePrefs', async () => {
    const s = useNotificationStore()
    await s.loadPrefs()
    expect(s.prefs).toEqual({ email_enabled: true, disabled_types: [] })
    await s.savePrefs({ email_enabled: false, disabled_types: ['WO_ASSIGNED'] })
    expect(api.putPreference).toHaveBeenCalledWith({ email_enabled: false, disabled_types: ['WO_ASSIGNED'] })
    expect(s.prefs?.email_enabled).toBe(false)
  })
})
