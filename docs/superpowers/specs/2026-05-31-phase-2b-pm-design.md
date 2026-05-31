# Phase 2B：预防性维护（PreventiveMaintenance / PM）设计

- **日期**: 2026-05-31
- **状态**: 已批准（设计）
- **上游**: [总体路线图](2026-05-30-smart-cmms-master-roadmap-design.md) · [功能对标矩阵](2026-05-30-feature-parity-matrix.md) · [Phase 2A 设计](2026-05-30-phase-2a-request-design.md)
- **作者**: brainstorming 协作产出

---

## 1. 目标与范围

实现 Atlas 对标矩阵的 **预防性维护（PreventiveMaintenance / PM）**：按时间计划自动生成工单。PM 与 2A 的维修请求是同构的「触发源 → 生成工单」模式——区别在于触发不是人工审批，而是后台调度任务按 interval 周期自动触发。

本期建立在 Phase 0 多租户基座（`TenantMixin`/`TenantContextMiddleware`/ORM 全局租户事件/`require_permission`/软删 helper）、Phase 1A 基础域（Asset/Location/Sequence）、Phase 1B 工单（`work_order_service.create_work_order`、`work_order_execution_service.attach_procedure`）与既有 APScheduler 调度基础设施（`app/tasks/`）之上。遵循净室重写护栏：Atlas 仅作行为参考，绝不复制其源码/DDL/文案/品牌，产物不含 "Atlas" 字样。

Phase 2 拆为三个独立周期（2A Request / 2B PreventiveMaintenance / 2C Meter），各自走完整 spec→plan→implement。本文是 **2B**。

### 1.1 本期交付（In）

- **PM 核心**：CRUD + 软删；customId（`PM%06d`，复用通用 Sequence，scope=`preventive_maintenance`）；title/description/priority；绑定 asset/location（FK RESTRICT 弱关联）。
- **预设**：primary_user（标量）+ assignee_ids（M:N）+ team_ids（M:N）+ procedure_id（SOP，无 FK 弱引用），生成工单时复制进 `WorkOrderCreate`，与 2A approve 生单能力对齐。
- **调度规则**：简单 interval——`start_date` + `frequency_unit`(DAY/WEEK/MONTH) + `frequency_value`（每 N 个单位）。`next_due_date` 跟踪下一期到期日。
- **生成引擎**：单个每日 APScheduler cron job，跨租户扫描到期 PM → 逐 PM 设租户上下文生成工单 → 锥摆推进 `next_due_date`（一期一单、不补单）→ 逐项提交。
- **调度开关**：`is_enabled` 布尔，与软删 `is_active` 正交；专用 enable/disable 端点。
- **手动「立即生成一次」端点**：复用同一生单+推进逻辑，不校验到期。
- **活动时间线**：CREATED/UPDATED/ENABLED/DISABLED/WO_GENERATED/COMMENT，与 2A `request_activity` 对齐。
- 新权限点 `preventive_maintenance.*`（view/create/edit/delete）入 registry；内置角色补默认集（无新增角色）。
- 一个 Alembic 增量迁移（新建 4 张表）。

### 1.2 明确不做（Out，部分预留）

- **计量触发（Meter/Reading/Trigger）→ Phase 2C**（独立子周期）。本期只做时间 interval 触发。
- cron 式/复杂调度表达 → YAGNI，不做（如有需要后续增量）。
- 错过多期的逐期补单 → 不做（明确采用「跳到未来、一期一单」语义）。
- 可配置 lead_time 偏移 → 不做（生成工单 due_date = 本期计划到期日）。
- PM 分析/报表（/analytics）→ Phase 4。
- 前端业务 UI（本期后端 API 优先）。

---

## 2. 数据模型

### 2.1 枚举 `PMFrequencyUnit`

新建 `app/models/pm_frequency.py`，`PMFrequencyUnit(str, Enum)`：`DAY` / `WEEK` / `MONTH`。priority 复用 Phase 1B 既有 `WorkOrderPriority`（NONE/LOW/MEDIUM/HIGH），不另立。

### 2.2 表 `tb_preventive_maintenance`

Mixins：`UUIDMixin + TimestampMixin + SoftDeleteMixin + TenantMixin`（NOT NULL company_id）。

