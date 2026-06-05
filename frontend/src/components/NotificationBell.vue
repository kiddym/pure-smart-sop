<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { Bell } from '@element-plus/icons-vue'
import { useNotificationStore } from '@/store/notifications'
import { formatNotification, entityRoute } from '@/utils/notificationText'
import { relativeTime } from '@/utils/format'
import type { Notification } from '@/types/notification'

const store = useNotificationStore()
const router = useRouter()
const badge = computed(() => (store.unreadCount > 99 ? '99+' : store.unreadCount))

function onOpen(visible: boolean): void {
  if (visible) void store.fetchRecent()
}
async function onItem(n: Notification): Promise<void> {
  await store.markRead(n.id)
  const to = entityRoute(n)
  if (to) router.push(to)
}
function text(n: Notification): string {
  return formatNotification(n)
}
</script>

<template>
  <el-dropdown trigger="click" popper-class="notif-bell-popper" @visible-change="onOpen">
    <el-badge :value="badge" :hidden="store.unreadCount === 0" :max="9999">
      <button class="notif-bell-btn" aria-label="通知">
        <el-icon><Bell /></el-icon>
      </button>
    </el-badge>
    <template #dropdown>
      <div class="notif-dropdown">
        <div class="notif-head">
          <span>通知</span>
          <el-button text size="small" :disabled="store.unreadCount === 0" @click="store.markAllRead()">
            全部已读
          </el-button>
        </div>
        <div v-if="store.recent.length === 0" class="notif-empty">暂无通知</div>
        <ul v-else class="notif-list">
          <li
            v-for="n in store.recent"
            :key="n.id"
            data-test="notif-item"
            class="notif-item"
            :class="{ unread: !n.is_read }"
            @click="onItem(n)"
          >
            <span v-if="!n.is_read" class="dot" />
            <span class="msg">{{ text(n) }}</span>
            <span class="time">{{ relativeTime(n.created_at) }}</span>
          </li>
        </ul>
        <div class="notif-foot">
          <router-link to="/notifications">查看全部 →</router-link>
        </div>
      </div>
    </template>
  </el-dropdown>
</template>

<style scoped>
.notif-bell-btn {
  width: 28px;
  height: 28px;
  border: none;
  background: transparent;
  border-radius: 4px;
  cursor: pointer;
  color: var(--text-regular);
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.notif-bell-btn:hover {
  background: var(--bg-hover);
}
.notif-dropdown {
  width: 320px;
}
.notif-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  border-bottom: 1px solid var(--border-subtle);
}
.notif-empty {
  padding: 24px;
  text-align: center;
  color: var(--text-tertiary);
  font-size: 13px;
}
.notif-list {
  list-style: none;
  margin: 0;
  padding: 0;
  max-height: 360px;
  overflow-y: auto;
}
.notif-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  cursor: pointer;
  font-size: 13px;
}
.notif-item:hover {
  background: var(--bg-hover);
}
.notif-item.unread .msg {
  color: var(--text-primary);
  font-weight: 500;
}
.notif-item .dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--accent);
  flex-shrink: 0;
}
.notif-item .msg {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.notif-item .time {
  color: var(--text-tertiary);
  font-size: 11px;
  flex-shrink: 0;
}
.notif-foot {
  padding: 8px 12px;
  text-align: center;
  border-top: 1px solid var(--border-subtle);
}
.notif-foot a {
  color: var(--el-color-primary);
  font-size: 12px;
  text-decoration: none;
}
</style>
