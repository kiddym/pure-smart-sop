# 精简 CMMS 残留页面 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 物理删除人员权限、公司设置、通知、审计+文件库四块 CMMS 残留页面及其全部连带引用，使前端聚焦 SOP 核心，回归全绿。

**Architecture:** 删除型变更。按"低风险先行"分四个删除任务 + 一个全量回归任务。每个任务遵循「删文件 → 清理悬空引用 → 删/改对应测试 → 验证（grep 无残留 + typecheck + 相关 vitest）→ commit」循环，以回归绿替代 TDD 红绿循环（删除任务无新增功能可先测）。

**Tech Stack:** Vue 3 + TypeScript + Element Plus + Pinia + vue-router + Vitest + ESLint。

**前置条件（后端，前端范围外）：** 后端将登录用户统一为 `super_admin`，使前端保留的 `hasPermission` 恒为 true、按钮照常显示；公司设置默认值由后端提供。

**通用命令（每个任务的验证用）：**
- 类型检查：`cd "/Users/yuming/Desktop/smart CMMS/pure sop session/SmartSOP-pure/frontend" && npx vue-tsc --noEmit`
- 全量测试：`npx vitest run`
- Lint：`npx eslint . --max-warnings 0`

---

## 文件结构（删除/修改总览）

**纯删除（文件）：**
```
views/audit/AuditLogsView.vue, AuditLogTab.vue
views/admin/FileLibraryView.vue
views/notifications/NotificationCenterView.vue
components/NotificationBell.vue
components/notifications/NotificationPreferences.vue
views/platform/{PeopleView,UsersView,RolesView,TeamsView}.vue
views/platform/CompanySettingsView.vue
store/notifications.ts, store/companySettings.ts
api/{auditLogs,notifications,users,roles,teams,permissions,companySettings}.ts
utils/notificationText.ts
types/{auditLog,notification}.ts
```

**修改（清理悬空引用）：**
```
api/attachments.ts            — 删 listFileLibrary / setAttachmentHidden
layouts/AppLayout.vue         — 删通知轮询
components/AppTopBar.vue       — 删 NotificationBell
store/auth.ts                 — 删 loadMe 的 companySettings、switchAccount/logout 的 notifications
views/admin/config/OrganizationConfigView.vue — 退化为直接渲染 SettingsView
views/admin/config/ConfigConsoleView.vue      — 删 4 个已删模块入口
components/AppSidebar.vue      — 删 2 个管理组入口 + 对应 icon + activeMenu 分支
router/routes.ts              — 删相关路由与重定向
types/platform.ts             — 删 User*/Role*/Team*/CompanySettings 类型（删空则删文件）
```

**测试删除/修改：** 见各任务。

---

## Task 1: 删除 审计日志 + 文件库（最独立）

**Files:**
- Delete: `src/views/audit/AuditLogsView.vue`、`src/views/audit/AuditLogTab.vue`、`src/views/admin/FileLibraryView.vue`、`src/api/auditLogs.ts`、`src/types/auditLog.ts`
- Modify: `src/api/attachments.ts`、`src/router/routes.ts`、`src/components/AppSidebar.vue`、`src/views/admin/config/ConfigConsoleView.vue`
- Test: 删除 `tests/unit/FileLibraryView.spec.ts`（及任何 audit spec）；修改 `tests/unit/router/redirects.spec.ts`

- [ ] **Step 1: 删除文件**

```bash
cd "/Users/yuming/Desktop/smart CMMS/pure sop session/SmartSOP-pure/frontend"
rm src/views/audit/AuditLogsView.vue src/views/audit/AuditLogTab.vue \
   src/views/admin/FileLibraryView.vue src/api/auditLogs.ts src/types/auditLog.ts
rmdir src/views/audit 2>/dev/null || true
```

- [ ] **Step 2: 清理 `api/attachments.ts`**

删除末尾两个文件库专用导出（保留 `deleteAttachment`/`downloadAttachment`/`listEntityAttachments`/`uploadEntityAttachment`）：

