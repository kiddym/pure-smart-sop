# Phase 1B：工单闭环 + SOP×工单执行 设计

- **日期**: 2026-05-30
- **状态**: 已批准（设计）
- **上游**: [总体路线图](2026-05-30-smart-cmms-master-roadmap-design.md) · [功能对标矩阵](2026-05-30-feature-parity-matrix.md) · [Phase 0 设计](2026-05-30-phase-0-platform-foundation-design.md) · [Phase 1A 设计](2026-05-30-phase-1a-base-domain-design.md)
- **作者**: brainstorming 协作产出

---

## 1. 目标与范围

实现 Smart CMMS 的**核心维护闭环**：工单（WorkOrder）的创建→指派→执行→完成全链路，并落地需求 #1 的差异化核心——**用 SmartSOP 的结构化 SOP 替代 Atlas 的扁平清单（`Task/TaskBase`）作为工单执行依据**。

本期建立在 Phase 0 多租户基座（`TenantMixin`、`TenantContextMiddleware`、`_ensure_same_tenant`、`require_permission`、软删 helper）与 Phase 1A 基础域（Asset/Location/Team/Sequence）之上。遵循[净室重写护栏](2026-05-30-smart-cmms-master-roadmap-design.md#6-净室重写合规护栏需求-3不可妥协)：Atlas 仅作行为参考，绝不复制其源码/DDL/文案/品牌。

### 1.1 本期交付（In）

- **WorkOrder 核心**：CRUD + 软删；customId（`WO%06d`，复用 Phase 1A 通用 Sequence，scope=`work_order`）；title/description/priority/due_date；绑定 asset/location；指派 primary_user（单列）+ assignedTo（多人表）+ team（多对多）。
- **生命周期状态机**：OPEN / IN_PROGRESS / ON_HOLD / COMPLETE / CANCELED，合法转移表 service 层守卫，专用 transition 端点（原子写时间线）。
- **SOP×工单执行**：版本钉定（挂接已发布 Procedure 版本，不可变）+ 逐 step 响应叠加（仅 `kind='step'` 节点生成执行行）；执行视图合并只读结构 + 响应；required 字段校验；完成校验。
- **工单活动/评论时间线**：状态变更/挂接/标记完成自动写入，用户可发评论。
- 新权限点 `work_order.*` 入 registry；内置 4 角色补默认集。
- 全部走 Phase 0 `TenantContextMiddleware` 自动作用域 + `_ensure_same_tenant` 兜底。
- 一个 Alembic 增量迁移（全新建表，无需 dialect 分支）。

### 1.2 明确不做（Out，部分预留）

- 工时登记、人工/备件成本 → Phase 4（分析）/后期。
- 附件文件关联（工单/执行行）→ 文件阶段（Phase 5）。
- Request（维修请求→审批→转工单）→ Phase 2（独立子系统，自有状态机/角色）。
- PreventiveMaintenance（PM 排程自动建单）、Meter/Reading/Trigger → Phase 2。
- 工单 PDF 导出（复用 ReportLab）→ 后期小周期（执行记录已结构化，可随时补）。
- 前端业务 UI（本期后端 API 优先；UI 作为紧随其后的小周期）。

---

## 2. 工单生命周期状态机

`WorkOrderStatus`（str enum，仿 Phase 1A 的 `AssetStatus`）：

| 状态 | 含义 |
|---|---|
| `OPEN` | 已创建待开始（默认初始态） |
| `IN_PROGRESS` | 执行中 |
| `ON_HOLD` | 挂起（等备件/审批等） |
| `COMPLETE` | 已完成 |
| `CANCELED` | 已取消（终态，不可重开） |

**合法转移表**（service 层 `_assert_transition` 守卫，非法 → `bad_request("WORKORDER_BAD_TRANSITION")`）：

```
OPEN        → IN_PROGRESS, CANCELED
IN_PROGRESS → ON_HOLD, COMPLETE, CANCELED
ON_HOLD     → IN_PROGRESS, CANCELED
COMPLETE    → IN_PROGRESS          (重开：回到执行中，保留执行行)
CANCELED    → (终态，无出边)
```

- 状态变更走**专用端点** `POST /api/v1/work-orders/{id}/transition`（body `{to_status, note?}`），原子地校验转移 + 改 status + 写一条 `WorkOrderActivity(STATUS_CHANGE)`。普通 PATCH 只改业务字段，**不碰 status**。
- 转 `COMPLETE` 前置校验：若挂接了 SOP，则所有执行行须 `is_done=True`，否则 `bad_request("WORKORDER_STEPS_INCOMPLETE")`；未挂 SOP 可直接完成。
- `completed_at` 进入 COMPLETE 时盖章；重开（COMPLETE→IN_PROGRESS）清空 `completed_at`，**保留**执行行与响应。

---

## 3. 数据模型

全部 UUID 主键、`tb_` 前缀、`TenantMixin`（NOT NULL `company_id`，行级隔离）。WorkOrder 软删（`SoftDeleteMixin`）；关联/执行行/活动随父由 service 层管理。M:N 关联表带 `company_id*` 使其成为 `TenantScoped`，作用域统一。

### 3.1 WorkOrder（`tb_work_order`）

```
id, company_id*, custom_id(WO000001),
title, description,
status(WorkOrderStatus 枚举, 默认 OPEN),
priority(str 枚举: NONE/LOW/MEDIUM/HIGH, 默认 NONE),
due_date(date|null),
asset_id    → tb_asset    (nullable, FK RESTRICT),
location_id → tb_location (nullable, FK RESTRICT),
primary_user_id → tb_user (nullable, FK SET NULL),
-- SOP 钉定（执行依据）
procedure_id(str|null)         -- 钉定的具体 Procedure 版本行 id（不可变；弱引用，不设 FK）
procedure_group_id(str|null)   -- 冗余版本族，便于"查看该 SOP 其它版本"
procedure_attached_at(datetime|null),
completed_at(datetime|null),
created_at, updated_at, is_active, deleted_at
```
- `custom_id` 由 Sequence 保证租户内唯一，不设 DB 唯一约束（与 Asset/Location 一致）。
- `procedure_id` 弱引用（无 FK）：钉定的程序版本不可变，且 Procedure 属另一聚合（SOP 引擎）。

### 3.2 指派关联（M:N）

```
WorkOrderAssignee  tb_work_order_assignee  (id, company_id*, work_order_id→tb_work_order CASCADE, user_id→tb_user CASCADE)
    约束: UNIQUE(work_order_id, user_id)
WorkOrderTeam      tb_work_order_team      (id, company_id*, work_order_id→tb_work_order CASCADE, team_id→tb_team CASCADE)
    约束: UNIQUE(work_order_id, team_id)
```
- primary_user 是单列 FK；assignedTo 多人用 assignee 表（与 Asset 的 primaryUser+assignedTo 模式一致）。

### 3.3 WorkOrderStepResult（`tb_work_order_step_result` — 版本钉定执行行）

```
id, company_id*, work_order_id → tb_work_order (FK CASCADE),
node_id(str)                     -- 指向钉定版本里某 kind='step' 的 ProcedureNode id（弱引用，无 FK）
node_code(str), node_sort_order(int)   -- 生成执行行时从节点冗余拷入，执行视图自包含、排序稳定
response(JSON, 默认 {})          -- 操作员对该 step input_schema 的填值
is_done(bool, 默认 False),
done_by_user_id(str|null), done_at(datetime|null),
notes(Text, 默认 ""),
created_at, updated_at
约束: UNIQUE(work_order_id, node_id)
```
- 仅 `kind='step'` 节点生成执行行（见 §4）。弱引用 + 冗余字段是版本钉定方案的关键：钉定版本不可变，执行视图无需回查程序即可稳定渲染。

### 3.4 WorkOrderActivity（`tb_work_order_activity` — 时间线）

```
id, company_id*, work_order_id → tb_work_order (FK CASCADE),
activity_type(str: STATUS_CHANGE / COMMENT / ASSIGN / SOP_ATTACH / STEP_DONE),
actor_user_id(str|null),
from_status(str|null), to_status(str|null),   -- 仅 STATUS_CHANGE
comment(Text, 默认 ""),                         -- COMMENT
created_at, updated_at
```
- 只增不软删（审计性质，与 AssetDowntime 同理）。STATUS_CHANGE/SOP_ATTACH/STEP_DONE/ASSIGN 由 service 在对应操作时自动写；COMMENT 由评论端点写。

### 3.5 模型文件

```
app/models/work_order_status.py      WorkOrderStatus 枚举 + PRIORITIES 常量 + 合法转移表 ALLOWED_TRANSITIONS
app/models/work_order.py             WorkOrder + WorkOrderAssignee + WorkOrderTeam
app/models/work_order_step_result.py WorkOrderStepResult
app/models/work_order_activity.py    WorkOrderActivity
```

---

## 4. SOP×工单执行语义（需求 #1 核心）

复用 Phase 0/SOP 既有 `Procedure`（多版本，`status` ∈ DRAFT/PUBLISHED/ARCHIVED，同 group 共享 `procedure_group_id`）与 `ProcedureNode`（统一节点：`kind` ∈ node/step，step 带 `input_schema` 标准 JSON Schema）。

### 4.1 挂接 SOP（`POST /api/v1/work-orders/{id}/attach-procedure`，body `{procedure_id}`）

- `procedure_id` 必须是一条 `status='PUBLISHED'` 的 Procedure 版本行（草稿/归档不可挂），且同租户；否则 `bad_request`。
- 工单已挂接 → `conflict("WORKORDER_PROCEDURE_ATTACHED")`（需先 detach）。
- 在工单记 `procedure_id` / `procedure_group_id` / `procedure_attached_at`。
- 查询该 procedure 下所有 `kind='step'` 且 `is_active` 的 ProcedureNode，按 `sort_order` 为每个生成一条 `WorkOrderStepResult`（冗余 `node_code`/`node_sort_order`，`response={}`、`is_done=False`）。
- 写 `WorkOrderActivity(SOP_ATTACH)`。
- 钉定即不可变：之后程序新版本/编辑不影响本工单（弱引用 + 已生成执行行）。

### 4.2 解绑（`DELETE /api/v1/work-orders/{id}/procedure`）

- 仅当工单非 COMPLETE 时允许（COMPLETE 后锁定，避免误删执行记录）；否则 `bad_request`。
- 删除全部执行行 + 清空工单 procedure 字段。

### 4.3 执行视图（`GET /api/v1/work-orders/{id}/execution`）

返回自包含视图，合并钉定程序的只读结构与执行响应：
```
{
  procedure: { id, group_id, code, name, version },
  outline: [ {node_id, heading_level, kind, body, code, sort_order} ... ],   // 全部活跃节点（章节/正文做阅读上下文）
  steps:   [ {id, node_id, node_code, input_schema, response, is_done, done_by_user_id, done_at, notes} ... ]  // 仅 step，叠加响应
}
```
- `outline` 给完整阅读上下文（章节/正文只读）；`steps` 是可填写项。`input_schema` 实时从钉定版本节点读取（版本不可变，安全）。
- 工单未挂 SOP → `procedure=null, outline=[], steps=[]`。

### 4.4 填写与标记完成（`PATCH /api/v1/work-orders/{id}/steps/{result_id}`，body `{response?, is_done?, notes?}`）

- 工单须为 `IN_PROGRESS`（其它态不可填 → `bad_request("WORKORDER_NOT_IN_PROGRESS")`，引导先 transition）。
- 置 `is_done=True` 时：
  - **required 校验**：从钉定节点 `input_schema`（标准 JSON Schema）取 `required` 字段集，逐项核对 `response` 中已有非空值；缺 → `bad_request("STEP_REQUIRED_MISSING", 缺失字段名)`。
  - 盖章 `done_by_user_id`（current_user）+ `done_at`，写 `WorkOrderActivity(STEP_DONE)`。
- 置 `is_done=False`（撤销完成）：清 `done_by_user_id`/`done_at`（本期不写撤销活动，从简）。
- `response`/`notes` 可独立更新（不要求同时 done）。

### 4.5 工单完成校验

- transition→COMPLETE 时：若 `procedure_id` 非空，要求**所有**执行行 `is_done=True`（每行置 done 时已做 required 校验，故完成校验只查 `is_done` 全真）。任一未完成 → `bad_request("WORKORDER_STEPS_INCOMPLETE")`。
- 未挂 SOP 的工单：无 step 约束，可直接 COMPLETE。

---

## 5. API 面

全部 `/api/v1` 前缀，认证 + 权限点保护。DELETE = 软删（工单）。子资源都在 `/{id}/...` 下，无静态路径与 `/{id}` 冲突。

```
工单   GET    /api/v1/work-orders            列表(过滤 status/priority/asset_id/location_id/assignee_id/procedure_attached)  [work_order.view]
       POST   /api/v1/work-orders            建单(可选 procedure_id 同时挂 SOP)        [work_order.create]
       GET    /api/v1/work-orders/{id}                                                  [work_order.view]
       PATCH  /api/v1/work-orders/{id}        改字段(标题/描述/优先级/到期/asset·location/primary_user)  [work_order.edit]
       DELETE /api/v1/work-orders/{id}        软删                                       [work_order.delete]
       PUT    /api/v1/work-orders/{id}/assignees   设指派用户集(替换式,去重)            [work_order.edit]
       PUT    /api/v1/work-orders/{id}/teams       设指派团队集(替换式,去重)            [work_order.edit]
状态   POST   /api/v1/work-orders/{id}/transition   {to_status, note?}                   [work_order.edit]
SOP    POST   /api/v1/work-orders/{id}/attach-procedure   {procedure_id}                 [work_order.edit]
       DELETE /api/v1/work-orders/{id}/procedure                                         [work_order.edit]
       GET    /api/v1/work-orders/{id}/execution    合并执行视图                         [work_order.view]
       PATCH  /api/v1/work-orders/{id}/steps/{result_id}   {response?,is_done?,notes?}   [work_order.execute]
活动   GET    /api/v1/work-orders/{id}/activities                                        [work_order.view]
       POST   /api/v1/work-orders/{id}/activities  {comment}  发评论                     [work_order.view]
```

**策略**：
- 所有按 `{id}` 取对象走 `_ensure_same_tenant` 兜底（防 `db.get` 绕过 read-scope），跨租户 → 404。
- `work_order.execute` 独立权限点（技师能执行 step，未必能改/删单）。
- 评论用 `work_order.view`（能看单即可评论）。
- 建单时若带 `procedure_id`，等价于建后立即 attach（同 §4.1 校验与生成）。

---

## 6. RBAC 权限点

入 `app/permissions.py` registry：
```
work_order.view / work_order.create / work_order.edit / work_order.delete / work_order.execute
```

内置角色默认集补齐：

| 角色 | 1B 默认权限 |
|---|---|
| super_admin | 全部（通配，自动含新点） |
| admin | 全部 work_order.* |
| technician | `work_order.view` + `work_order.execute` + `work_order.edit`（现场执行 step、改状态/指派、看单评论；不可建/删单） |
| viewer | 仅 `work_order.view` |

> super_admin 通配无需逐点补；其余三角色显式补 code 列表。

---

## 7. 测试重点（pytest，沿用 conftest client/db fixtures）

- **跨租户隔离（最高优先，e2e）**：A 读/改/删/转移/挂SOP/填step B 的工单 → 404；列表不含他租户。
- **customId**：每租户 `WO000001` 起、各自独立（Sequence scope=`work_order`）。
- **状态机**：合法转移通过；非法转移（OPEN→COMPLETE、CANCELED→任何）→ 400；CANCELED 终态；COMPLETE→IN_PROGRESS 重开保留执行行 + 清 completed_at。
- **完成校验**：挂 SOP 且有未完成 step → COMPLETE 400；全 done → 通过；未挂 SOP 直接 COMPLETE 通过。
- **SOP 执行核心**：
  - attach 仅 PUBLISHED 版本；为每个 step 生成执行行（章节/正文不生成）；重复 attach → 409。
  - 版本钉定不可变：attach 后编辑/新版程序，execution 视图与执行行不变。
  - 填 response + 置 done；required 字段缺失 → 400；done 盖章 done_by/done_at。
  - detach 非 COMPLETE 删执行行；COMPLETE 后 detach → 400。
- **执行视图**：outline 含全部活跃节点、steps 仅 step 且叠加 response。
- **指派**：PUT assignees/teams 替换式、去重；primary_user 单列。
- **活动时间线**：transition/attach/step-done 自动写活动；评论端点写 COMMENT；列表按时间序。
- **RBAC**：technician 能 execute step、转状态，不能 delete（403）；viewer 只读 + 可评论；无 token 401。
- **全量回归**：不破坏 Phase 0/1A 与 SOP 既有测试。

---

## 8. 净室合规复核

- 全新数据模型，依据领域理解 + 路线图 §4 融合设计编写，未参照 Atlas DDL/源码。
- 不含 "Atlas" 名称、商标、文案、资源。Atlas 的 `Task/TaskBase` 扁平清单**不复刻**——由 SOP 执行取代。
- 工单状态机、指派、执行记录、时间线为通用 CMMS/工作流领域模式，非受版权保护的具体表达。

---

## 9. 下一步

1. 提交本 spec。
2. 用 writing-plans 技能为 Phase 1B 编写实现计划（TDD，bite-sized）。
3. 进入实现（subagent-driven 或 inline，**串行**——见教训记忆 [[no-parallel-implementer-subagents]]）。
4. 之后 Phase 2（请求 + PM + 仪表）再走 spec→plan→implement。
