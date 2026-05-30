# Phase 0：平台基座（Platform Foundation）设计

- **日期**: 2026-05-30
- **状态**: 已批准（设计）
- **上游**: [总体路线图](2026-05-30-smart-cmms-master-roadmap-design.md) · [Atlas 盘点](2026-05-30-atlas-cmms-inventory-and-dependencies.md) · [功能对标矩阵](2026-05-30-feature-parity-matrix.md)
- **作者**: brainstorming 协作产出

---

## 1. 目标

为 Smart CMMS 建立**多租户平台基座**：租户、认证、用户、角色权限、i18n 框架、品牌，并把
已有的 SmartSOP SOP 表纳入多租户体系。这是后续所有阶段（工单、资产、库存、分析……）的地基。

本期遵循[净室重写护栏](2026-05-30-smart-cmms-master-roadmap-design.md#6-净室重写合规护栏需求-3不可妥协)：
Atlas 仅作行为参考，绝不复制其源码/DDL/文案/品牌。

---

## 2. 已确认决策

| 维度 | 决策 |
|------|------|
| 现有数据 | **全新库，无生产数据**——无需真实数据迁移 |
| 多租户隔离 | shared-DB + `company_id` **行级隔离**，**ORM 事件钩子自动作用域** |
| 租户开通 | **自助注册即建租户**（注册人成为该租户超级管理员） |
| 认证 | 邮箱+密码+JWT。本期：注册 + 登录 + 管理员直接建号。**推后**：邮件邀请、自助找回密码 |
| RBAC | **简化角色起步 + 架构预留细粒度**：权限点 code 体系 + 内置 4 角色 |
| 平台运营方 | 身份位**预留**（`is_platform_admin`），Phase 0 **不做**运营后台 UI |
| i18n | 前后端 i18n 框架就位，**仅出中文文案**（架构随时可加他语） |
| 团队 Team | **推后到 Phase 1**（服务于工单指派） |

---

## 3. 范围边界

### 本期交付（In）

- Company 租户根模型 + 自助注册建租户
- 邮箱密码登录（JWT access + refresh）
- 用户管理（含**管理员在租户内直接创建用户账号**，设初始密码）
- 角色与权限点（permission code）体系 + 内置 4 角色播种
- 租户设置（名称、locale）
- 租户隔离机制（ORM 钩子自动作用域 + 关键处显式校验兜底）
- i18n 框架（后端 message-key/locale 解析 + 前端 vue-i18n + 中文语言包）
- 品牌改名 SmartSOP → Smart CMMS（配置驱动）
- 现有 SOP 表接入 `TenantMixin`（`company_id`）+ 迁移 + dev 默认租户播种

### 明确不做（Out，但架构预留）

- 邮件邀请成员、自助找回密码（预留扩展点）
- 平台运营后台 UI（预留 `is_platform_admin` 身份位与跨租户绕过作用域能力）
- 团队 Team（→ Phase 1）
- SSO/OAuth 第三方登录（认证层抽象为可插拔 provider，本期只实现本地 provider）
- 订阅/计费（Company 预留占位字段，不接逻辑 → Phase 6）

---

## 4. 数据模型（Phase 0 新增 / 改造）

`*` 标记的字段由 `TenantMixin` 提供，承载行级隔离。

```
Company（租户根）
    id, name, slug, status(active/suspended), locale(默认 zh-CN), created_at, updated_at
    ◷ 预留占位（不接逻辑）: plan, subscription_status

User
    id, company_id*, email, password_hash, name, status(active/disabled),
    role_id → Role, locale, last_login_at, created_at, updated_at
    ◷ 预留: is_platform_admin（跨租户运营身份，Phase 0 恒 false）
    约束: email 唯一性策略见 §4.1

Role
    id, company_id*, code, name, is_builtin,
    permissions: JSON[ permission_code ]      ← 细粒度预留点
    created_at, updated_at

Permission（不建表）
    以代码常量集中声明权限点 registry；Phase 0 只声明平台层权限点：
      user.create / user.view / user.edit / user.delete
      role.view / role.manage
      company.settings
    业务模块（工单/资产/库存…）的权限点随各自阶段增量加入 registry。
```

### 4.1 email 唯一性

- email 在**单租户内唯一**（`UNIQUE(company_id, email)`）。
- 允许同一 email 出现在不同租户（同一人可属于多家公司）——更贴合多租户 SaaS。
- 自助注册时若该 email 在目标新租户不存在即可建租户（注册总是建新租户 + 新用户）。

### 4.2 内置 4 角色（每个新租户注册时自动播种）

| code | 名称 | 权限 |
|------|------|------|
| `super_admin` | 超级管理员 | 全部权限点（注册人默认此角色，不可删除） |
| `admin` | 管理员 | 用户/角色管理 + 公司设置 |
| `technician` | 技术员 | 业务执行类权限（Phase 0 暂只有查看类） |
| `viewer` | 只读 | 仅 `*.view` |

> 内置角色随后续阶段权限点增多而扩充其默认权限集；租户可自建自定义角色。

---

## 5. 租户隔离机制

1. **租户上下文**：请求进入时，JWT 解出 `company_id` → 存入 `contextvar`（`tenant_context`）。
2. **读自动作用域**：SQLAlchemy `with_loader_criteria` 对所有继承 `TenantMixin` 的实体
   自动注入 `WHERE company_id = :current`。
3. **写自动盖章**：`before_flush` 事件对新建对象自动写入 `company_id`（来自上下文）。
4. **显式兜底**：跨表写入、批量操作等关键路径加显式断言，防越权。
5. **平台超管绕过**（预留）：`is_platform_admin` 为真时可跳过作用域；Phase 0 不启用。
6. **无上下文保护**：未携带有效 `company_id` 的请求访问租户数据时拒绝（避免误读全表）。

---

## 6. 认证流

认证层抽象为可插拔 `AuthProvider`，本期只实现 `LocalPasswordProvider`（为 SSO 预留）。

| 端点 | 说明 |
|------|------|
| `POST /auth/register` | 建 Company + 超管 User + 播种 4 角色 → 返回 JWT |
| `POST /auth/login` | 校验邮箱密码 → 返回 access + refresh JWT |
| `POST /auth/refresh` | 用 refresh 换新 access |
| `GET /auth/me` | 返回当前用户 + 解析出的权限点集合 |

- JWT payload 含 `user_id`、`company_id`、`role_code`。
- 接通 SmartSOP 已有但未接线的 JWT/passlib 脚手架（passlib bcrypt 哈希）。
- 找回密码、邮件邀请不在本期（端点预留命名，返回未实现）。

---

## 7. RBAC

- 权限点 = 字符串 code，集中注册于 `permissions registry`。
- `require_permission("user.create")` 作为 FastAPI 依赖做接口级校验。
- 解析顺序：当前 User → role_id → Role.permissions（code 列表）→ 命中即放行。
- `super_admin` 角色视为拥有全部已注册权限点。
- 后续模块扩展只需：注册新 code + 在内置角色默认集补齐 + 接口挂 `require_permission`，**不改架构**。

### 管理端点（Phase 0）

| 端点 | 权限点 |
|------|--------|
| `GET/POST/PATCH/DELETE /users` | `user.*` |
| `GET /roles`，`POST/PATCH/DELETE /roles` | `role.view` / `role.manage` |
| `GET/PATCH /companies/me`（租户设置） | `company.settings` |

---

## 8. i18n / 品牌 / 现有 SOP 接入

### 8.1 i18n

- **后端**：错误与邮件文案走 message-key + locale；locale 解析优先级
  `user.locale → Accept-Language → 默认 zh-CN`。
- **前端**：接入 `vue-i18n`，提供 `zh-CN` 语言包脚手架；架构上随时可加 `en` 等。
- 本期只产出中文文案；不做语言切换 UI（可后补）。

### 8.2 品牌

- 配置驱动的 App 名：`SmartSOP → Smart CMMS`。
- 替换前端壳、页面标题、`package.json`/配置中的展示名；**不**改内部 Python 包名以免无谓改动。

### 8.3 现有 SOP 表接入多租户

- 为 Folder / Procedure / ProcedureVersion / Section / Step 等 SOP 实体加 `TenantMixin`（`company_id`）。
- Alembic 迁移新增列（全新库，直接 NOT NULL + 外键）。
- dev 环境播种一个默认租户，将种子 SOP 数据挂其名下。
- 这些表纳入 §5 的自动作用域。

---

## 9. 架构与代码组织

在 SmartSOP 仓库内扩展（方案 A）。建议模块边界（各单元职责单一、接口清晰）：

```
backend/app/
  platform/
    tenant/        Company 模型 + 租户上下文(contextvar) + 隔离钩子(TenantMixin, loader_criteria, before_flush)
    auth/          AuthProvider 抽象 + LocalPasswordProvider + JWT + 路由
    users/         User 模型 + CRUD + 路由
    rbac/          Role 模型 + permissions registry + require_permission 依赖
    i18n/          locale 解析 + message catalog
  sop/             已有 SOP 域（接入 TenantMixin）
frontend/
  src/i18n/        vue-i18n + zh-CN 包
  src/...          品牌/壳改名
```

每个子单元应能独立回答：做什么、怎么用、依赖谁。租户隔离钩子是横切基础设施，被所有租户表复用。

---

## 10. 测试重点（pytest）

- **跨租户隔离**（最高优先）：A 租户用户读/改/删 B 租户数据必须失败（404/403）。
- **自动盖章**：新建对象的 `company_id` 来自上下文且正确。
- **认证**：注册建租户+超管+播种角色；登录签发/校验 JWT；refresh。
- **RBAC**：各权限点校验放行/拒绝；super_admin 全通；viewer 仅读。
- **无上下文保护**：缺失 `company_id` 上下文时拒绝访问租户数据。

---

## 11. 净室合规复核

- 全新数据模型，依据领域理解编写，未参照 Atlas 任何 DDL/源码。
- 不含 "Atlas" 名称、商标、文案、资源。
- 多租户/RBAC 为通用工程模式（行级隔离、code 权限点），非受版权保护的具体表达。

---

## 12. 下一步

1. 提交本 spec。
2. 用 writing-plans 技能为 Phase 0 编写实现计划。
3. 进入实现（spec → plan → implement）。