移除 L55-61：
```ts
// 全局文件库：当前 company 下跨实体分页列出附件（支持类型/关键字/含隐藏过滤）。
export const listFileLibrary = (query: LibraryQuery = {}): Promise<LibraryPage> =>
  http.get<LibraryPage>('/attachments/library', { params: query }).then((r) => r.data)

// 改附件隐藏标记（复用通用 PUT /attachments/{id}）。
export const setAttachmentHidden = (attachId: string, hidden: boolean): Promise<AttachmentOut> =>
  http.put<AttachmentOut>(`/attachments/${attachId}`, { hidden }).then((r) => r.data)
```
并把首行 import 中不再使用的类型移除：`import type { AttachmentOut, LibraryPage, LibraryQuery } from '@/types/attachment'` → `import type { AttachmentOut } from '@/types/attachment'`（执行时 grep 确认 `LibraryPage`/`LibraryQuery` 在 `src` 内无其它引用；若有则保留）。

- [ ] **Step 3: 清理 `router/routes.ts`**

删除以下三段：
```ts
{
  path: '/admin/audit-logs',
  name: 'audit-logs',
  component: () => import('@/views/audit/AuditLogsView.vue'),
  meta: { title: '审计日志', requiresAuth: true },
},
{ path: '/audit-logs', redirect: '/admin/audit-logs' },
```
以及：
```ts
{
  path: '/admin/files',
  name: 'admin-files',
  component: () => import('@/views/admin/FileLibraryView.vue'),
  meta: { title: '文件库', requiresAuth: true },
},
```

- [ ] **Step 4: 清理 `components/AppSidebar.vue`**

(a) import 块移除 `Tickets`：
```ts
import {
  // SOP
  Document,
  EditPen,
  Folder,
  // 管理：用户与权限
  User,
  // 管理：配置中心
  Setting,
} from '@element-plus/icons-vue'
```
(b) 管理组删除审计日志项（保留用户与权限、配置中心两项不变）：
```ts
  {
    label: '管理',
    entries: [
      { label: '用户与权限', path: '/admin/people', icon: User },
      { label: '配置中心', path: '/admin/config', icon: Setting },
    ],
  },
```
(c) `activeMenu` 删除审计分支、并把 `/admin/files` 从配置中心吸附里移除：
```ts
const activeMenu = computed<string>(() => {
  const p = route.path
  if (p.startsWith('/admin/people')) return '/admin/people'
  if (p.startsWith('/admin/config')) return '/admin/config'
  if (p.startsWith('/admin/')) return p
  if (p.startsWith('/procedures/drafts')) return '/procedures/drafts'
  if (p.startsWith('/procedures/folders')) return '/procedures/folders'
  if (p.startsWith('/procedures')) return '/procedures/library'
  return ''
})
```

- [ ] **Step 5: 清理 `ConfigConsoleView.vue` 的 stage ⑤（运维）**

从 `stages` 数组删除整个 ⑤ 段：
```ts
  { no: '⑤', title: '运维', desc: '文件与审计', entries: [
    { label: '文件库', to: '/admin/files' },
    { label: '审计日志', to: '/admin/audit-logs' },
  ]},
```

- [ ] **Step 6: 删除/修改测试**

```bash
rm tests/unit/FileLibraryView.spec.ts
# grep 确认无其它 audit 专属 spec：
grep -rl "AuditLog\|audit-logs\|FileLibrary" tests/ || true
```
修改 `tests/unit/router/redirects.spec.ts`：从 `REDIRECTS` 删除 `['/audit-logs', '/admin/audit-logs']`；从 `NEW_PATHS` 删除 `'/admin/audit-logs'`。

- [ ] **Step 7: 验证**

```bash
grep -rn "auditLogs\|AuditLog\|audit-logs\|FileLibrary\|listFileLibrary\|setAttachmentHidden\|admin-files" src/ ; echo "↑应为空"
npx vue-tsc --noEmit && npx vitest run && npx eslint . --max-warnings 0
```
Expected: grep 无输出；三命令均退出 0、测试全绿。

- [ ] **Step 8: 提交（按需）**

```bash
git add -A && git commit -m "chore: 删除审计日志与文件库页面（CMMS 残留精简）"
```

---

## Task 2: 删除 通知

