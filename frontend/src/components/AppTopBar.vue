<script setup lang="ts">
import { ElIcon } from 'element-plus'
import { Expand, Fold, Moon, Sunny } from '@element-plus/icons-vue'
import UserMenu from '@/components/UserMenu.vue'
import { useThemeStore } from '@/store/theme'

const theme = useThemeStore()

defineProps<{
  collapsed: boolean
}>()

defineEmits<{
  (e: 'toggle-sidebar'): void
}>()

// 注：顶栏不再保留 ⚙ 设置下拉与通知铃铛，配置入口统一在左侧栏「配置中心」。
</script>

<template>
  <header class="app-topbar">
    <button
      class="icon-btn topbar-toggle"
      :aria-label="collapsed ? '展开侧栏' : '折叠侧栏'"
      @click="$emit('toggle-sidebar')"
    >
      <el-icon><Expand v-if="collapsed" /><Fold v-else /></el-icon>
    </button>
    <span class="app-brand">{{ $t('app.name') }}</span>
    <!-- 全库搜索为路线图功能，未上线前不在顶栏占位（避免常驻的禁用控件传递半成品感）。
         上线时在此处恢复一个可用的搜索入口。 -->
    <span class="topbar-spacer" />
    <button
      class="icon-btn topbar-theme"
      :aria-label="theme.isDark ? '切换到浅色' : '切换到暗色'"
      :title="theme.isDark ? '切换到浅色' : '切换到暗色'"
      @click="theme.toggle()"
    >
      <el-icon><Sunny v-if="theme.isDark" /><Moon v-else /></el-icon>
    </button>
    <UserMenu />
  </header>
</template>

<style scoped>
.app-topbar {
  height: var(--topbar-height);
  display: flex;
  align-items: center;
  padding: 0 14px;
  gap: 14px;
  background: var(--bg-surface);
  border-bottom: 1px solid var(--border-subtle);
  flex-shrink: 0;
}
.app-brand {
  font-weight: 700;
  font-size: 14px;
  letter-spacing: 0.3px;
  color: var(--text-primary);
}
.topbar-spacer {
  flex: 1;
}
</style>
