<script setup lang="ts">
import { computed, type Component } from 'vue'
import { useRoute } from 'vue-router'
import { ElIcon, ElMenu, ElMenuItem } from 'element-plus'
import {
  // SOP
  Document,
  EditPen,
  Folder,
  // 管理：配置中心
  Setting,
} from '@element-plus/icons-vue'

defineProps<{ collapsed: boolean }>()
const route = useRoute()

interface NavItem {
  label: string
  path?: string
  requiredPermission?: string
  // 折叠态侧栏只显示图标（el-menu 折叠时隐藏 #title 文字），每项必须配一个。
  icon?: Component
}
interface NavGroup {
  label: string
  entries: NavItem[]
}

// 导航目标路径；无 path 的占位项落到 soon: 前缀避免空 index。
function menuIndex(it: NavItem): string {
  return it.path ?? `soon:${it.label}`
}

const groups = computed<NavGroup[]>(() => [
  {
    label: 'SOP',
    entries: [
      { label: '程序库', path: '/procedures/library', icon: Document },
      { label: '草稿箱', path: '/procedures/drafts', icon: EditPen },
      { label: '文件夹', path: '/procedures/folders', icon: Folder },
    ],
  },
  {
    label: '管理',
    entries: [
      { label: '配置中心', path: '/admin/config', icon: Setting },
    ],
  },
])

const activeMenu = computed<string>(() => {
  const p = route.path
  // 配置中心吸附其全部子路径（子页/重定向落点均高亮所属入口）。
  if (p.startsWith('/admin/config')) return '/admin/config'
  if (p.startsWith('/admin/')) return p
  if (p.startsWith('/procedures/drafts')) return '/procedures/drafts'
  if (p.startsWith('/procedures/folders')) return '/procedures/folders'
  if (p.startsWith('/procedures')) return '/procedures/library'
  return ''
})

defineExpose({ activeMenu, groups })
</script>

<template>
  <aside class="app-aside" :class="{ collapsed }">
    <el-menu
      :default-active="activeMenu"
      :collapse="collapsed"
      :collapse-transition="false"
      router
      text-color="var(--text-regular)"
      background-color="transparent"
      :style="{ '--el-menu-active-color': 'var(--accent)' }"
    >
      <template v-for="g in groups" :key="g.label">
        <div v-if="!collapsed && g.entries.length" class="menu-group-label">{{ g.label }}</div>
        <el-menu-item v-for="entry in g.entries" :key="entry.label" :index="menuIndex(entry)">
          <!-- 默认 slot 的图标在折叠态仍显示（#title 文字此时被 el-menu 隐藏）。 -->
          <el-icon v-if="entry.icon" class="nav-icon"><component :is="entry.icon" /></el-icon>
          <template #title>
            {{ entry.label }}
          </template>
        </el-menu-item>
      </template>
    </el-menu>
  </aside>
</template>

<style scoped>
.app-aside {
  width: 240px;
  background: var(--bg-surface);
  border-right: 1px solid var(--border-subtle);
  display: flex;
  flex-direction: column;
  transition: width 0.2s ease;
  overflow: hidden;
}
.app-aside.collapsed {
  width: 64px;
}
.app-aside :deep(.el-menu) {
  border-right: none;
  background: transparent;
  flex: 1;
  /* 菜单项超出可视高度时纵向滚动，横向裁切避免折叠动画溢出 */
  overflow-y: auto;
  overflow-x: hidden;
}
.menu-group-label {
  padding: 14px 16px 4px;
  font-size: 11px;
  color: var(--text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

/* 选中态：左 3px 陶土橙竖条 + accent-bg 底（design-system.md §3.2）。
   EP 默认仅给激活项换文字色，这里补足竖条与底色，强化层级辨识。 */
.app-aside :deep(.el-menu-item.is-active) {
  position: relative;
  background: var(--accent-bg);
}
.app-aside :deep(.el-menu-item.is-active)::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 3px;
  background: var(--accent);
}
/* hover 不盖过选中底色 */
.app-aside :deep(.el-menu-item.is-active:hover) {
  background: var(--accent-bg-hover);
}
</style>