**Files:**
- Delete: `src/views/notifications/NotificationCenterView.vue`、`src/components/NotificationBell.vue`、`src/components/notifications/NotificationPreferences.vue`、`src/store/notifications.ts`、`src/api/notifications.ts`、`src/utils/notificationText.ts`、`src/types/notification.ts`
- Modify: `src/layouts/AppLayout.vue`、`src/components/AppTopBar.vue`、`src/store/auth.ts`、`src/router/routes.ts`
- Test: 删除 `NotificationBell.spec.ts`、`NotificationPreferences.spec.ts`、`views/NotificationCenterView.spec.ts`；修改 `AppTopBar.spec.ts`、`App.spec.ts`

- [ ] **Step 1: 删除文件**

```bash
cd "/Users/yuming/Desktop/smart CMMS/pure sop session/SmartSOP-pure/frontend"
rm src/views/notifications/NotificationCenterView.vue \
   src/components/NotificationBell.vue \
   src/components/notifications/NotificationPreferences.vue \
   src/store/notifications.ts src/api/notifications.ts \
   src/utils/notificationText.ts src/types/notification.ts
rmdir src/views/notifications src/components/notifications 2>/dev/null || true
```

- [ ] **Step 2: 清理 `layouts/AppLayout.vue`**

删除通知 import、`notif` 变量、轮询钩子。`<script setup>` 改为：
```ts
import { watch, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import AppTopBar from '@/components/AppTopBar.vue'
import AppSidebar from '@/components/AppSidebar.vue'
import { useSidebar } from '@/composables/useSidebar'
import { decideAutoCollapse } from '@/utils/sidebarAutoCollapse'

const { collapsed, toggle } = useSidebar()
const route = useRoute()
```
并删除原 `onMounted(() => { if (auth.isAuthenticated) notif.startPolling() })` 与 `onUnmounted(() => notif.stopPolling())` 两行及其上方注释。`onMounted`/`onUnmounted` 若不再被其它逻辑使用则一并从 import 移除（执行时确认；当前文件除轮询外未用，故 import 改为 `import { watch } from 'vue'`）。

- [ ] **Step 3: 清理 `components/AppTopBar.vue`**

移除 `import NotificationBell from '@/components/NotificationBell.vue'` 与模板中的 `<NotificationBell />`。

- [ ] **Step 4: 清理 `store/auth.ts` 的 notifications 引用**

`switchAccount` 删除通知清理块（L68-73），变为：
```ts
    async switchAccount(companyId: string): Promise<void> {
      this.loading = true
      try {
        const pair = await authApi.switchAccount(companyId)
        this._applyTokens(pair.access_token, pair.refresh_token)
        await this.loadMe()
      } finally {
        this.loading = false
      }
    },
```
`logout` 删除通知清理块（L96-100），变为：
```ts
    logout(): void {
      authStorage.clearTokens()
      this.user = null
      this._bootstrapPromise = null
    },
```
（`loadMe` 的 companySettings 清理留待 Task 3。）

- [ ] **Step 5: 清理 `router/routes.ts`**

删除：
```ts
{
  path: '/notifications',
  name: 'notification-center',
  component: () => import('@/views/notifications/NotificationCenterView.vue'),
  meta: { title: '通知中心', requiresAuth: true },
},
```

- [ ] **Step 6: 删除/修改测试**

```bash
rm tests/unit/NotificationBell.spec.ts tests/unit/NotificationPreferences.spec.ts
rm tests/unit/views/NotificationCenterView.spec.ts 2>/dev/null || true
```
修改 `tests/unit/AppTopBar.spec.ts`：删除 `import NotificationBell ...` 行与「顶栏含通知铃铛」用例（保留「不再渲染 ⚙ 设置下拉」用例）。
修改 `tests/unit/App.spec.ts`：移除/调整 stub 路由表中对 `/notifications` 的引用（执行时按该 spec 实际写法定位）。

- [ ] **Step 7: 验证**

```bash
grep -rn "NotificationBell\|notificationText\|store/notifications\|api/notifications\|notification-center\|startPolling\|useNotificationStore" src/ ; echo "↑应为空"
npx vue-tsc --noEmit && npx vitest run && npx eslint . --max-warnings 0
```
Expected: grep 无输出；三命令均绿。