| 字段 | 类型 | 说明 |
|---|---|---|
| `custom_id` | String(20) NOT NULL | 序列号，scope=`preventive_maintenance`，前缀 `PM`（如 `PM000001`）|
| `title` | String(300) NOT NULL | 生成工单的标题 |
| `description` | Text default "", server_default "" | |
| `priority` | `WorkOrderPriority` enum, NOT NULL, default NONE | |
| `asset_id` | String(36) FK `tb_asset` ondelete RESTRICT, nullable, index | 弱关联 |
| `location_id` | String(36) FK `tb_location` ondelete RESTRICT, nullable, index | 弱关联 |
| `primary_user_id` | String(36) FK `tb_user` ondelete SET NULL, nullable, index | 预设主负责人（同 WO）|
| `procedure_id` | String(36), nullable, index | 预设 SOP，无 FK 弱引用（同 WO）|
| `start_date` | Date NOT NULL | 首期到期日 |
| `frequency_unit` | `PMFrequencyUnit` enum NOT NULL | |
| `frequency_value` | Integer NOT NULL | 每 N 个单位；service 校验 ≥1 |
| `next_due_date` | Date NOT NULL | 创建时 = `start_date` |
| `is_enabled` | Boolean NOT NULL, default True, server_default true | **调度开关**，与软删 `is_active` 正交 |
| `last_generated_at` | DATETIME6, nullable | 审计/UI |
| `last_work_order_id` | String(36), nullable | 弱引用上次生成的 WO |

### 2.3 关联表（照抄 WO 关联表结构）

**`tb_pm_assignee`**：`UUIDMixin + TimestampMixin + TenantMixin`；`pm_id` String(36) FK `tb_preventive_maintenance` ondelete CASCADE index；`user_id` String(36) FK `tb_user` ondelete CASCADE index；`UniqueConstraint(pm_id, user_id, name="uq_pm_assignee")`。

**`tb_pm_team`**：同上，`team_id` String(36) FK `tb_team` ondelete CASCADE index；`UniqueConstraint(pm_id, team_id, name="uq_pm_team")`。

### 2.4 活动表 `tb_pm_activity`（照抄 `request_activity`，去状态字段）

`UUIDMixin + TimestampMixin + TenantMixin`：

| 字段 | 类型 | 说明 |
|---|---|---|
| `pm_id` | String(36), index | 弱引用所属 PM |
| `activity_type` | String | CREATED / UPDATED / ENABLED / DISABLED / WO_GENERATED / COMMENT |
| `actor_user_id` | String(36), nullable | 调度任务自动生成时为 None |
| `comment` | Text default "" | WO_GENERATED 时存生成的工单 customId |
| `created_at` | (TimestampMixin) | 时间线排序键 |

PM 无状态机，故**不要** `from_status`/`to_status` 字段。

---

## 3. 调度语义与推进算法

### 3.1 周期推进纯函数 `_add_interval(d: date, unit, value) -> date`

独立可测，无 `dateutil` 依赖（环境不可用），手写月份加法：

- `DAY` → `d + timedelta(days=value)`
- `WEEK` → `d + timedelta(days=value * 7)`
- `MONTH` → 目标 `year/month` 进位后，把 day 钳制到目标月最后一天（`calendar.monthrange`）。
  - 例：`2026-01-31` + 1 月 → `2026-02-28`；`2026-01-31` + 13 月 → `2027-02-28`。

### 3.2 到期判定

PM 到期当且仅当：`is_active is True`（未软删）且 `is_enabled is True`（未暂停）且 `next_due_date <= today`。`today = now.date()`，`now` 由调度任务注入 → 确定性可测。

### 3.3 锥摆 + 跳到未来（一期一单，不补单）

生成一张工单后推进 `next_due_date`：

```
generated_due = pm.next_due_date          # 这张 WO 的 due_date = 本期计划到期日
nd = pm.next_due_date
while nd <= today:                         # 连加周期直到落在未来
    nd = _add_interval(nd, pm.frequency_unit, pm.frequency_value)
pm.next_due_date = nd
```

