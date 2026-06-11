<script setup lang="ts">
import { computed, type Component } from 'vue'
import { useRoute } from 'vue-router'
import { ElIcon, ElMenu, ElMenuItem, ElSubMenu } from 'element-plus'
import {
  // SOP
  Document,
  EditPen,
  Folder,
  // 管理：人员与权限
  User,
  UserFilled,
  Connection,
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
interface NavSubGroup {
  label: string
  icon?: Component
  items: NavItem[]
}
type NavEntry = NavItem | NavSubGroup
interface NavGroup {
  label: string
  entries: NavEntry[]
}

function isSubGroup(e: NavEntry): e is NavSubGroup {
  return (e as NavSubGroup).items !== undefined
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
      {
        label: '人员与权限',
        icon: User,
        items: [
          { label: '用户', path: '/admin/users', icon: User },
          { label: '角色', path: '/admin/roles', icon: UserFilled },
          { label: '团队', path: '/admin/teams', icon: Connection },
        ],
      },
      { label: '配置中心', path: '/admin/config', icon: Setting },
    ],
  },
])

const activeMenu = computed<string>(() => {
  const p = route.path
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
        <template v-for="entry in g.entries" :key="entry.label">
          <el-sub-menu v-if="isSubGroup(entry)" :index="`grp:${entry.label}`">
            <template #title>
              <el-icon v-if="entry.icon" class="nav-icon"><component :is="entry.icon" /></el-icon>
              <span>{{ entry.label }}</span>
            </template>
            <el-menu-item v-for="it in entry.items" :key="it.label" :index="menuIndex(it)">
              <el-icon v-if="it.icon" class="nav-icon"><component :is="it.icon" /></el-icon>
              <template #title>
                {{ it.label }}
              </template>
            </el-menu-item>
          </el-sub-menu>
          <el-menu-item v-else :index="menuIndex(entry)">
            <!-- 默认 slot 的图标在折叠态仍显示（#title 文字此时被 el-menu 隐藏）。 -->
            <el-icon v-if="entry.icon" class="nav-icon"><component :is="entry.icon" /></el-icon>
            <template #title>
              {{ entry.label }}
            </template>
          </el-menu-item>
        </template>
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
   EP 默认仅给激活项换文字色，这里补足竖条与底色，强化层级辨识。
   :deep 选择器同样覆盖 el-sub-menu 内嵌的激活叶子项。 */
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