- [ ] **Step 8: 提交（按需）**

```bash
git add -A && git commit -m "chore: 删除通知中心与通知铃铛（CMMS 残留精简）"
```

---

## Task 3: 删除 公司设置（保留系统设置）

**Files:**
- Delete: `src/views/platform/CompanySettingsView.vue`、`src/api/companySettings.ts`、`src/store/companySettings.ts`
- Modify: `src/store/auth.ts`、`src/views/admin/config/OrganizationConfigView.vue`、`src/views/admin/config/ConfigConsoleView.vue`、`src/router/routes.ts`、`src/types/platform.ts`
- Test: 修改 `configAggregateViews.spec.ts`、`OrganizationConfigView.spec.ts`（若存在）

- [ ] **Step 1: 删除文件**

```bash
cd "/Users/yuming/Desktop/smart CMMS/pure sop session/SmartSOP-pure/frontend"
rm src/views/platform/CompanySettingsView.vue src/api/companySettings.ts src/store/companySettings.ts
```

- [ ] **Step 2: 清理 `store/auth.ts` 的 `loadMe`**

```ts
    async loadMe(): Promise<void> {
      this.user = await authApi.fetchMe()
    },
```
（删除 try/catch 内 companySettings 动态 import 与 loadSettings 调用及其注释。）

- [ ] **Step 3: 退化 `OrganizationConfigView.vue` 为系统设置单页**

整个文件替换为直接渲染 `SettingsView`（不再有 tab）：
```vue
<script setup lang="ts">
import SettingsView from '@/views/settings/SettingsView.vue'
// 公司设置已删除，本页只剩系统设置，直接渲染 SettingsView。
</script>

<template>
  <div class="config-aggregate">
    <h2 class="page-title">系统设置</h2>
    <SettingsView />
  </div>
</template>

<style scoped>
.config-aggregate {
  padding: 20px 24px;
}
.page-title {
  font-size: 20px;
  font-weight: 600;
  margin: 0 0 12px;
  color: var(--text-primary);
}
</style>
```

- [ ] **Step 4: 清理 `ConfigConsoleView.vue` 的 stage ①，并修正系统设置链接**

删除 stage ①（组织基础）整段：
```ts
  { no: '①', title: '组织基础', desc: '先配组织信息与模块开关', entries: [
    { label: '公司设置 · 模块开关', to: '/admin/config/organization?tab=company' },
  ]},
```
并把 stage ③ 系统设置的 `to` 改为不带 tab：
```ts
  { no: '③', title: '全局参数', desc: '审批流、版本控制等全局开关,影响各模块行为', entries: [
    { label: '系统设置', to: '/admin/config/organization' },
  ]},
```

- [ ] **Step 5: 清理 `router/routes.ts` 公司设置相关重定向**

`/admin/config/organization` 主路由保留，但其 `meta.title` 改为「系统设置」，并删除指向 `tab=company` 的别名重定向。具体：
- 将 `/admin/settings` 的 redirect 由 `{ path: '/admin/config/organization', query: { tab: 'global' } }` 改为 `'/admin/config/organization'`
- 将 `/admin/company` 的 redirect（`{ path: '/admin/config/organization', query: { tab: 'company' } }`）改为 `'/admin/config/organization'`
- `/platform/settings` → `/admin/company` 的链可保留（最终落到系统设置）
执行时核对 routes.ts 现状逐条调整，确保无残留 `tab: 'company'`。

- [ ] **Step 6: 清理 `types/platform.ts`**

删除 `CompanySettings` 与 `CompanySettingsUpdate` 接口（保留其它类型，User*/Role*/Team* 留待 Task 4）。

- [ ] **Step 7: 修改测试**

修改 `tests/unit/configAggregateViews.spec.ts` 与 `tests/unit/OrganizationConfigView.spec.ts`（若存在）：删除「公司设置」tab 相关断言，断言改为系统设置单页（页标题「系统设置」、渲染 SettingsView）。执行时按 spec 实际写法调整。

- [ ] **Step 8: 验证**