- **锚定在计划日历上**：从原 `next_due_date` 累加，不随扫描时刻漂移。
- 停机错过多期时**只产一张工单**，`next_due_date` 一路跳到今天之后第一个未到期点。
- 防御：`while` 每轮 `next_due_date` 严格递增（`value≥1` 由校验保证），不会死循环。

### 3.4 首期语义

创建时 `next_due_date = start_date`。若 `start_date` 是过去日期，首次扫描即生成一张工单（due_date = start_date）并锥摆到未来——「从某历史锚点起按节律」的直觉，只补一张。

### 3.5 改期重算规则（PATCH）

- payload 含 `start_date` → `next_due_date` 重置为新 `start_date`（计划重锁）。
- 仅改 `frequency_unit`/`frequency_value`、不动 `next_due_date`（下期仍按原计划点，之后按新频率递增）。
- `next_due_date` 不作为可写字段暴露给 PATCH（避免不一致状态）。

---

## 4. 生成引擎（调度任务）

新模块 `app/tasks/pm_generate.py`，照搬 `asset_gc` 形状（`run(db, now=...) -> dict 摘要` + `main(argv) -> int` CLI 入口）。

```
TASK_NAME = "pm_generate"

def run(db, *, now=None, commit=True) -> dict[str, int]:
    started = now or utcnow()
    today = started.date()
    # 1) 跨租户扫描：bypass_tenant_scope 下捞所有到期 PM 的 id
    with bypass_tenant_scope():
        due = pm_service.due_candidates(db, today=today)
    generated = errors = 0
    for pm_id in due:
        try:
            pm = db.get(PreventiveMaintenance, pm_id)        # 重核
            token = set_current_company_id(pm.company_id)    # 2) 逐 PM 设租户上下文
            try:
                pm_service.generate_once(db, pm, actor_user_id=None,
                                         now=started, enforce_due=True)
                if commit: db.commit()
                generated += 1
            finally:
                reset_current_company_id(token)
        except Exception:                                    # 3) 逐项提交隔离
            if commit: db.rollback()
            errors += 1
            logger.exception("pm_generate 失败 pm_id=%s", pm_id)
    summary = {"scanned": len(due), "generated": generated, "errors": errors}
    logger.info(json.dumps({"task": TASK_NAME, "started_at": started.isoformat(),
                            **summary}, ensure_ascii=False))
    return summary

def main(argv=None) -> int:   # CLI: python -m app.tasks.pm_generate --once
    ...
```

要点：

- **扫描用 `bypass_tenant_scope()`** 显式跨租户（防御残留上下文污染），只取 id 列表。
- **生单逐 PM 设上下文**，让 `create_work_order` 的写入盖对租户章、`attach_procedure` 的 SOP 查询正确 scope。`create_work_order` 也显式收 `company_id`。
- **逐项提交**：一个坏 PM（引用已删 asset 触发 RESTRICT、或 SOP 非 PUBLISHED 等）只回滚自己、记日志、继续，不拖垮整批。
- `generate_once(...)` 是 service 层核心，被调度任务与手动端点**共用**（`enforce_due` 区分：任务 True 校验到期，手动端点 False）。

### 4.1 scheduler 注册

`build_scheduler()` 加第 4 个 job `pm_generate`，`CronTrigger(hour=settings.cleanup_hour, minute=45)`（与既有 job 错开分钟）。CLI 入口 `python -m app.tasks.pm_generate`。

> **已知契约变更**：`tests/unit/test_tasks.py::test_scheduler_has_three_jobs` 断言恰好 3 个 job → 需更新为 4 个（断言含 `pm_generate`）。

---

## 5. Service 层与 API

### 5.1 `app/services/pm_service.py`（照抄 `request_service` 分层）

