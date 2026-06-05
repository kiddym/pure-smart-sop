import { defineStore } from 'pinia'

import * as notifApi from '@/api/notifications'
import type { Notification, NotificationPreference } from '@/types/notification'

const POLL_MS = 60000

interface State {
  unreadCount: number
  recent: Notification[]
  prefs: NotificationPreference | null
  pollTimer: ReturnType<typeof setInterval> | null
}

export const useNotificationStore = defineStore('notifications', {
  state: (): State => ({ unreadCount: 0, recent: [], prefs: null, pollTimer: null }),
  actions: {
    async fetchUnread(): Promise<void> {
      this.unreadCount = (await notifApi.getUnreadCount()).count
    },
    async fetchRecent(): Promise<void> {
      this.recent = (await notifApi.listNotifications({ page: 1, page_size: 10 })).items
    },
    async markRead(id: string): Promise<void> {
      const item = this.recent.find((n) => n.id === id)
      const wasUnread = item ? !item.is_read : false
      if (item) item.is_read = true
      if (wasUnread) this.unreadCount = Math.max(0, this.unreadCount - 1)
      try {
        await notifApi.markRead(id)
      } catch {
        if (item) item.is_read = false
        await this.fetchUnread()
      }
    },
    async markAllRead(): Promise<void> {
      await notifApi.markAllRead()
      this.unreadCount = 0
      this.recent = this.recent.map((n) => ({ ...n, is_read: true }))
    },
    async loadPrefs(): Promise<void> {
      this.prefs = await notifApi.getPreference()
    },
    async savePrefs(p: NotificationPreference): Promise<void> {
      this.prefs = await notifApi.putPreference(p)
    },
    startPolling(): void {
      this.stopPolling()
      void this.fetchUnread()
      this.pollTimer = setInterval(() => void this.fetchUnread(), POLL_MS)
    },
    stopPolling(): void {
      if (this.pollTimer) {
        clearInterval(this.pollTimer)
        this.pollTimer = null
      }
    },
  },
})