```bash
grep -rn "companySettings\|CompanySettings\|公司设置\|tab=company\|tab: 'company'" src/ ; echo "↑应为空（公司设置已删）"
npx vue-tsc --noEmit && npx vitest run && npx eslint . --max-warnings 0
```
Expected: grep 无输出；三命令均绿。

- [ ] **Step 9: 提交（按需）**

```bash
git add -A && git commit -m "chore: 删除公司设置，组织设置退化为系统设置单页（CMMS 残留精简）"
```

---

## Task 4: 删除 人员与权限（清理面最大，最后做）

**Files:**
- Delete: `src/views/platform/{PeopleView,UsersView,RolesView,TeamsView}.vue`、`src/api/{users,roles,teams,permissions}.ts`
- Modify: `src/router/routes.ts`、`src/components/AppSidebar.vue`、`src/views/admin/config/ConfigConsoleView.vue`、`src/types/platform.ts`
- Test: 删除 `UsersView.spec.ts`、`RolesView.spec.ts`、`TeamsView.spec.ts`、`PeopleView.spec.ts`；修改 `redirects.spec.ts`、`ConfigConsoleView.spec.ts`

- [ ] **Step 1: 删除文件**

```bash
cd "/Users/yuming/Desktop/smart CMMS/pure sop session/SmartSOP-pure/frontend"
rm src/views/platform/PeopleView.vue src/views/platform/UsersView.vue \
   src/views/platform/RolesView.vue src/views/platform/TeamsView.vue \
   src/api/users.ts src/api/roles.ts src/api/teams.ts src/api/permissions.ts
# platform 目录若空则删除
rmdir src/views/platform 2>/dev/null || true
```

- [ ] **Step 2: 清理 `router/routes.ts`**

删除人员合并页主路由与 6 条重定向：
```ts
{
  path: '/admin/people',
  name: 'platform-people',
  component: () => import('@/views/platform/PeopleView.vue'),
  meta: { title: '用户与权限', requiresAuth: true, requiredPermission: 'user.view' },
},
{ path: '/admin/users', redirect: { path: '/admin/people', query: { tab: 'users' } } },
{ path: '/admin/roles', redirect: { path: '/admin/people', query: { tab: 'roles' } } },
{ path: '/admin/teams', redirect: { path: '/admin/people', query: { tab: 'teams' } } },
{ path: '/platform/users', redirect: { path: '/admin/people', query: { tab: 'users' } } },
{ path: '/platform/roles', redirect: { path: '/admin/people', query: { tab: 'roles' } } },
{ path: '/platform/teams', redirect: { path: '/admin/people', query: { tab: 'teams' } } },
```

- [ ] **Step 3: 清理 `components/AppSidebar.vue`**

(a) import 块移除 `User`（此时 SOP 组与配置中心不再用 User）：
```ts
import {
  Document,
  EditPen,
  Folder,
  Setting,
} from '@element-plus/icons-vue'
```
（注意：SOP 组「文件夹」用 `Folder`，程序库/草稿箱用 `Document`/`EditPen`，配置中心用 `Setting`。确认 `User` 已无引用再删。）
(b) 管理组只剩配置中心：
```ts
  {
    label: '管理',
    entries: [
      { label: '配置中心', path: '/admin/config', icon: Setting },
    ],
  },
```
(c) `activeMenu` 删除 `/admin/people` 分支：
```ts
const activeMenu = computed<string>(() => {
  const p = route.path
  if (p.startsWith('/admin/config')) return '/admin/config'
  if (p.startsWith('/admin/')) return p
  if (p.startsWith('/procedures/drafts')) return '/procedures/drafts'
  if (p.startsWith('/procedures/folders')) return '/procedures/folders'
  if (p.startsWith('/procedures')) return '/procedures/library'
  return ''
})
```

- [ ] **Step 4: 清理 `ConfigConsoleView.vue` 的 stage ②（人员权限）**

删除整段：
```ts
  { no: '②', title: '人员权限', desc: '角色 → 团队 → 用户,先有角色再分配', entries: [
    { label: '角色', to: '/admin/people?tab=roles' },
    { label: '团队', to: '/admin/people?tab=teams' },
    { label: '用户', to: '/admin/people?tab=users' },
  ]},
```