| 函数 | 职责 |
|---|---|
| `create_pm(db, payload, company_id, actor_user_id)` | 取号 `PM` 前缀 → 建行 → 写 assignee/team 关联 → `next_due_date=start_date` → 记 CREATED → commit |
| `list_pms(db, *, is_enabled=None, asset_id=None, location_id=None)` | 过滤 `is_active`，按 `custom_id` 排序 |
| `get_pm(db, pm_id)` | 软删过滤，返回 None 或对象 |
| `update_pm(db, pm, payload, company_id, actor_user_id)` | `exclude_unset` 改字段；关联表全量替换；改期重算（§3.5）；记 UPDATED |
| `delete_pm(db, pm)` | 软删（`is_active=False` + `deleted_at`）|
| `enable_pm` / `disable_pm(db, pm, company_id, actor_user_id)` | 翻 `is_enabled`、记 ENABLED/DISABLED |
| `generate_once(db, pm, *, actor_user_id, now, enforce_due)` | §3/§4 核心生单+推进，任务与手动端点共用 |
| `due_candidates(db, *, today)` | 跨租户取到期 PM id 列表（调用方已 bypass）|
| `add_comment` / `list_activities` | 同 2A |
| `_add_interval(d, unit, value)` | §3.1 纯函数 |

**`generate_once` 内部流程**：（`enforce_due` 时先校验 §3.2 到期，否则跳过）复制 PM 预设构造 `WorkOrderCreate(title/description/priority/due_date=pm.next_due_date/asset_id/location_id/primary_user_id/assignee_ids/team_ids)` → `work_order_service.create_work_order` → 若 `procedure_id` 非空则 `work_order_execution_service.attach_procedure` → 回填 `pm.last_generated_at=now`/`pm.last_work_order_id=wo.id` → 记 `WO_GENERATED` 活动（comment=wo.custom_id）→ 锥摆推进 `next_due_date`（§3.3）。工单服务在函数内 import 以避免模块级循环依赖（同 2A）。

**手动生成对 `is_enabled=False` 放行**：手动是显式人为操作，不受暂停开关限制；但软删（`is_active=False`）的 PM 拒绝（`get_pm` 返回 None → 404）。

**校验**：`frequency_value ≥ 1`（否则 `bad_request("PM_INVALID_FREQUENCY")`）；asset/location 存在性交给 FK RESTRICT；`procedure_id` 非 PUBLISHED 由 `attach_procedure` 自身报错。

### 5.2 `app/routers/preventive_maintenances.py`，前缀 `/api/v1/preventive-maintenances`

| 方法 | 路径 | 权限 |
|---|---|---|
| GET | `/`（list，过滤参数 is_enabled/asset_id/location_id）| `preventive_maintenance.view` |
| POST | `/` | `preventive_maintenance.create` |
| GET | `/{id}` | `preventive_maintenance.view` |
| PATCH | `/{id}` | `preventive_maintenance.edit` |
| DELETE | `/{id}` | `preventive_maintenance.delete` |
| POST | `/{id}/enable` · `/{id}/disable` | `preventive_maintenance.edit` |
| POST | `/{id}/generate`（立即生成，返回生成的 WO）| `preventive_maintenance.create` |
| GET | `/{id}/activities` | `preventive_maintenance.view` |
| POST | `/{id}/comments` | `preventive_maintenance.view` |

enable/disable/generate **不新增独立权限码**——归入 edit/create，避免权限码膨胀。全部走 Phase 0 租户自动作用域 + `_ensure_same_tenant` 兜底（沿用 2A 路由模式）。

### 5.3 Schemas `app/schemas/pm.py`

- `PMCreate`：title/description/priority/asset_id/location_id/primary_user_id/procedure_id/assignee_ids/team_ids/start_date/frequency_unit/frequency_value。
- `PMUpdate`：以上字段全可选（`exclude_unset` 部分更新）；不含 `next_due_date`。
- `PMRead`：全字段 + 关联 id 列表 + `next_due_date`/`is_enabled`/`last_generated_at`/`last_work_order_id`/`custom_id`。
- `PMActivityRead`：activity_type/actor_user_id/comment/created_at。

---

## 6. RBAC 权限

### 6.1 新权限码（全拼风格，与 `work_order.*` 一致）

追加到 `app/permissions.py` 的 `ALL_PERMISSIONS`：

```
preventive_maintenance.view
preventive_maintenance.create
preventive_maintenance.edit
preventive_maintenance.delete
```

### 6.2 内置角色分配（`BUILTIN_ROLES`，5 个角色不变）

