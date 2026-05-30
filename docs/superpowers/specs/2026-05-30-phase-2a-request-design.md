# Phase 2A：维修请求（Request）设计

- **日期**: 2026-05-30
- **状态**: 已批准（设计）
- **上游**: [总体路线图](2026-05-30-smart-cmms-master-roadmap-design.md) · [功能对标矩阵](2026-05-30-feature-parity-matrix.md) · [Phase 1B 设计](2026-05-30-phase-1b-workorder-loop-design.md)
- **作者**: brainstorming 协作产出

---

## 1. 目标与范围

实现 Atlas 对标矩阵 **WO4——维修请求（Request）** 的提交→审批→转工单全链路，与 Phase 1B 工单闭环衔接。本期建立在 Phase 0 多租户基座（`TenantMixin`、`TenantContextMiddleware`、`_ensure_same_tenant`、`require_permission`、软删 helper）、Phase 1A 基础域（Asset/Location/Sequence）与 Phase 1B 工单（`work_order_service`、`work_order_execution_service`）之上。遵循[净室重写护栏](2026-05-30-smart-cmms-master-roadmap-design.md#6-净室重写合规护栏需求-3不可妥协)：Atlas 仅作行为参考，绝不复制其源码/DDL/文案/品牌。

Phase 2 拆为三个独立周期（2A Request / 2B PreventiveMaintenance / 2C Meter），各自走完整 spec→plan→implement。本文是 **2A**。

### 1.1 本期交付（In）

- **Request 核心**：CRUD + 软删；customId（`RQ%06d`，复用 Phase 1A 通用 Sequence，scope=`request`）；title/description/priority/due_date；绑定 asset/location。
- **生命周期状态机**：PENDING / APPROVED / REJECTED / CANCELED，合法转移表 service 层守卫，审批/拒绝/取消专用端点。
- **审批转工单**：审批通过时复制请求字段调 `work_order_service.create_work_order` 生成工单，审批可附加指派/SOP；请求与工单双向弱关联。
- **请求活动/评论时间线**：状态变更/转工单自动写入，用户可发评论。
- 新权限点 `request.*` 入 registry；内置角色补默认集；新增 `requester` 内置角色（对标 Atlas REQUESTER）。
- 全部走 Phase 0 `TenantContextMiddleware` 自动作用域 + `_ensure_same_tenant` 兜底。
- 一个 Alembic 增量迁移（新建 request/activity 表 + 给 tb_work_order 加 request_id 列）。

### 1.2 明确不做（Out，部分预留）

- 语音描述 audioDescription → 后期（低优先）。
- 请求门户 REQUEST_PORTAL → Phase 6（套餐门控）。
- 请求表单字段配置（FieldConfiguration）→ Phase 6。
- 请求分析（/analytics/requests）→ Phase 4。
- PreventiveMaintenance（PM）、Meter/Reading/Trigger → Phase 2B/2C（独立子周期）。
- 前端业务 UI（本期后端 API 优先）。

---

## 2. 请求生命周期状态机

`RequestStatus`（str enum，仿 Phase 1B 的 `WorkOrderStatus`）：

| 状态 | 含义 |
|---|---|
| `PENDING` | 已提交待审批（默认初始态） |
| `APPROVED` | 审批通过（已生成工单，终态） |
| `REJECTED` | 审批拒绝（带原因，终态） |
| `CANCELED` | 提交者撤回（带原因，终态） |

**合法转移表**（service 层守卫，非法 → `bad_request("REQUEST_BAD_TRANSITION")`）：

```
PENDING → APPROVED, REJECTED, CANCELED
APPROVED  → (终态，无出边)
REJECTED  → (终态，无出边)
CANCELED  → (终态，无出边)
```

- 审批是一次性闸门：已决（APPROVED/REJECTED/CANCELED）的请求不可再改状态；若需再处理另开新请求。
- `resolved_at` 在进入任一终态时盖章；`resolved_by_user_id` 记操作人。

---

## 3. 数据模型

全部 UUID 主键、`tb_` 前缀、`TenantMixin`（NOT NULL `company_id`，行级隔离）。Request 软删（`SoftDeleteMixin`）；活动随父由 service 层管理。

### 3.1 Request（`tb_request`）

```
id, company_id*, custom_id(RQ000001),
title, description,
priority(str 枚举: NONE/LOW/MEDIUM/HIGH, 默认 NONE),
due_date(date|null),
asset_id    → tb_asset    (nullable, FK RESTRICT),
location_id → tb_location (nullable, FK RESTRICT),
status(RequestStatus 枚举, 默认 PENDING),
-- 审批结果
work_order_id(str|null)          -- 批准后生成的工单 id（弱引用，无 FK）
resolution_note(Text, 默认 "")    -- 拒绝/取消原因
resolved_by_user_id(str|null), resolved_at(datetime|null),
created_at, updated_at, is_active, deleted_at
```
- `custom_id` 由 Sequence 保证租户内唯一，不设 DB 唯一约束（与 WorkOrder 一致）。
- `work_order_id` 弱引用（无 FK）：工单属另一聚合，且生成后两者各自演进。
- 复用 `WorkOrderPriority` 枚举（同 NONE/LOW/MEDIUM/HIGH），不另立优先级枚举（DRY）。

### 3.2 WorkOrder 反向关联

`tb_work_order` 增列：
```
request_id(str|null)   -- 来源请求 id（弱引用，无 FK；直建工单时为 None）
```
- 由 alembic `add_column` 加入；model 同步加字段。

### 3.3 RequestActivity（`tb_request_activity` — 时间线）

```
id, company_id*, request_id → tb_request (FK CASCADE),
activity_type(str: STATUS_CHANGE / COMMENT / WO_GENERATED),
actor_user_id(str|null),
from_status(str|null), to_status(str|null),   -- 仅 STATUS_CHANGE
comment(Text, 默认 ""),                         -- COMMENT；WO_GENERATED 记工单 custom_id
created_at, updated_at
```
- 只增不软删（审计性质，与 WorkOrderActivity 同理）。STATUS_CHANGE/WO_GENERATED 由 service 在对应操作时自动写；COMMENT 由评论端点写。CREATE 不记（与 WorkOrder 一致）。

### 3.4 模型文件

```
app/models/request_status.py       RequestStatus 枚举 + 合法转移表 ALLOWED_TRANSITIONS + can_transition
app/models/request.py              Request
app/models/request_activity.py     RequestActivity
app/models/work_order.py           （改：加 request_id 列）
```

---

## 4. 审批转工单语义（核心）

### 4.1 审批通过（`POST /api/v1/requests/{id}/approve`）

body `{note?, primary_user_id?, assignee_ids?, team_ids?, procedure_id?}`：
- 请求须为 PENDING；否则 `bad_request("REQUEST_BAD_TRANSITION")`。
- 调 `work_order_service.create_work_order`，用 `WorkOrderCreate` 复制请求的 title/description/priority/due_date/asset_id/location_id 建工单（OPEN 态）；body 的 primary_user_id/assignee_ids/team_ids 叠加到 `WorkOrderCreate`。
- 若 body 带 `procedure_id`：调 `work_order_execution_service.attach_procedure` 挂接（仅 PUBLISHED，校验同 Phase 1B §4.1）。
- 回写：`request.status=APPROVED`、`request.work_order_id=新工单.id`、`resolved_by_user_id=current_user`、`resolved_at=now`；`work_order.request_id=本请求.id`。
- 写 `RequestActivity(STATUS_CHANGE, to_status=APPROVED, comment=note)` + `RequestActivity(WO_GENERATED, comment=工单 custom_id)`。

### 4.2 审批拒绝（`POST /api/v1/requests/{id}/reject`）

body `{reason}`：请求须为 PENDING；置 `status=REJECTED`、`resolution_note=reason`、resolved 盖章；写 `RequestActivity(STATUS_CHANGE→REJECTED, comment=reason)`。

### 4.3 取消（`POST /api/v1/requests/{id}/cancel`）

body `{reason}`：请求须为 PENDING；置 `status=CANCELED`、`resolution_note=reason`、resolved 盖章；写 `RequestActivity(STATUS_CHANGE→CANCELED, comment=reason)`。

### 4.4 编辑限制

`PATCH /requests/{id}` 仅当 PENDING 时允许改业务字段（title/description/priority/due_date/asset_id/location_id）；已决请求改字段 → `bad_request("REQUEST_NOT_PENDING")`。`status` 不经 PATCH 改，只经审批/拒绝/取消端点。

---

## 5. API 面

全部 `/api/v1` 前缀，认证 + 权限点保护。DELETE = 软删。静态子路径 `/pending` 在 `/{id}` 之前注册，避免冲突。

```
请求   GET    /api/v1/requests            列表(过滤 status/priority/asset_id/location_id)  [request.view]
       GET    /api/v1/requests/pending    待审批列表(status=PENDING)                       [request.view]
       POST   /api/v1/requests            建请求                                           [request.create]
       GET    /api/v1/requests/{id}                                                        [request.view]
       PATCH  /api/v1/requests/{id}        改字段(仅 PENDING)                              [request.create]
       DELETE /api/v1/requests/{id}        软删                                            [request.delete]
审批   POST   /api/v1/requests/{id}/approve  {note?,primary_user_id?,assignee_ids?,team_ids?,procedure_id?}  [request.approve]
       POST   /api/v1/requests/{id}/reject   {reason}                                      [request.approve]
       POST   /api/v1/requests/{id}/cancel   {reason}                                      [request.cancel]
活动   GET    /api/v1/requests/{id}/activities                                            [request.view]
       POST   /api/v1/requests/{id}/activities  {comment}  发评论                         [request.view]
```

**策略**：
- 所有按 `{id}` 取对象走 `_ensure`（防 `db.get` 绕过 read-scope），跨租户 → 404。
- `request.approve` 独立权限点（审批需管理级；审批人转工单时即使无 `work_order.create` 也可批，权限以 `request.approve` 为准——service 层不再校验 work_order 权限，由 router 的 approve 端点权限守卫）。
- `request.cancel` 独立（提交者撤回，与审批分开）。
- 评论用 `request.view`（能看请求即可评论）。

---

## 6. RBAC 权限点

入 `app/permissions.py` registry：
```
request.view / request.create / request.cancel / request.delete / request.approve
```

内置角色默认集补齐：

| 角色 | 2A 默认权限 |
|---|---|
| super_admin | 全部（通配，自动含新点） |
| admin | 全部 request.* |
| technician | `request.view` + `request.create` |
| viewer | 仅 `request.view`（viewer 自动派生 `.view` 点） |
| **requester（新增内置角色）** | `request.view` + `request.create`（对标 Atlas REQUESTER：仅提请求） |

> super_admin 通配无需逐点补。`requester` 是本期新增的第 5 个内置角色，仅含请求查看与创建，定位为"报修人"。

---

## 7. 测试重点（pytest，沿用 conftest client/db fixtures）

- **跨租户隔离（最高优先，e2e）**：A 读/改/删/审批/拒绝/取消 B 的请求 → 404；列表不含他租户。
- **customId**：每租户 `RQ000001` 起、各自独立（Sequence scope=`request`）。
- **状态机**：PENDING→APPROVED/REJECTED/CANCELED 合法；终态再审批/拒绝/取消 → 400；非法转移 → 400。
- **审批转工单核心**：
  - approve 复制请求字段建工单（title/description/priority/due_date/asset/location）。
  - approve body 附加 primary_user/assignees/teams 叠加到工单。
  - approve body 带 procedure_id → 工单挂接该 SOP（仅 PUBLISHED；非 PUBLISHED → 校验报错）。
  - 双向关联：request.work_order_id 与 work_order.request_id 互指。
  - approve 后请求 resolved_by/resolved_at 盖章、status=APPROVED。
- **拒绝/取消**：写 resolution_note + resolved 盖章 + 活动。
- **编辑限制**：PATCH 非 PENDING → 400。
- **pending 列表**：仅返回 PENDING。
- **活动时间线**：approve/reject/cancel 自动写 STATUS_CHANGE；approve 额外写 WO_GENERATED；评论端点写 COMMENT；列表按时间序。
- **RBAC**：requester 能 view+create、不能 approve（403）；technician 不能 approve（403）；viewer 只读；无 token 401。
- **全量回归**：不破坏 Phase 0/1A/1B 与 SOP 既有测试。

---

## 8. 净室合规复核

- 全新数据模型，依据领域理解 + 路线图 §4 融合设计编写，未参照 Atlas DDL/源码。
- 不含 "Atlas" 名称、商标、文案、资源。
- **不复刻** Atlas 的 `Request extends WorkOrderBase` 继承结构——用独立 `tb_request` 表 + 与工单的双向弱引用替代。请求审批→工单为通用 CMMS/工作流领域模式，非受版权保护的具体表达。

---

## 9. 下一步

1. 提交本 spec。
2. 用 writing-plans 技能为 Phase 2A 编写实现计划（TDD，bite-sized）。
3. 进入实现（subagent-driven，**串行**——见教训记忆 [[no-parallel-implementer-subagents]]）。
4. 之后 Phase 2B（PreventiveMaintenance）、2C（Meter）再各自走 spec→plan→implement。