- [ ] **Step 5: 清理 `types/platform.ts`**

删除 `UserRead/UserCreate/UserInvite/UserUpdate/UserStatus/InviteResult/RoleRead/RoleCreate/RoleUpdate/TeamRead/TeamCreate/TeamUpdate/PermissionGroup` 等人员相关类型。

```bash
# 删完后检查文件是否已空（仅剩 import/空行）：
cat src/types/platform.ts
# 若无任何有效导出，删除文件并 grep 确认无 import：
grep -rn "@/types/platform" src/ tests/ || true
```
若文件已空且无引用：`rm src/types/platform.ts`。

- [ ] **Step 6: 删除/修改测试**

```bash
rm tests/unit/UsersView.spec.ts tests/unit/RolesView.spec.ts \
   tests/unit/TeamsView.spec.ts tests/unit/PeopleView.spec.ts
```
修改 `tests/unit/router/redirects.spec.ts`：从 `REDIRECTS` 删除 6 条人员重定向（`/admin/users`、`/admin/roles`、`/admin/teams`、`/platform/users`、`/platform/roles`、`/platform/teams`）；从 `NEW_PATHS` 删除 `'/admin/people'`。
修改 `tests/unit/ConfigConsoleView.spec.ts`：删除人员/公司设置/文件库/审计相关入口断言，断言改为剩余三项（系统设置、SOP配置、文件夹配置）。

- [ ] **Step 7: 验证**

```bash
grep -rn "platform-people\|/admin/people\|UsersView\|RolesView\|TeamsView\|PeopleView\|api/users\|api/roles\|api/teams\|api/permissions" src/ tests/ ; echo "↑应为空"
npx vue-tsc --noEmit && npx vitest run && npx eslint . --max-warnings 0
```
Expected: grep 无输出；三命令均绿。

- [ ] **Step 8: 提交（按需）**

```bash
git add -A && git commit -m "chore: 删除用户/角色/团队管理界面（保留权限框架，CMMS 残留精简）"
```

---

## Task 5: 全量回归与收尾

**Files:** 无新增改动，仅校验。

- [ ] **Step 1: 悬空引用全局扫描**

```bash
cd "/Users/yuming/Desktop/smart CMMS/pure sop session/SmartSOP-pure/frontend"
grep -rn "NotificationBell\|notification-center\|audit-logs\|FileLibrary\|platform-people\|CompanySettings\|companySettings\|listFileLibrary" src/ tests/ ; echo "↑应全空"
```
Expected: 无输出。

- [ ] **Step 2: 三件套全绿**

```bash
npx vue-tsc --noEmit && echo TSC_OK
npx vitest run
npx eslint . --max-warnings 0 && echo LINT_OK
```
Expected: `TSC_OK`、测试全 passed、`LINT_OK`。

- [ ] **Step 3: 人工抽查导航**

确认侧栏为：SOP 组（程序库/草稿箱/文件夹）+ 管理组（配置中心）；顶栏无通知铃铛；配置中心聚合页为 系统设置/SOP配置/文件夹配置 三项。可启动 `npm run dev` 目视确认。

- [ ] **Step 4: 最终提交（按需）**

```bash
git add -A && git commit -m "chore: CMMS 残留页面精简收尾，回归全绿"
```

---

## 自检结果（写计划后已核对 spec）

- **Spec 覆盖**：§3.1→Task4、§3.2→Task3、§3.3→Task2、§3.4→Task1；§4 共享清理分摊到各任务（含 spec 遗漏的 `auth.ts` switchAccount/logout 通知引用，已在 Task2 Step4 覆盖）；§5 导航→Task1/4 的 AppSidebar+ConfigConsole；§6 测试→各任务测试步；§8 验证→Task5。无遗漏。
- **占位符**：删除型任务以 grep+回归为验证，无模糊占位；个别"执行时按 spec 实际写法定位"针对的是第三方 spec 内部细节，已给定位 grep。
- **类型/命名一致**：路由 name（`audit-logs`/`notification-center`/`platform-people`）、组件名、store/api 路径在删除项与 grep 校验项间一致。
