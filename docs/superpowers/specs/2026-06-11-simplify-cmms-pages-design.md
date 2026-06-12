# 精简 CMMS 残留页面，聚焦 SOP 核心 — 设计文档

- 日期：2026-06-11
- 范围：前端（`SmartSOP-pure/frontend`）
- 性质：物理删除四块与 SOP 核心非直接相关的外围功能页面及其连带引用，不可逆。

## 1. 背景与目标

本项目底层为一套 CMMS（维护管理）系统，SOP 仅是其中一个模块。前端存留若干 CMMS 残留与外围功能（人员权限、公司设置、通知、审计、文件库），与 SOP 核心链路（程序库 / 草稿箱 / 文件夹 / 编辑器 / 详情 / 批量审阅 / PDF）无直接关系，增加维护面与界面噪音。

目标：物理删除这些外围页面与路由代码，清理所有连带的悬空引用、导航入口与测试，使前端聚焦 SOP 核心，并保持 `vue-tsc` / `vitest` / `eslint` 全绿。

非目标：不改动 SOP 核心链路功能；不删除前端权限框架；不删除系统设置（SettingsView，控制 SOP 行为）。

## 2. 关键决策（已与需求方确认）

1. **删除力度**：真实物理删除页面与路由代码（不可逆），而非隐藏入口。
2. **删除范围**：人员与权限、公司设置、通知、审计日志 + 文件库 四块。账户/认证、计费锁定（featureLocked）不在范围。
3. **权限框架**：保留。前端 16 处 `hasPermission` 判断一行不改；正确性依赖后端将登录用户统一为 `super_admin`（前置条件，见 §7）。
4. **组织设置**：仅删 `CompanySettingsView`（公司资料 / CMMS 模块开关，前端零消费）；保留 `SettingsView`（系统设置，控制审批流 / 版本号 / 默认等级等 SOP 行为）。
5. **导航收尾**：保留「配置中心」聚合页，仅移除已删模块入口，聚合页剩 系统设置 / SOP配置 / 文件夹配置 三项。

## 3. 删除清单（逐文件）

### 3.1 人员与权限
删除：
- `src/views/platform/PeopleView.vue`
- `src/views/platform/UsersView.vue`
- `src/views/platform/RolesView.vue`
- `src/views/platform/TeamsView.vue`
- `src/api/users.ts`、`src/api/roles.ts`、`src/api/teams.ts`、`src/api/permissions.ts`
- `src/types/platform.ts` 中 User*/Role*/Team*/Permission* 相关类型（保留与其它模块共用的类型；删除后确认无其它引用）

保留：`src/composables/usePermission.ts`、`src/store/auth.ts`（权限框架）。

### 3.2 公司设置
删除：
- `src/views/platform/CompanySettingsView.vue`
- `src/api/companySettings.ts`
- `src/store/companySettings.ts`
- `src/types/platform.ts` 中 `CompanySettings` / `CompanySettingsUpdate`

保留：`src/views/settings/SettingsView.vue`、`src/api/settings.ts`、`src/types/settings.ts`。

### 3.3 通知
删除：
- `src/views/notifications/NotificationCenterView.vue`
- `src/components/NotificationBell.vue`
- `src/components/notifications/NotificationPreferences.vue`
- `src/store/notifications.ts`
- `src/api/notifications.ts`
- `src/utils/notificationText.ts`
- `src/types/notification.ts`

### 3.4 审计日志 + 文件库
删除：
- `src/views/audit/AuditLogsView.vue`、`src/views/audit/AuditLogTab.vue`
- `src/views/admin/FileLibraryView.vue`
- `src/api/auditLogs.ts`
- `src/types/auditLog.ts`

修改：`src/api/attachments.ts` 删除 `listFileLibrary` / `setAttachmentHidden`，**保留** `deleteAttachment` / `downloadAttachment`（程序编辑器与实体附件仍用）。

## 4. 共享代码清理（消除悬空引用）