| 角色 | PM 权限 |
|---|---|
| `super_admin` / `admin` | 全部 4 个（admin=全部码，自动含）|
| `technician` | 仅 `preventive_maintenance.view` |
| `viewer` | 仅 `preventive_maintenance.view`（viewer=所有 `.view`，自动含）|
| `requester` | 无 |

PM 是管理级计划配置，由 admin 维护；technician 只查看，执行的是生成出的工单。

### 6.3 已知需同步更新的契约测试断言

改 `ALL_PERMISSIONS`/`BUILTIN_ROLES` 必然触发：

- `tests/**/test_permissions.py` — 权限码总集
- `tests/**/test_auth_service.py` — 角色默认权限集
- `tests/**/test_roles_api.py` — 角色 API 返回

---

## 7. 迁移、接线、测试策略

### 7.1 Alembic 迁移

`backend/alembic/versions/20260531_0005_phase2b_pm.py`，`revision="phase2b_pm"`，`down_revision="phase2a_request"`。手写 `create_table` ×4（pm / pm_assignee / pm_team / pm_activity），MySQL prod + SQLite dev/test 双方言；`upgrade` 建表 + 索引 + 唯一约束 + FK；`downgrade` 反序 drop。枚举列用 `sa.Enum(...)`（与现有迁移写法一致）。

### 7.2 接线（三处，全用 Edit 精确锚点替换，禁 sed/re.sub）

1. `app/models/__init__.py` — import 区 + `__all__` 登记 `PreventiveMaintenance`/`PMAssignee`/`PMTeam`/`PMActivity`/`PMFrequencyUnit`（conftest 经此触发 create_all）。
2. `app/main.py` — `from app.routers import (...)` 块加 `preventive_maintenances` + 一行 `app.include_router(...)`。
3. `app/tasks/scheduler.py` — import `pm_generate` + `_run_pm_generate()` 包装 + `add_job`。

改完即验证落地：`python -c "import app.main; import app.models; import app.tasks.scheduler"` 通过再继续。新模块务必 `git add` 后再提交。

### 7.3 测试策略

- **纯函数单测**：`_add_interval`（DAY/WEEK/MONTH、月末钳制、跨年）；锥摆推进（错过多期只产一单、不漂移）。
- **service 单测**（`db` fixture）：create 取号/关联表、update 改期重算规则、enable/disable、delete 软删、`generate_once`（enforce_due True/False）、`due_candidates` 跨租户、`frequency_value<1` 校验。
- **调度任务单测**（`db` fixture + 注入 `now`）：到期产单、未到期不产、`is_enabled=False`/软删跳过、逐项提交隔离（一个坏 PM 不拖垮）、多租户各自盖章。
- **API 集成测**（`client`，经 auth API 建主体：register→roles→users→login，不手工 `db.add(User)`，不自定义 client fixture）：CRUD、enable/disable、手动 generate 返回 WO、activities/comments、403 权限边界（technician 不能 create）、租户隔离（A 租户看不到 B 的 PM）。
- **scheduler 装配测**：更新 `test_scheduler_has_three_jobs` → 4 个 job，断言含 `pm_generate`。
- **确定性**：清 `__pycache__`+`.pytest_cache`、`PYTHONDONTWRITEBYTECODE=1`、前台 `pytest` 并 tee 到唯一命名文件后 Read 摘要行；722 → 预期新增若干测试后仍 0 failures。

---

## 8. 风险与缓解

| 风险 | 缓解 |
|---|---|
| 调度任务残留租户上下文导致扫描漏租户 | 扫描显式 `bypass_tenant_scope()`；生单后 `reset_current_company_id` |
| 月末钳制错误（如 1/31 + 1月）| `_add_interval` 纯函数单测覆盖月末/跨年边界 |
| 错过多期产生工单风暴 | 锥摆「跳到未来、一期一单」语义，单测验证只产一张 |
| 改 ALL_PERMISSIONS/BUILTIN_ROLES 漏改契约断言 | §6.3 显式列出三处断言，plan 中作为同一任务 |
| scheduler job 数断言遗漏 | §4.1/§7.3 显式标注更新 three→four |
| 生成工单时 SOP 非 PUBLISHED | `attach_procedure` 自身报错 → 逐项提交隔离，记 errors 不中断批次 |