| 文件 | 清理动作 |
|---|---|
| `src/layouts/AppLayout.vue` | 移除 `useNotificationStore` import、`notif` 变量、`onMounted` 轮询、`onUnmounted` 停止轮询 |
| `src/components/AppTopBar.vue` | 移除 `NotificationBell` import 与 `<NotificationBell />` 渲染 |
| `src/store/auth.ts` | `loadMe()` 中移除 `companySettingsStore().loadSettings()` 调用与相关 import |
| `src/views/admin/config/OrganizationConfigView.vue` | 双 tab（公司设置/系统设置）退化为单一系统设置：直接渲染 `SettingsView`，页标题改「系统设置」 |
| `src/views/admin/config/ConfigConsoleView.vue` | 移除 人员(3)、公司设置(1)、文件库+审计(2) 共 6 条入口；聚合页重组为 系统设置 / SOP配置 / 文件夹配置 三项 |
| `src/components/AppSidebar.vue` | 「管理」组删除「用户与权限」与「审计日志」，仅剩「配置中心」；同步移除不再使用的 icon import（User、Tickets） |
| `src/router/routes.ts` | 删除下列路由与重定向 |

routes.ts 删除项：
- `/admin/people`（name `platform-people`）及 6 条重定向：`/admin/users`、`/admin/roles`、`/admin/teams`、`/platform/users`、`/platform/roles`、`/platform/teams`
- `/notifications`（name `notification-center`）
- `/admin/audit-logs`（name `audit-logs`）及 `/audit-logs` 重定向
- `/admin/files`（name `admin-files`）
- 公司设置相关重定向：`/admin/company`、`/platform/settings`（指向公司设置 tab 的别名）；保留 `/admin/config/organization` 主路由（现指向系统设置）

`/admin/config/organization` 的默认/`tab=company` 别名需改为指向系统设置（不再有 company tab）。

## 5. 导航最终形态

```
侧栏 SOP 组：程序库 · 草稿箱 · 文件夹
侧栏 管理组：配置中心
配置中心聚合页：系统设置 · SOP配置 · 文件夹配置
顶栏：折叠 · 品牌 · 主题切换 · 用户菜单   （通知铃铛已删）
```

`AppSidebar` 的 `activeMenu` 计算需移除对 `/admin/people`、`/admin/audit` 的吸附分支。

## 6. 测试善后

删除对应 spec：
- `tests/unit/UsersView.spec.ts`、`RolesView.spec.ts`、`TeamsView.spec.ts`、`PeopleView.spec.ts`
- `tests/unit/NotificationBell.spec.ts`、`NotificationPreferences.spec.ts`、`views/NotificationCenterView.spec.ts`
- 审计 / 文件库相关 spec（若存在）

修改 spec：
- `tests/unit/router/redirects.spec.ts`：移除人员/审计相关重定向断言与 NEW_PATHS 中已删路径
- `tests/unit/AppTopBar.spec.ts`：移除通知铃铛存在性断言
- `tests/unit/App.spec.ts`：处理 `/notifications` 相关引用
- `tests/unit/ConfigConsoleView.spec.ts`、`configAggregateViews.spec.ts`：按入口缩减更新断言

## 7. 后端协调点（前端范围外，前置条件）

1. **单角色**：后端将登录用户统一为 `super_admin`，使前端保留的 `hasPermission` 对其恒为 true，按钮照常显示。若不满足，删管理界面后部分按钮会被权限隐藏。
2. **公司设置默认值**：`date_format` / `timezone` / `auto_assign` 等改由后端默认值提供。
3. 通知 / 审计的后端接口可继续存在，前端不再调用即可。

## 8. 验证标准

- `npx vue-tsc --noEmit` 退出 0
- `npx vitest run` 全绿
- `npx eslint . --max-warnings 0` 退出 0
- 全局 grep 确认无悬空 import / 路由 name / 组件引用（`NotificationBell`、`platform-people`、`audit-logs`、`companySettings` 等）

## 9. 执行顺序（建议）

按"低风险先行、共享清理随删"原则，分四步，每步后跑 typecheck + 相关测试：
1. 审计 + 文件库（最独立）
2. 通知（清理 AppLayout / AppTopBar）
3. 公司设置（清理 auth.ts / OrganizationConfigView）
4. 人员与权限（清理 routes / sidebar / config 入口）
最后统一 `vue-tsc` + `vitest run` + `eslint` 全量回归，并删除/更新全部受影响 spec。
