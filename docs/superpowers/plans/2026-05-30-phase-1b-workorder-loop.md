# Phase 1B 工单闭环 + SOP×工单执行 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 Smart CMMS 核心维护闭环——工单 CRUD/状态机/指派/时间线，并以 SmartSOP 结构化 SOP（版本钉定 + 逐 step 响应叠加）作为工单执行依据，替代 Atlas 的扁平清单。

**Architecture:** 在 Phase 0 多租户基座 + Phase 1A 基础域之上扩展（同仓库扁平布局）。WorkOrder 用 `TenantMixin`（NOT NULL company_id），由 Phase 0 `TenantContextMiddleware` 自动作用域；`db.get()` 路径用 `_ensure_same_tenant` 兜底。状态变更走专用 transition 端点（原子写时间线）。SOP 执行：挂接已发布 Procedure 版本（弱引用，不可变），仅为 `kind='step'` 节点生成执行行；customId 复用 Phase 1A 通用 Sequence（scope=`work_order`）。

**关键事实（已核对真实代码库，务必遵守）：**
- **扁平布局**：模型 `app/models/`、schema `app/schemas/`、服务 `app/services/`、路由 `app/routers/`；`main.py` 用 `from app.routers import (... )` 括号块 + 逐行 `app.include_router(...)`。
- **错误助手返回 HTTPException**（`app/errors.py`：`bad_request/not_found/conflict/...`），调用处 `raise bad_request(...)`。签名 `(code, message, field=None)`。
- **路由风格**（见 `app/routers/locations.py`）：注入 `current_user: User = Depends(require_permission(permissions.X))` 与 `db: Session = Depends(get_db)`；service create 显式收 `company_id=current_user.company_id`；按主键取对象用模块内 `_ensure(obj, current_user.company_id)`（None 或跨租户 → 404）。
- **软删约定**（见 `app/services/location_service.py`）：list/get 用 `.where(X.is_active.is_(True))`；delete 设 `is_active=False, deleted_at=utcnow()`（`utcnow` 来自 `app.models.base`）。
- **模型注册**：`app/models/__init__.py` 顶部 import + `__all__` 登记；`conftest` 经 `from app.models import (...)` 触发全量 import → `Base.metadata.create_all` 在测试 SQLite 建表。**每个新模型都要登记**。当前 `__all__` 用普通双引号字符串字面量（**直接 Edit 文本，禁止用 re.sub 注入**——曾因此注入字面 `\"` 损坏文件）。
- **多租户隔离事件**已注册在全局 `Session`（`app/tenant_isolation.py`）：有上下文时自动作用域 SELECT、自动盖章 INSERT（仅当 `company_id is None` 时盖）。新表继承 `TenantMixin` 即自动纳入。`conftest` autouse 在每个 test 前后清空租户上下文。
- **SOP 模型**：`Procedure`（`app/models/procedure.py`，`status` ∈ DRAFT/PUBLISHED/ARCHIVED，多版本共享 `procedure_group_id`，`version` int）与 `ProcedureNode`（`app/models/node.py`，`kind` ∈ node/step，step 带 `input_schema` JSON=标准 JSON Schema，`sort_order` int，`code` str，`heading_level` int|null，`body`，`is_active`）。两者为 `NullableTenantMixin`（company_id 可空，但在租户上下文下创建会被盖章）。
- **Sequence**：`app/services/sequence_service.py` 暴露 `next_value(db, scope, company_id) -> int` 与 `format_custom_id(prefix, value, digits=6) -> str`。
- **Alembic 现 head 修订 id = `phase1a_base_domain`**。本期所有表都是新建（`create_table`），FK 在 SQLite 与 MySQL 的 `create_table` 内均可，无需 dialect 分支。
- **测试引擎共享**：`conftest` 的 `client` 与 `db` fixture 绑定同一 in-memory engine（StaticPool）。一个 test 同时取 `(client, db)` 时，经 `db` 直接建的行对 `client` 请求可见——用于 SOP 执行 API 测试中预置 Procedure/Node。

**命令约定：** 后端命令在激活的虚拟环境内：`cd "/Users/yuming/Desktop/smart CMMS/SmartSOP/backend" && source .venv/bin/activate && <cmd>`。**激活 venv 是必须的，否则 `python` 命令找不到**。git 仓库在仓库根（`/Users/yuming/Desktop/smart CMMS/SmartSOP`），提交用 `git -C "/Users/yuming/Desktop/smart CMMS/SmartSOP" add backend/<path>`。当前分支 `phase-0-platform-foundation`（1B 依赖未合并的 0/1A，继续在此分支）。**提交信息结尾加** `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`。

**编辑 `__init__.py` / `main.py` 共享文件的纪律（曾踩坑）：** 用 Edit 工具做精确文本替换，**不要**用 `python -c "re.sub(...)"` 写回（原始替换串会注入字面 `\n`/`\"` 损坏文件）。改完立即 `python -c "import app.main; import app.models"` 验证可导入。

**Tech Stack:** FastAPI · SQLAlchemy 2.0 (sync) · Pydantic v2 · Alembic · MySQL/PyMySQL（生产）· SQLite in-memory（测试）· pytest · TestClient。

**净室合规：** 全新模型，依据领域理解 + 路线图 §4 融合设计编写，绝不复制 Atlas 源码/DDL/文案/品牌；产物不含 "Atlas" 字样。`Task/TaskBase` 扁平清单不复刻。

---

## 文件结构（本期新建 / 改造）

**新建（后端）**
- `app/models/work_order_status.py` — `WorkOrderStatus` 枚举 + `WorkOrderPriority` 枚举 + `ALLOWED_TRANSITIONS`
- `app/models/work_order.py` — `WorkOrder` + `WorkOrderAssignee` + `WorkOrderTeam`
- `app/models/work_order_step_result.py` — `WorkOrderStepResult`
- `app/models/work_order_activity.py` — `WorkOrderActivity`
- `app/schemas/work_order.py` — 工单 + 指派 + 转移 + 执行 + 活动 schema
- `app/services/work_order_service.py` — CRUD/customId/指派/transition/活动
- `app/services/work_order_execution_service.py` — attach/detach/执行视图/填 step/完成校验
- `app/routers/work_orders.py` — `/api/v1/work-orders`（含执行子资源）
- `app/alembic/versions/20260530_0003_phase1b_workorder_loop.py`
- `tests/test_*.py`（各任务）

**改造（后端）**
- `app/permissions.py` — 新增 `work_order.*` 权限点 + 内置角色默认集
- `app/models/__init__.py` — 登记全部新模型
- `app/main.py` — include 新路由

---

## Task 1: 权限点扩展（work_order.*）

**Files:**
- Modify: `backend/app/permissions.py`
- Test: `backend/tests/test_permissions_phase1b.py`

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_permissions_phase1b.py`:

```python
from app import permissions as perms


def test_phase1b_codes_registered():
    for code in [
        "work_order.view", "work_order.create", "work_order.edit",
        "work_order.delete", "work_order.execute",
    ]:
        assert code in perms.ALL_PERMISSIONS


def test_super_admin_wildcard_includes_workorder():
    assert perms.effective_codes("super_admin", []) == set(perms.ALL_PERMISSIONS)


def test_admin_has_all_workorder():
    admin = next(r for r in perms.BUILTIN_ROLES if r["code"] == "admin")
    for code in ["work_order.create", "work_order.delete", "work_order.execute"]:
        assert code in admin["permissions"]


def test_technician_workorder_view_execute_edit_not_delete():
    tech = next(r for r in perms.BUILTIN_ROLES if r["code"] == "technician")
    assert "work_order.view" in tech["permissions"]
    assert "work_order.execute" in tech["permissions"]
    assert "work_order.edit" in tech["permissions"]
    assert "work_order.create" not in tech["permissions"]
    assert "work_order.delete" not in tech["permissions"]


def test_viewer_only_view():
    viewer = next(r for r in perms.BUILTIN_ROLES if r["code"] == "viewer")
    assert "work_order.view" in viewer["permissions"]
    assert "work_order.execute" not in viewer["permissions"]
    assert all(c.endswith(".view") for c in viewer["permissions"])
```

- [ ] **Step 2: 运行确认失败**

Run: `cd "/Users/yuming/Desktop/smart CMMS/SmartSOP/backend" && source .venv/bin/activate && python -m pytest tests/test_permissions_phase1b.py -v`
Expected: FAIL（`work_order.view` 等不在 `ALL_PERMISSIONS`）。

- [ ] **Step 3: 实现**

Edit `backend/app/permissions.py`：在 `TEAM_MANAGE = "team.manage"` 行之后、`_PLATFORM = [` 之前插入新常量块：

```python

# --- 维护闭环（Phase 1B）---
WORK_ORDER_VIEW = "work_order.view"
WORK_ORDER_CREATE = "work_order.create"
WORK_ORDER_EDIT = "work_order.edit"
WORK_ORDER_DELETE = "work_order.delete"
WORK_ORDER_EXECUTE = "work_order.execute"
```

在 `_BASE_DOMAIN = [ ... ]` 列表之后新增一个 `_WORKORDER` 列表，并把它并入 `ALL_PERMISSIONS`。即把：

```python
_BASE_DOMAIN = [
    LOCATION_VIEW, LOCATION_CREATE, LOCATION_EDIT, LOCATION_DELETE,
    ASSET_VIEW, ASSET_CREATE, ASSET_EDIT, ASSET_DELETE,
    ASSET_CATEGORY_VIEW, ASSET_CATEGORY_MANAGE,
    TEAM_VIEW, TEAM_MANAGE,
]

ALL_PERMISSIONS: list[str] = _PLATFORM + _BASE_DOMAIN
```

替换为：

```python
_BASE_DOMAIN = [
    LOCATION_VIEW, LOCATION_CREATE, LOCATION_EDIT, LOCATION_DELETE,
    ASSET_VIEW, ASSET_CREATE, ASSET_EDIT, ASSET_DELETE,
    ASSET_CATEGORY_VIEW, ASSET_CATEGORY_MANAGE,
    TEAM_VIEW, TEAM_MANAGE,
]
_WORKORDER = [
    WORK_ORDER_VIEW, WORK_ORDER_CREATE, WORK_ORDER_EDIT,
    WORK_ORDER_DELETE, WORK_ORDER_EXECUTE,
]

ALL_PERMISSIONS: list[str] = _PLATFORM + _BASE_DOMAIN + _WORKORDER
```

并在 `technician` 角色的 permissions 列表中追加工单点。把：

```python
    {"code": "technician", "name": "技术员", "permissions": [
        USER_VIEW, ROLE_VIEW,
        LOCATION_VIEW, ASSET_VIEW, ASSET_EDIT, ASSET_CATEGORY_VIEW, TEAM_VIEW,
    ]},
```

替换为：

```python
    {"code": "technician", "name": "技术员", "permissions": [
        USER_VIEW, ROLE_VIEW,
        LOCATION_VIEW, ASSET_VIEW, ASSET_EDIT, ASSET_CATEGORY_VIEW, TEAM_VIEW,
        WORK_ORDER_VIEW, WORK_ORDER_EXECUTE, WORK_ORDER_EDIT,
    ]},
```

> `viewer` 自动派生 `.view` 点（含 `work_order.view`），无需改。`admin`/`super_admin` 用 `list(ALL_PERMISSIONS)`，自动含新点。

- [ ] **Step 4: 运行确认通过**

Run: `cd "/Users/yuming/Desktop/smart CMMS/SmartSOP/backend" && source .venv/bin/activate && python -m pytest tests/test_permissions_phase1b.py tests/test_permissions.py tests/test_permissions_phase1a.py -v`
Expected: PASS（新测试 + 原 Phase 0/1A 权限测试）。

- [ ] **Step 5: 提交**

```bash
git -C "/Users/yuming/Desktop/smart CMMS/SmartSOP" add backend/app/permissions.py backend/tests/test_permissions_phase1b.py
git -C "/Users/yuming/Desktop/smart CMMS/SmartSOP" commit -m "feat(rbac): phase1b work_order permission codes

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: 工单状态机（枚举 + 转移表，纯单元）

**Files:**
- Create: `backend/app/models/work_order_status.py`
- Test: `backend/tests/test_work_order_status.py`

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_work_order_status.py`:

```python
from app.models.work_order_status import (
    ALLOWED_TRANSITIONS, WorkOrderPriority, WorkOrderStatus, can_transition,
)


def test_status_values():
    assert {s.value for s in WorkOrderStatus} == {
        "OPEN", "IN_PROGRESS", "ON_HOLD", "COMPLETE", "CANCELED"}


def test_priority_values():
    assert {p.value for p in WorkOrderPriority} == {"NONE", "LOW", "MEDIUM", "HIGH"}


def test_legal_transitions():
    assert can_transition(WorkOrderStatus.OPEN, WorkOrderStatus.IN_PROGRESS)
    assert can_transition(WorkOrderStatus.IN_PROGRESS, WorkOrderStatus.ON_HOLD)
    assert can_transition(WorkOrderStatus.IN_PROGRESS, WorkOrderStatus.COMPLETE)
    assert can_transition(WorkOrderStatus.ON_HOLD, WorkOrderStatus.IN_PROGRESS)
    assert can_transition(WorkOrderStatus.COMPLETE, WorkOrderStatus.IN_PROGRESS)  # 重开
    assert can_transition(WorkOrderStatus.OPEN, WorkOrderStatus.CANCELED)


def test_illegal_transitions():
    assert not can_transition(WorkOrderStatus.OPEN, WorkOrderStatus.COMPLETE)
    assert not can_transition(WorkOrderStatus.CANCELED, WorkOrderStatus.IN_PROGRESS)
    assert not can_transition(WorkOrderStatus.COMPLETE, WorkOrderStatus.ON_HOLD)
    assert not can_transition(WorkOrderStatus.IN_PROGRESS, WorkOrderStatus.IN_PROGRESS)


def test_canceled_is_terminal():
    assert ALLOWED_TRANSITIONS[WorkOrderStatus.CANCELED] == frozenset()
```

- [ ] **Step 2: 运行确认失败**

Run: `cd "/Users/yuming/Desktop/smart CMMS/SmartSOP/backend" && source .venv/bin/activate && python -m pytest tests/test_work_order_status.py -v`
Expected: FAIL（`ModuleNotFoundError: app.models.work_order_status`）。

- [ ] **Step 3: 实现**

Create `backend/app/models/work_order_status.py`:

```python
"""工单状态机与优先级枚举 + 合法转移表（Phase 1B）。"""
from __future__ import annotations

import enum


class WorkOrderStatus(str, enum.Enum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    ON_HOLD = "ON_HOLD"
    COMPLETE = "COMPLETE"
    CANCELED = "CANCELED"


class WorkOrderPriority(str, enum.Enum):
    NONE = "NONE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


# 合法状态转移（CANCELED 为终态；COMPLETE 仅能重开回 IN_PROGRESS）。
ALLOWED_TRANSITIONS: dict[WorkOrderStatus, frozenset[WorkOrderStatus]] = {
    WorkOrderStatus.OPEN: frozenset({WorkOrderStatus.IN_PROGRESS, WorkOrderStatus.CANCELED}),
    WorkOrderStatus.IN_PROGRESS: frozenset(
        {WorkOrderStatus.ON_HOLD, WorkOrderStatus.COMPLETE, WorkOrderStatus.CANCELED}
    ),
    WorkOrderStatus.ON_HOLD: frozenset({WorkOrderStatus.IN_PROGRESS, WorkOrderStatus.CANCELED}),
    WorkOrderStatus.COMPLETE: frozenset({WorkOrderStatus.IN_PROGRESS}),
    WorkOrderStatus.CANCELED: frozenset(),
}


def can_transition(src: WorkOrderStatus, dst: WorkOrderStatus) -> bool:
    return dst in ALLOWED_TRANSITIONS.get(src, frozenset())
```

- [ ] **Step 4: 运行确认通过**

Run: `cd "/Users/yuming/Desktop/smart CMMS/SmartSOP/backend" && source .venv/bin/activate && python -m pytest tests/test_work_order_status.py -v`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git -C "/Users/yuming/Desktop/smart CMMS/SmartSOP" add backend/app/models/work_order_status.py backend/tests/test_work_order_status.py
git -C "/Users/yuming/Desktop/smart CMMS/SmartSOP" commit -m "feat(workorder): status/priority enums + transition table

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: 工单模型层（WorkOrder + 指派 + StepResult + Activity）

**Files:**
- Create: `backend/app/models/work_order.py`
- Create: `backend/app/models/work_order_step_result.py`
- Create: `backend/app/models/work_order_activity.py`
- Modify: `backend/app/models/__init__.py`
- Test: `backend/tests/test_work_order_model.py`

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_work_order_model.py`:

```python
from app.models.company import Company
from app.models.work_order import WorkOrder
from app.models.work_order_status import WorkOrderPriority, WorkOrderStatus


def test_work_order_defaults(db):
    c = Company(name="Acme", slug="acme")
    db.add(c)
    db.commit()
    wo = WorkOrder(custom_id="WO000001", title="换轴承", company_id=c.id)
    db.add(wo)
    db.commit()
    db.refresh(wo)
    assert wo.status == WorkOrderStatus.OPEN
    assert wo.priority == WorkOrderPriority.NONE
    assert wo.is_active is True
    assert wo.procedure_id is None
    assert wo.id is not None and len(wo.id) == 36


def test_step_result_and_activity_importable(db):
    from app.models.work_order_activity import WorkOrderActivity
    from app.models.work_order_step_result import WorkOrderStepResult
    c = Company(name="Acme", slug="acme")
    db.add(c)
    db.commit()
    wo = WorkOrder(custom_id="WO000001", title="t", company_id=c.id)
    db.add(wo)
    db.commit()
    sr = WorkOrderStepResult(
        work_order_id=wo.id, node_id="n1", node_code="S1", node_sort_order=0, company_id=c.id
    )
    act = WorkOrderActivity(work_order_id=wo.id, activity_type="COMMENT", comment="hi", company_id=c.id)
    db.add_all([sr, act])
    db.commit()
    assert sr.is_done is False
    assert act.activity_type == "COMMENT"
```

- [ ] **Step 2: 运行确认失败**

Run: `cd "/Users/yuming/Desktop/smart CMMS/SmartSOP/backend" && source .venv/bin/activate && python -m pytest tests/test_work_order_model.py -v`
Expected: FAIL（`ModuleNotFoundError: app.models.work_order`）。

- [ ] **Step 3: 实现 WorkOrder + 指派**

Create `backend/app/models/work_order.py`:

```python
"""工单及其指派关联（每租户）。

procedure_id/procedure_group_id 为弱引用（无 FK）：钉定的 Procedure 版本
不可变且属 SOP 聚合，故不设外键约束（见 spec §3.1/§3.3）。
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Date, Enum as SAEnum, ForeignKey, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import DATETIME6, Base, UUIDMixin, TimestampMixin, SoftDeleteMixin, TenantMixin
from app.models.work_order_status import WorkOrderPriority, WorkOrderStatus


class WorkOrder(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin, TenantMixin):
    __tablename__ = "tb_work_order"

    custom_id: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
    status: Mapped[WorkOrderStatus] = mapped_column(
        SAEnum(WorkOrderStatus), nullable=False, default=WorkOrderStatus.OPEN
    )
    priority: Mapped[WorkOrderPriority] = mapped_column(
        SAEnum(WorkOrderPriority), nullable=False, default=WorkOrderPriority.NONE
    )
    due_date: Mapped[date | None] = mapped_column(Date, default=None)
    asset_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("tb_asset.id", ondelete="RESTRICT"), index=True
    )
    location_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("tb_location.id", ondelete="RESTRICT"), index=True
    )
    primary_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("tb_user.id", ondelete="SET NULL"), index=True
    )
    # SOP 钉定（弱引用，无 FK）
    procedure_id: Mapped[str | None] = mapped_column(String(36), default=None, index=True)
    procedure_group_id: Mapped[str | None] = mapped_column(String(36), default=None)
    procedure_attached_at: Mapped[datetime | None] = mapped_column(DATETIME6, default=None)
    completed_at: Mapped[datetime | None] = mapped_column(DATETIME6, default=None)


class WorkOrderAssignee(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "tb_work_order_assignee"
    __table_args__ = (
        UniqueConstraint("work_order_id", "user_id", name="uq_work_order_assignee"),
    )

    work_order_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_work_order.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_user.id", ondelete="CASCADE"), index=True
    )


class WorkOrderTeam(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "tb_work_order_team"
    __table_args__ = (
        UniqueConstraint("work_order_id", "team_id", name="uq_work_order_team"),
    )

    work_order_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_work_order.id", ondelete="CASCADE"), index=True
    )
    team_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_team.id", ondelete="CASCADE"), index=True
    )
```

- [ ] **Step 4: 实现 StepResult**

Create `backend/app/models/work_order_step_result.py`:

```python
"""工单执行行（版本钉定，仅 kind='step' 节点生成）。

node_id 为弱引用（无 FK）：钉定版本不可变且节点属 SOP 聚合。
node_code/node_sort_order 生成时冗余拷入，使执行视图自包含、排序稳定。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import DATETIME6, Base, UUIDMixin, TimestampMixin, TenantMixin


class WorkOrderStepResult(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "tb_work_order_step_result"

    work_order_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_work_order.id", ondelete="CASCADE"), index=True
    )
    node_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    node_code: Mapped[str] = mapped_column(String(50), default="", server_default="")
    node_sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    response: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    is_done: Mapped[bool] = mapped_column(default=False, server_default="0")
    done_by_user_id: Mapped[str | None] = mapped_column(String(36), default=None)
    done_at: Mapped[datetime | None] = mapped_column(DATETIME6, default=None)
    notes: Mapped[str] = mapped_column(Text, default="", server_default="")

    __table_args__ = ()
```

> 注：执行行的「同工单同节点唯一」由 service 层 attach 逻辑保证（attach 时清旧建新），不设 DB 唯一约束以简化（spec §3.3 提及 UNIQUE 为意图，本实现用 service 保证；如需 DB 约束可在迁移加，但本期从简）。

- [ ] **Step 5: 实现 Activity**

Create `backend/app/models/work_order_activity.py`:

```python
"""工单活动时间线（只增不软删，审计性质）。"""
from __future__ import annotations

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDMixin, TimestampMixin, TenantMixin


class WorkOrderActivity(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "tb_work_order_activity"

    work_order_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_work_order.id", ondelete="CASCADE"), index=True
    )
    # STATUS_CHANGE / COMMENT / ASSIGN / SOP_ATTACH / STEP_DONE
    activity_type: Mapped[str] = mapped_column(String(20), nullable=False)
    actor_user_id: Mapped[str | None] = mapped_column(String(36), default=None)
    from_status: Mapped[str | None] = mapped_column(String(20), default=None)
    to_status: Mapped[str | None] = mapped_column(String(20), default=None)
    comment: Mapped[str] = mapped_column(Text, default="", server_default="")
```

- [ ] **Step 6: 登记模型**

Edit `backend/app/models/__init__.py`。在 import 区（`from app.models.user import User` 之前的合适位置）加入：

```python
from app.models.work_order import WorkOrder, WorkOrderAssignee, WorkOrderTeam
from app.models.work_order_activity import WorkOrderActivity
from app.models.work_order_step_result import WorkOrderStepResult
```

在 `__all__` 列表（`"User",` 之前）加入：

```python
    "WorkOrder",
    "WorkOrderActivity",
    "WorkOrderAssignee",
    "WorkOrderStepResult",
    "WorkOrderTeam",
```

> 用 Edit 工具做文本替换（找到 `from app.models.user import User` 与 `    "User",` 作为锚点插入）。改完执行 `python -c "import app.models; print(len(app.models.__all__))"` 确认可导入、无 `SyntaxError`。`work_order_status` 无表，不登记。

- [ ] **Step 7: 运行确认通过**

Run: `cd "/Users/yuming/Desktop/smart CMMS/SmartSOP/backend" && source .venv/bin/activate && python -m pytest tests/test_work_order_model.py -v`
Expected: PASS。

- [ ] **Step 8: 全量回归 + 提交**

Run: `cd "/Users/yuming/Desktop/smart CMMS/SmartSOP/backend" && source .venv/bin/activate && python -m pytest -q`
Expected: 全部 PASS。

```bash
git -C "/Users/yuming/Desktop/smart CMMS/SmartSOP" add backend/app/models/work_order.py backend/app/models/work_order_step_result.py backend/app/models/work_order_activity.py backend/app/models/__init__.py backend/tests/test_work_order_model.py
git -C "/Users/yuming/Desktop/smart CMMS/SmartSOP" commit -m "feat(workorder): WorkOrder/Assignee/Team/StepResult/Activity models

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: 工单 schema

**Files:**
- Create: `backend/app/schemas/work_order.py`
- Test: `backend/tests/test_work_order_schemas.py`

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_work_order_schemas.py`:

```python
import pytest
from pydantic import ValidationError

from app.models.work_order_status import WorkOrderPriority, WorkOrderStatus
from app.schemas.work_order import (
    StepResultUpdate, WorkOrderCreate, WorkOrderTransition, WorkOrderUpdate,
)


def test_create_defaults():
    c = WorkOrderCreate(title="换油")
    assert c.priority == WorkOrderPriority.NONE
    assert c.description == ""
    assert c.assignee_ids == []
    assert c.procedure_id is None


def test_create_requires_title():
    with pytest.raises(ValidationError):
        WorkOrderCreate(title="")


def test_transition_parses_status():
    t = WorkOrderTransition(to_status="IN_PROGRESS")
    assert t.to_status == WorkOrderStatus.IN_PROGRESS


def test_update_is_partial():
    u = WorkOrderUpdate()
    assert u.model_dump(exclude_unset=True) == {}


def test_step_result_update_partial():
    s = StepResultUpdate(is_done=True)
    data = s.model_dump(exclude_unset=True)
    assert data == {"is_done": True}
```

- [ ] **Step 2: 运行确认失败**

Run: `cd "/Users/yuming/Desktop/smart CMMS/SmartSOP/backend" && source .venv/bin/activate && python -m pytest tests/test_work_order_schemas.py -v`
Expected: FAIL（`ModuleNotFoundError`）。

- [ ] **Step 3: 实现**

Create `backend/app/schemas/work_order.py`:

```python
"""工单 schema（Phase 1B）。"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.work_order_status import WorkOrderPriority, WorkOrderStatus


class WorkOrderCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: str = ""
    priority: WorkOrderPriority = WorkOrderPriority.NONE
    due_date: date | None = None
    asset_id: str | None = None
    location_id: str | None = None
    primary_user_id: str | None = None
    assignee_ids: list[str] = []
    team_ids: list[str] = []
    # 建单时可选立即挂接已发布 SOP
    procedure_id: str | None = None


class WorkOrderUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = None
    priority: WorkOrderPriority | None = None
    due_date: date | None = None
    asset_id: str | None = None
    location_id: str | None = None
    primary_user_id: str | None = None


class WorkOrderTransition(BaseModel):
    to_status: WorkOrderStatus
    note: str = ""


class AssigneesSet(BaseModel):
    user_ids: list[str] = []


class TeamsSet(BaseModel):
    team_ids: list[str] = []


class WorkOrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    custom_id: str
    title: str
    description: str
    status: WorkOrderStatus
    priority: WorkOrderPriority
    due_date: date | None = None
    asset_id: str | None = None
    location_id: str | None = None
    primary_user_id: str | None = None
    procedure_id: str | None = None
    procedure_group_id: str | None = None
    completed_at: datetime | None = None
    assignee_ids: list[str] = []
    team_ids: list[str] = []


class StepResultUpdate(BaseModel):
    response: dict[str, Any] | None = None
    is_done: bool | None = None
    notes: str | None = None


class StepResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    node_id: str
    node_code: str
    node_sort_order: int
    input_schema: dict[str, Any] = {}
    response: dict[str, Any] = {}
    is_done: bool
    done_by_user_id: str | None = None
    done_at: datetime | None = None
    notes: str


class OutlineNode(BaseModel):
    node_id: str
    heading_level: int | None = None
    kind: str
    body: str
    code: str
    sort_order: int


class ProcedureRef(BaseModel):
    id: str
    group_id: str | None = None
    code: str
    name: str
    version: int


class ExecutionView(BaseModel):
    procedure: ProcedureRef | None = None
    outline: list[OutlineNode] = []
    steps: list[StepResultRead] = []


class AttachProcedure(BaseModel):
    procedure_id: str


class CommentCreate(BaseModel):
    comment: str = Field(min_length=1)


class ActivityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    activity_type: str
    actor_user_id: str | None = None
    from_status: str | None = None
    to_status: str | None = None
    comment: str
    created_at: datetime
```

- [ ] **Step 4: 运行确认通过**

Run: `cd "/Users/yuming/Desktop/smart CMMS/SmartSOP/backend" && source .venv/bin/activate && python -m pytest tests/test_work_order_schemas.py -v`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git -C "/Users/yuming/Desktop/smart CMMS/SmartSOP" add backend/app/schemas/work_order.py backend/tests/test_work_order_schemas.py
git -C "/Users/yuming/Desktop/smart CMMS/SmartSOP" commit -m "feat(workorder): work order schemas

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: 工单服务（CRUD / customId / 指派 / transition / 活动）

**Files:**
- Create: `backend/app/services/work_order_service.py`
- Test: `backend/tests/test_work_order_service.py`

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_work_order_service.py`:

```python
import pytest
from fastapi import HTTPException

from app import tenant
from app.models.company import Company
from app.models.user import User
from app.models.work_order_status import WorkOrderStatus
from app.schemas.work_order import WorkOrderCreate, WorkOrderTransition, WorkOrderUpdate
from app.services import work_order_service as svc


def _company(db, slug):
    c = Company(name=slug, slug=slug)
    db.add(c)
    db.commit()
    return c


def _ctx(company_id):
    tenant.set_current_company_id(company_id)


def test_create_assigns_custom_id(db):
    c = _company(db, "acme")
    _ctx(c.id)
    a = svc.create_work_order(db, WorkOrderCreate(title="泵1"), c.id, actor_user_id=None)
    b = svc.create_work_order(db, WorkOrderCreate(title="泵2"), c.id, actor_user_id=None)
    assert a.custom_id == "WO000001"
    assert b.custom_id == "WO000002"
    assert a.status == WorkOrderStatus.OPEN


def test_tenants_independent_custom_id(db):
    c1 = _company(db, "acme"); c2 = _company(db, "globex")
    _ctx(c1.id)
    a = svc.create_work_order(db, WorkOrderCreate(title="x"), c1.id, actor_user_id=None)
    _ctx(c2.id)
    b = svc.create_work_order(db, WorkOrderCreate(title="y"), c2.id, actor_user_id=None)
    assert a.custom_id == "WO000001" and b.custom_id == "WO000001"


def test_assignees_replace_and_dedupe(db):
    c = _company(db, "acme")
    _ctx(c.id)
    u1 = User(company_id=c.id, email="u1@a.com", password_hash="x", name="U1")
    u2 = User(company_id=c.id, email="u2@a.com", password_hash="x", name="U2")
    db.add_all([u1, u2]); db.commit()
    wo = svc.create_work_order(db, WorkOrderCreate(title="t"), c.id, actor_user_id=None)
    svc.set_assignees(db, wo, [u1.id, u2.id, u1.id], c.id)
    assert set(svc.assignee_ids(db, wo.id)) == {u1.id, u2.id}
    svc.set_assignees(db, wo, [u1.id], c.id)
    assert svc.assignee_ids(db, wo.id) == [u1.id]


def test_legal_transition_writes_activity(db):
    c = _company(db, "acme")
    _ctx(c.id)
    wo = svc.create_work_order(db, WorkOrderCreate(title="t"), c.id, actor_user_id="u9")
    svc.transition(db, wo, WorkOrderTransition(to_status=WorkOrderStatus.IN_PROGRESS),
                   c.id, actor_user_id="u9")
    assert wo.status == WorkOrderStatus.IN_PROGRESS
    acts = svc.list_activities(db, wo.id)
    assert any(a.activity_type == "STATUS_CHANGE" and a.to_status == "IN_PROGRESS" for a in acts)


def test_illegal_transition_rejected(db):
    c = _company(db, "acme")
    _ctx(c.id)
    wo = svc.create_work_order(db, WorkOrderCreate(title="t"), c.id, actor_user_id=None)
    with pytest.raises(HTTPException) as exc:
        svc.transition(db, wo, WorkOrderTransition(to_status=WorkOrderStatus.COMPLETE),
                       c.id, actor_user_id=None)
    assert exc.value.status_code == 400


def test_complete_sets_and_reopen_clears_completed_at(db):
    c = _company(db, "acme")
    _ctx(c.id)
    wo = svc.create_work_order(db, WorkOrderCreate(title="t"), c.id, actor_user_id=None)
    svc.transition(db, wo, WorkOrderTransition(to_status=WorkOrderStatus.IN_PROGRESS), c.id, None)
    svc.transition(db, wo, WorkOrderTransition(to_status=WorkOrderStatus.COMPLETE), c.id, None)
    assert wo.completed_at is not None
    svc.transition(db, wo, WorkOrderTransition(to_status=WorkOrderStatus.IN_PROGRESS), c.id, None)
    assert wo.completed_at is None


def test_update_and_soft_delete(db):
    c = _company(db, "acme")
    _ctx(c.id)
    wo = svc.create_work_order(db, WorkOrderCreate(title="t"), c.id, actor_user_id=None)
    svc.update_work_order(db, wo, WorkOrderUpdate(title="t2", description="d"))
    assert wo.title == "t2" and wo.description == "d"
    svc.delete_work_order(db, wo)
    assert wo.is_active is False
    assert svc.get_work_order(db, wo.id) is None


def test_comment_activity(db):
    c = _company(db, "acme")
    _ctx(c.id)
    wo = svc.create_work_order(db, WorkOrderCreate(title="t"), c.id, actor_user_id=None)
    svc.add_comment(db, wo, "需要备件", c.id, actor_user_id="u3")
    acts = svc.list_activities(db, wo.id)
    assert any(a.activity_type == "COMMENT" and a.comment == "需要备件" for a in acts)
```

- [ ] **Step 2: 运行确认失败**

Run: `cd "/Users/yuming/Desktop/smart CMMS/SmartSOP/backend" && source .venv/bin/activate && python -m pytest tests/test_work_order_service.py -v`
Expected: FAIL（`ModuleNotFoundError`）。

- [ ] **Step 3: 实现**

Create `backend/app/services/work_order_service.py`:

```python
"""工单服务：CRUD、customId、指派、状态转移、活动时间线。

SOP 执行相关逻辑见 work_order_execution_service。挂接了 SOP 的工单转
COMPLETE 的 step 完成校验也在 execution service（避免循环依赖：本模块在
transition 时按需 import）。
"""
from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.errors import bad_request
from app.models.base import utcnow
from app.models.work_order import WorkOrder, WorkOrderAssignee, WorkOrderTeam
from app.models.work_order_activity import WorkOrderActivity
from app.models.work_order_status import WorkOrderStatus, can_transition
from app.schemas.work_order import WorkOrderCreate, WorkOrderTransition, WorkOrderUpdate
from app.services import sequence_service


def assignee_ids(db: Session, work_order_id: str) -> list[str]:
    return list(db.execute(
        select(WorkOrderAssignee.user_id).where(WorkOrderAssignee.work_order_id == work_order_id)
    ).scalars().all())


def team_ids(db: Session, work_order_id: str) -> list[str]:
    return list(db.execute(
        select(WorkOrderTeam.team_id).where(WorkOrderTeam.work_order_id == work_order_id)
    ).scalars().all())


def to_read(db: Session, wo: WorkOrder) -> dict:
    return {
        "id": wo.id, "custom_id": wo.custom_id, "title": wo.title,
        "description": wo.description, "status": wo.status, "priority": wo.priority,
        "due_date": wo.due_date, "asset_id": wo.asset_id, "location_id": wo.location_id,
        "primary_user_id": wo.primary_user_id, "procedure_id": wo.procedure_id,
        "procedure_group_id": wo.procedure_group_id, "completed_at": wo.completed_at,
        "assignee_ids": assignee_ids(db, wo.id), "team_ids": team_ids(db, wo.id),
    }


def _log(db: Session, work_order_id: str, company_id: str, activity_type: str,
         actor_user_id: str | None = None, from_status: str | None = None,
         to_status: str | None = None, comment: str = "") -> None:
    db.add(WorkOrderActivity(
        work_order_id=work_order_id, company_id=company_id, activity_type=activity_type,
        actor_user_id=actor_user_id, from_status=from_status, to_status=to_status, comment=comment,
    ))


def set_assignees(db: Session, wo: WorkOrder, user_ids: list[str], company_id: str) -> WorkOrder:
    db.execute(delete(WorkOrderAssignee).where(WorkOrderAssignee.work_order_id == wo.id))
    for uid in dict.fromkeys(user_ids):
        db.add(WorkOrderAssignee(work_order_id=wo.id, user_id=uid, company_id=company_id))
    db.commit()
    db.refresh(wo)
    return wo


def set_teams(db: Session, wo: WorkOrder, team_ids_: list[str], company_id: str) -> WorkOrder:
    db.execute(delete(WorkOrderTeam).where(WorkOrderTeam.work_order_id == wo.id))
    for tid in dict.fromkeys(team_ids_):
        db.add(WorkOrderTeam(work_order_id=wo.id, team_id=tid, company_id=company_id))
    db.commit()
    db.refresh(wo)
    return wo


def create_work_order(db: Session, payload: WorkOrderCreate, company_id: str,
                      actor_user_id: str | None) -> WorkOrder:
    seq = sequence_service.next_value(db, "work_order", company_id)
    wo = WorkOrder(
        custom_id=sequence_service.format_custom_id("WO", seq),
        title=payload.title, description=payload.description, priority=payload.priority,
        due_date=payload.due_date, asset_id=payload.asset_id, location_id=payload.location_id,
        primary_user_id=payload.primary_user_id, company_id=company_id,
    )
    db.add(wo)
    db.flush()
    for uid in dict.fromkeys(payload.assignee_ids):
        db.add(WorkOrderAssignee(work_order_id=wo.id, user_id=uid, company_id=company_id))
    for tid in dict.fromkeys(payload.team_ids):
        db.add(WorkOrderTeam(work_order_id=wo.id, team_id=tid, company_id=company_id))
    db.commit()
    db.refresh(wo)
    return wo


def list_work_orders(db: Session, *, status: str | None = None, priority: str | None = None,
                     asset_id: str | None = None, location_id: str | None = None,
                     assignee_id: str | None = None,
                     procedure_attached: bool | None = None) -> list[WorkOrder]:
    stmt = select(WorkOrder).where(WorkOrder.is_active.is_(True))
    if status is not None:
        stmt = stmt.where(WorkOrder.status == status)
    if priority is not None:
        stmt = stmt.where(WorkOrder.priority == priority)
    if asset_id is not None:
        stmt = stmt.where(WorkOrder.asset_id == asset_id)
    if location_id is not None:
        stmt = stmt.where(WorkOrder.location_id == location_id)
    if procedure_attached is not None:
        if procedure_attached:
            stmt = stmt.where(WorkOrder.procedure_id.is_not(None))
        else:
            stmt = stmt.where(WorkOrder.procedure_id.is_(None))
    if assignee_id is not None:
        sub = select(WorkOrderAssignee.work_order_id).where(
            WorkOrderAssignee.user_id == assignee_id)
        stmt = stmt.where(WorkOrder.id.in_(sub))
    return list(db.execute(stmt.order_by(WorkOrder.custom_id)).scalars().all())


def get_work_order(db: Session, work_order_id: str) -> WorkOrder | None:
    wo = db.get(WorkOrder, work_order_id)
    if wo is None or not wo.is_active:
        return None
    return wo


def update_work_order(db: Session, wo: WorkOrder, payload: WorkOrderUpdate) -> WorkOrder:
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(wo, k, v)
    db.commit()
    db.refresh(wo)
    return wo


def transition(db: Session, wo: WorkOrder, payload: WorkOrderTransition, company_id: str,
               actor_user_id: str | None) -> WorkOrder:
    src, dst = wo.status, payload.to_status
    if not can_transition(src, dst):
        raise bad_request("WORKORDER_BAD_TRANSITION", f"非法状态转移 {src.value}->{dst.value}")
    if dst == WorkOrderStatus.COMPLETE:
        from app.services import work_order_execution_service as exe
        exe.assert_completable(db, wo)
        wo.completed_at = utcnow()
    if src == WorkOrderStatus.COMPLETE and dst == WorkOrderStatus.IN_PROGRESS:
        wo.completed_at = None
    wo.status = dst
    _log(db, wo.id, company_id, "STATUS_CHANGE", actor_user_id=actor_user_id,
         from_status=src.value, to_status=dst.value, comment=payload.note)
    db.commit()
    db.refresh(wo)
    return wo


def delete_work_order(db: Session, wo: WorkOrder) -> None:
    wo.is_active = False
    wo.deleted_at = utcnow()
    db.commit()


def add_comment(db: Session, wo: WorkOrder, comment: str, company_id: str,
                actor_user_id: str | None) -> WorkOrderActivity:
    act = WorkOrderActivity(
        work_order_id=wo.id, company_id=company_id, activity_type="COMMENT",
        actor_user_id=actor_user_id, comment=comment,
    )
    db.add(act)
    db.commit()
    db.refresh(act)
    return act


def list_activities(db: Session, work_order_id: str) -> list[WorkOrderActivity]:
    return list(db.execute(
        select(WorkOrderActivity).where(WorkOrderActivity.work_order_id == work_order_id)
        .order_by(WorkOrderActivity.created_at, WorkOrderActivity.id)
    ).scalars().all())
```

- [ ] **Step 4: 运行确认通过**

> 注：`test_legal_transition_writes_activity` 等会触发 `transition`→COMPLETE 时 import `work_order_execution_service`（Task 6 才创建）。但本任务的转移测试只到 IN_PROGRESS / 非法 COMPLETE（非法在 import 之前就 `can_transition` 拒绝），唯一走到 COMPLETE 的是 `test_complete_sets_and_reopen_clears_completed_at`——它需要 `assert_completable`。**因此本任务 Step 4 先跑除该用例外的子集**，完整 COMPLETE 路径在 Task 6 完成后回归。

Run: `cd "/Users/yuming/Desktop/smart CMMS/SmartSOP/backend" && source .venv/bin/activate && python -m pytest tests/test_work_order_service.py -v -k "not complete_sets_and_reopen"`
Expected: PASS（除 reopen 用例）。

- [ ] **Step 5: 提交**

```bash
git -C "/Users/yuming/Desktop/smart CMMS/SmartSOP" add backend/app/services/work_order_service.py backend/tests/test_work_order_service.py
git -C "/Users/yuming/Desktop/smart CMMS/SmartSOP" commit -m "feat(workorder): work order service (CRUD/customId/assignees/transition/activity)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: SOP 执行服务（attach / detach / 执行视图 / 填 step / 完成校验）

**Files:**
- Create: `backend/app/services/work_order_execution_service.py`
- Test: `backend/tests/test_work_order_execution_service.py`

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_work_order_execution_service.py`:

```python
import pytest
from fastapi import HTTPException

from app import tenant
from app.models.company import Company
from app.models.node import ProcedureNode
from app.models.procedure import Procedure
from app.models.work_order_status import WorkOrderStatus
from app.schemas.work_order import (
    StepResultUpdate, WorkOrderCreate, WorkOrderTransition,
)
from app.services import work_order_execution_service as exe
from app.services import work_order_service as wos


def _company(db, slug):
    c = Company(name=slug, slug=slug)
    db.add(c)
    db.commit()
    return c


def _published_procedure(db, company_id, *, with_required=False):
    """建一个 PUBLISHED 程序：1 章节 + 2 步骤（第二步可带 required 字段）。"""
    p = Procedure(
        procedure_group_id="grp-1", folder_id="f1", code="SOP-1", name="换泵程序",
        version=1, level_of_use="reference", status="PUBLISHED", company_id=company_id,
    )
    db.add(p)
    db.flush()
    chapter = ProcedureNode(
        procedure_id=p.id, sort_order=0, heading_level=1, kind="node",
        body="准备阶段", code="C1", company_id=company_id,
    )
    step1 = ProcedureNode(
        procedure_id=p.id, sort_order=1, heading_level=None, kind="step",
        body="关闭阀门", code="S1", input_schema={}, company_id=company_id,
    )
    schema2 = {"required": ["torque"]} if with_required else {}
    step2 = ProcedureNode(
        procedure_id=p.id, sort_order=2, heading_level=None, kind="step",
        body="紧固螺栓", code="S2", input_schema=schema2, company_id=company_id,
    )
    db.add_all([chapter, step1, step2])
    db.commit()
    return p


def test_attach_generates_step_rows_only(db):
    c = _company(db, "acme")
    tenant.set_current_company_id(c.id)
    p = _published_procedure(db, c.id)
    wo = wos.create_work_order(db, WorkOrderCreate(title="t"), c.id, None)
    exe.attach_procedure(db, wo, p.id, c.id, actor_user_id=None)
    view = exe.execution_view(db, wo)
    assert view["procedure"]["code"] == "SOP-1"
    assert len(view["outline"]) == 3          # 章节 + 2 步骤都在 outline
    assert len(view["steps"]) == 2            # 仅 step 生成执行行
    assert {s["node_code"] for s in view["steps"]} == {"S1", "S2"}


def test_attach_requires_published(db):
    c = _company(db, "acme")
    tenant.set_current_company_id(c.id)
    p = _published_procedure(db, c.id)
    p.status = "DRAFT"
    db.commit()
    wo = wos.create_work_order(db, WorkOrderCreate(title="t"), c.id, None)
    with pytest.raises(HTTPException) as exc:
        exe.attach_procedure(db, wo, p.id, c.id, actor_user_id=None)
    assert exc.value.status_code == 400


def test_double_attach_conflict(db):
    c = _company(db, "acme")
    tenant.set_current_company_id(c.id)
    p = _published_procedure(db, c.id)
    wo = wos.create_work_order(db, WorkOrderCreate(title="t"), c.id, None)
    exe.attach_procedure(db, wo, p.id, c.id, None)
    with pytest.raises(HTTPException) as exc:
        exe.attach_procedure(db, wo, p.id, c.id, None)
    assert exc.value.status_code == 409


def test_fill_step_requires_in_progress(db):
    c = _company(db, "acme")
    tenant.set_current_company_id(c.id)
    p = _published_procedure(db, c.id)
    wo = wos.create_work_order(db, WorkOrderCreate(title="t"), c.id, None)
    exe.attach_procedure(db, wo, p.id, c.id, None)
    sr = exe.list_step_results(db, wo.id)[0]
    with pytest.raises(HTTPException) as exc:  # OPEN 不可填
        exe.update_step(db, wo, sr, StepResultUpdate(is_done=True), c.id, actor_user_id=None)
    assert exc.value.status_code == 400


def test_required_field_missing_blocks_done(db):
    c = _company(db, "acme")
    tenant.set_current_company_id(c.id)
    p = _published_procedure(db, c.id, with_required=True)
    wo = wos.create_work_order(db, WorkOrderCreate(title="t"), c.id, None)
    exe.attach_procedure(db, wo, p.id, c.id, None)
    wos.transition(db, wo, WorkOrderTransition(to_status=WorkOrderStatus.IN_PROGRESS), c.id, None)
    s2 = [s for s in exe.list_step_results(db, wo.id) if s.node_code == "S2"][0]
    with pytest.raises(HTTPException) as exc:  # 缺 torque
        exe.update_step(db, wo, s2, StepResultUpdate(is_done=True), c.id, actor_user_id=None)
    assert exc.value.status_code == 400
    # 填上后可完成
    exe.update_step(db, wo, s2, StepResultUpdate(response={"torque": 40}, is_done=True),
                    c.id, actor_user_id="u1")
    db.refresh(s2)
    assert s2.is_done is True and s2.done_by_user_id == "u1"


def test_complete_requires_all_steps_done(db):
    c = _company(db, "acme")
    tenant.set_current_company_id(c.id)
    p = _published_procedure(db, c.id)
    wo = wos.create_work_order(db, WorkOrderCreate(title="t"), c.id, None)
    exe.attach_procedure(db, wo, p.id, c.id, None)
    wos.transition(db, wo, WorkOrderTransition(to_status=WorkOrderStatus.IN_PROGRESS), c.id, None)
    with pytest.raises(HTTPException) as exc:  # 有未完成 step
        wos.transition(db, wo, WorkOrderTransition(to_status=WorkOrderStatus.COMPLETE), c.id, None)
    assert exc.value.status_code == 400
    for sr in exe.list_step_results(db, wo.id):
        exe.update_step(db, wo, sr, StepResultUpdate(is_done=True), c.id, actor_user_id=None)
    wos.transition(db, wo, WorkOrderTransition(to_status=WorkOrderStatus.COMPLETE), c.id, None)
    assert wo.status == WorkOrderStatus.COMPLETE


def test_no_sop_work_order_completes_freely(db):
    c = _company(db, "acme")
    tenant.set_current_company_id(c.id)
    wo = wos.create_work_order(db, WorkOrderCreate(title="t"), c.id, None)
    wos.transition(db, wo, WorkOrderTransition(to_status=WorkOrderStatus.IN_PROGRESS), c.id, None)
    wos.transition(db, wo, WorkOrderTransition(to_status=WorkOrderStatus.COMPLETE), c.id, None)
    assert wo.status == WorkOrderStatus.COMPLETE


def test_detach_removes_rows_and_blocked_after_complete(db):
    c = _company(db, "acme")
    tenant.set_current_company_id(c.id)
    p = _published_procedure(db, c.id)
    wo = wos.create_work_order(db, WorkOrderCreate(title="t"), c.id, None)
    exe.attach_procedure(db, wo, p.id, c.id, None)
    assert len(exe.list_step_results(db, wo.id)) == 2
    exe.detach_procedure(db, wo, c.id)
    assert exe.list_step_results(db, wo.id) == []
    assert wo.procedure_id is None
    # 完成态禁止 detach
    exe.attach_procedure(db, wo, p.id, c.id, None)
    wos.transition(db, wo, WorkOrderTransition(to_status=WorkOrderStatus.IN_PROGRESS), c.id, None)
    for sr in exe.list_step_results(db, wo.id):
        exe.update_step(db, wo, sr, StepResultUpdate(is_done=True), c.id, None)
    wos.transition(db, wo, WorkOrderTransition(to_status=WorkOrderStatus.COMPLETE), c.id, None)
    with pytest.raises(HTTPException) as exc:
        exe.detach_procedure(db, wo, c.id)
    assert exc.value.status_code == 400


def test_version_pinning_immutable(db):
    c = _company(db, "acme")
    tenant.set_current_company_id(c.id)
    p = _published_procedure(db, c.id)
    wo = wos.create_work_order(db, WorkOrderCreate(title="t"), c.id, None)
    exe.attach_procedure(db, wo, p.id, c.id, None)
    before = len(exe.execution_view(db, wo)["steps"])
    # 程序新增一个 step（模拟编辑/新版）
    db.add(ProcedureNode(procedure_id=p.id, sort_order=3, heading_level=None, kind="step",
                         body="新步骤", code="S3", input_schema={}, company_id=c.id))
    db.commit()
    after = len(exe.list_step_results(db, wo.id))
    assert after == before  # 已生成的执行行不变（钉定不可变）
```

- [ ] **Step 2: 运行确认失败**

Run: `cd "/Users/yuming/Desktop/smart CMMS/SmartSOP/backend" && source .venv/bin/activate && python -m pytest tests/test_work_order_execution_service.py -v`
Expected: FAIL（`ModuleNotFoundError`）。

- [ ] **Step 3: 实现**

Create `backend/app/services/work_order_execution_service.py`:

```python
"""SOP×工单执行服务：挂接已发布版本、生成执行行、执行视图、填 step、完成校验。

钉定即不可变：执行行用弱引用 node_id + 冗余 code/sort_order；input_schema 在
执行视图按需从钉定版本节点读取（版本不可变，安全）。
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.errors import bad_request, conflict, not_found
from app.models.base import utcnow
from app.models.node import ProcedureNode
from app.models.procedure import Procedure
from app.models.work_order import WorkOrder
from app.models.work_order_step_result import WorkOrderStepResult
from app.models.work_order_status import WorkOrderStatus
from app.schemas.work_order import StepResultUpdate
from app.services import work_order_service as wos


def list_step_results(db: Session, work_order_id: str) -> list[WorkOrderStepResult]:
    return list(db.execute(
        select(WorkOrderStepResult)
        .where(WorkOrderStepResult.work_order_id == work_order_id)
        .order_by(WorkOrderStepResult.node_sort_order, WorkOrderStepResult.id)
    ).scalars().all())


def get_step_result(db: Session, result_id: str) -> WorkOrderStepResult | None:
    return db.get(WorkOrderStepResult, result_id)


def _pinned_nodes(db: Session, procedure_id: str) -> list[ProcedureNode]:
    return list(db.execute(
        select(ProcedureNode)
        .where(ProcedureNode.procedure_id == procedure_id, ProcedureNode.is_active.is_(True))
        .order_by(ProcedureNode.sort_order, ProcedureNode.id)
    ).scalars().all())


def attach_procedure(db: Session, wo: WorkOrder, procedure_id: str, company_id: str,
                     actor_user_id: str | None) -> WorkOrder:
    if wo.procedure_id is not None:
        raise conflict("WORKORDER_PROCEDURE_ATTACHED", "工单已挂接 SOP，请先解绑")
    proc = db.get(Procedure, procedure_id)
    if proc is None or proc.company_id != company_id or not proc.is_active:
        raise not_found("PROCEDURE_NOT_FOUND", "程序不存在")
    if proc.status != "PUBLISHED":
        raise bad_request("PROCEDURE_NOT_PUBLISHED", "只能挂接已发布的程序")
    wo.procedure_id = proc.id
    wo.procedure_group_id = proc.procedure_group_id
    wo.procedure_attached_at = utcnow()
    for node in _pinned_nodes(db, proc.id):
        if node.kind != "step":
            continue
        db.add(WorkOrderStepResult(
            work_order_id=wo.id, node_id=node.id, node_code=node.code,
            node_sort_order=node.sort_order, response={}, company_id=company_id,
        ))
    wos._log(db, wo.id, company_id, "SOP_ATTACH", actor_user_id=actor_user_id)
    db.commit()
    db.refresh(wo)
    return wo


def detach_procedure(db: Session, wo: WorkOrder, company_id: str) -> WorkOrder:
    if wo.status == WorkOrderStatus.COMPLETE:
        raise bad_request("WORKORDER_COMPLETE_LOCKED", "已完成工单不可解绑 SOP")
    db.execute(delete(WorkOrderStepResult).where(WorkOrderStepResult.work_order_id == wo.id))
    wo.procedure_id = None
    wo.procedure_group_id = None
    wo.procedure_attached_at = None
    db.commit()
    db.refresh(wo)
    return wo


def execution_view(db: Session, wo: WorkOrder) -> dict[str, Any]:
    if wo.procedure_id is None:
        return {"procedure": None, "outline": [], "steps": []}
    proc = db.get(Procedure, wo.procedure_id)
    nodes = _pinned_nodes(db, wo.procedure_id)
    schema_by_id = {n.id: (n.input_schema or {}) for n in nodes}
    outline = [
        {"node_id": n.id, "heading_level": n.heading_level, "kind": n.kind,
         "body": n.body, "code": n.code, "sort_order": n.sort_order}
        for n in nodes
    ]
    steps = []
    for sr in list_step_results(db, wo.id):
        steps.append({
            "id": sr.id, "node_id": sr.node_id, "node_code": sr.node_code,
            "node_sort_order": sr.node_sort_order,
            "input_schema": schema_by_id.get(sr.node_id, {}),
            "response": sr.response or {}, "is_done": sr.is_done,
            "done_by_user_id": sr.done_by_user_id, "done_at": sr.done_at, "notes": sr.notes,
        })
    procedure = None
    if proc is not None:
        procedure = {"id": proc.id, "group_id": proc.procedure_group_id,
                     "code": proc.code, "name": proc.name, "version": proc.version}
    return {"procedure": procedure, "outline": outline, "steps": steps}


def _required_fields(db: Session, node_id: str) -> list[str]:
    node = db.get(ProcedureNode, node_id)
    if node is None:
        return []
    schema = node.input_schema or {}
    req = schema.get("required", [])
    return list(req) if isinstance(req, list) else []


def update_step(db: Session, wo: WorkOrder, sr: WorkOrderStepResult, payload: StepResultUpdate,
                company_id: str, actor_user_id: str | None) -> WorkOrderStepResult:
    if wo.status != WorkOrderStatus.IN_PROGRESS:
        raise bad_request("WORKORDER_NOT_IN_PROGRESS", "工单需处于执行中才能填写步骤")
    data = payload.model_dump(exclude_unset=True)
    if "response" in data and data["response"] is not None:
        sr.response = data["response"]
    if "notes" in data and data["notes"] is not None:
        sr.notes = data["notes"]
    if "is_done" in data and data["is_done"] is not None:
        if data["is_done"]:
            missing = [f for f in _required_fields(db, sr.node_id)
                       if not (sr.response or {}).get(f)]
            if missing:
                raise bad_request("STEP_REQUIRED_MISSING", "必填字段缺失", field=",".join(missing))
            sr.is_done = True
            sr.done_by_user_id = actor_user_id
            sr.done_at = utcnow()
            wos._log(db, wo.id, company_id, "STEP_DONE", actor_user_id=actor_user_id,
                     comment=sr.node_code)
        else:
            sr.is_done = False
            sr.done_by_user_id = None
            sr.done_at = None
    db.commit()
    db.refresh(sr)
    return sr


def assert_completable(db: Session, wo: WorkOrder) -> None:
    """转 COMPLETE 前置：若挂接 SOP，要求所有执行行已完成。"""
    if wo.procedure_id is None:
        return
    rows = list_step_results(db, wo.id)
    if any(not r.is_done for r in rows):
        raise bad_request("WORKORDER_STEPS_INCOMPLETE", "存在未完成的执行步骤")
```

- [ ] **Step 4: 运行确认通过（含 Task 5 的 reopen 用例回归）**

Run: `cd "/Users/yuming/Desktop/smart CMMS/SmartSOP/backend" && source .venv/bin/activate && python -m pytest tests/test_work_order_execution_service.py tests/test_work_order_service.py -v`
Expected: PASS（两文件全过——Task 5 的 reopen 用例此刻可过，因 `assert_completable` 已存在）。

- [ ] **Step 5: 提交**

```bash
git -C "/Users/yuming/Desktop/smart CMMS/SmartSOP" add backend/app/services/work_order_execution_service.py backend/tests/test_work_order_execution_service.py
git -C "/Users/yuming/Desktop/smart CMMS/SmartSOP" commit -m "feat(workorder): SOP execution service (attach/detach/view/step/completion)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: 工单路由（CRUD/转移/指派/活动 + SOP 执行子资源）+ 挂载

**Files:**
- Create: `backend/app/routers/work_orders.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_work_orders_api.py`

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_work_orders_api.py`:

```python
from app import tenant
from app.models.company import Company
from app.models.node import ProcedureNode
from app.models.procedure import Procedure


def _admin(client, company="Acme", email="admin@acme.com"):
    return client.post("/api/v1/auth/register", json={
        "company_name": company, "email": email,
        "password": "secret123", "name": "Admin"}).json()["access_token"]


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def _company_id(db, slug):
    return db.execute(
        Company.__table__.select().where(Company.slug == slug)
    ).first().id


def _seed_published_procedure(db, company_id):
    """直接经 db 预置 PUBLISHED 程序（client 与 db 共享同一引擎）。"""
    tenant.set_current_company_id(company_id)
    p = Procedure(procedure_group_id="g1", folder_id="f1", code="SOP-1", name="程序",
                  version=1, level_of_use="reference", status="PUBLISHED", company_id=company_id)
    db.add(p)
    db.flush()
    db.add(ProcedureNode(procedure_id=p.id, sort_order=0, heading_level=1, kind="node",
                         body="章", code="C1", company_id=company_id))
    db.add(ProcedureNode(procedure_id=p.id, sort_order=1, heading_level=None, kind="step",
                         body="步1", code="S1", input_schema={}, company_id=company_id))
    db.commit()
    tenant.set_current_company_id(None)
    return p.id


def test_create_list_custom_id(client):
    t = _admin(client)
    a = client.post("/api/v1/work-orders", headers=_h(t), json={"title": "换油"}).json()
    assert a["custom_id"] == "WO000001"
    assert a["status"] == "OPEN"
    titles = {x["title"] for x in client.get("/api/v1/work-orders", headers=_h(t)).json()}
    assert titles == {"换油"}


def test_transition_and_activities(client):
    t = _admin(client)
    wid = client.post("/api/v1/work-orders", headers=_h(t), json={"title": "t"}).json()["id"]
    r = client.post(f"/api/v1/work-orders/{wid}/transition", headers=_h(t),
                    json={"to_status": "IN_PROGRESS"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "IN_PROGRESS"
    # 非法转移
    bad = client.post(f"/api/v1/work-orders/{wid}/transition", headers=_h(t),
                      json={"to_status": "OPEN"})
    assert bad.status_code == 400
    acts = client.get(f"/api/v1/work-orders/{wid}/activities", headers=_h(t)).json()
    assert any(a["activity_type"] == "STATUS_CHANGE" for a in acts)


def test_assignees_and_comment(client):
    t = _admin(client)
    uid = client.post("/api/v1/users", headers=_h(t),
                      json={"email": "w@a.com", "password": "secret123", "name": "W"}).json()["id"]
    wid = client.post("/api/v1/work-orders", headers=_h(t), json={"title": "t"}).json()["id"]
    r = client.put(f"/api/v1/work-orders/{wid}/assignees", headers=_h(t), json={"user_ids": [uid]})
    assert set(r.json()["assignee_ids"]) == {uid}
    c = client.post(f"/api/v1/work-orders/{wid}/activities", headers=_h(t),
                    json={"comment": "备件已到"})
    assert c.status_code == 201, c.text


def test_update_and_delete(client):
    t = _admin(client)
    wid = client.post("/api/v1/work-orders", headers=_h(t), json={"title": "t"}).json()["id"]
    assert client.patch(f"/api/v1/work-orders/{wid}", headers=_h(t),
                        json={"priority": "HIGH"}).json()["priority"] == "HIGH"
    assert client.delete(f"/api/v1/work-orders/{wid}", headers=_h(t)).status_code == 204
    assert client.get("/api/v1/work-orders", headers=_h(t)).json() == []


def test_sop_attach_execute_complete(client, db):
    t = _admin(client)
    cid = _company_id(db, "acme")
    pid = _seed_published_procedure(db, cid)
    wid = client.post("/api/v1/work-orders", headers=_h(t), json={"title": "t"}).json()["id"]
    # 挂接
    r = client.post(f"/api/v1/work-orders/{wid}/attach-procedure", headers=_h(t),
                    json={"procedure_id": pid})
    assert r.status_code == 200, r.text
    view = client.get(f"/api/v1/work-orders/{wid}/execution", headers=_h(t)).json()
    assert view["procedure"]["code"] == "SOP-1"
    assert len(view["outline"]) == 2 and len(view["steps"]) == 1
    rid = view["steps"][0]["id"]
    # 未到 IN_PROGRESS 不能填
    assert client.patch(f"/api/v1/work-orders/{wid}/steps/{rid}", headers=_h(t),
                        json={"is_done": True}).status_code == 400
    client.post(f"/api/v1/work-orders/{wid}/transition", headers=_h(t),
                json={"to_status": "IN_PROGRESS"})
    # 有未完成 step 不能 COMPLETE
    assert client.post(f"/api/v1/work-orders/{wid}/transition", headers=_h(t),
                       json={"to_status": "COMPLETE"}).status_code == 400
    assert client.patch(f"/api/v1/work-orders/{wid}/steps/{rid}", headers=_h(t),
                        json={"is_done": True}).status_code == 200
    assert client.post(f"/api/v1/work-orders/{wid}/transition", headers=_h(t),
                       json={"to_status": "COMPLETE"}).json()["status"] == "COMPLETE"


def test_attach_only_published(client, db):
    t = _admin(client)
    cid = _company_id(db, "acme")
    pid = _seed_published_procedure(db, cid)
    # 改为 DRAFT
    tenant.set_current_company_id(cid)
    proc = db.get(Procedure, pid)
    proc.status = "DRAFT"
    db.commit()
    tenant.set_current_company_id(None)
    wid = client.post("/api/v1/work-orders", headers=_h(t), json={"title": "t"}).json()["id"]
    r = client.post(f"/api/v1/work-orders/{wid}/attach-procedure", headers=_h(t),
                    json={"procedure_id": pid})
    assert r.status_code == 400


def test_requires_auth(client):
    assert client.get("/api/v1/work-orders").status_code == 401


def test_cross_tenant_404(client):
    ta = _admin(client, "Acme", "a@acme.com")
    tb = _admin(client, "Globex", "b@globex.com")
    bid = client.post("/api/v1/work-orders", headers=_h(tb), json={"title": "B单"}).json()["id"]
    assert client.get(f"/api/v1/work-orders/{bid}", headers=_h(ta)).status_code == 404
    assert client.post(f"/api/v1/work-orders/{bid}/transition", headers=_h(ta),
                       json={"to_status": "IN_PROGRESS"}).status_code == 404


def test_technician_execute_not_delete(client, db):
    admin = _admin(client)
    cid = _company_id(db, "acme")
    pid = _seed_published_procedure(db, cid)
    client.post("/api/v1/users", headers=_h(admin),
                json={"email": "tech@acme.com", "password": "secret123", "name": "T"})
    roles = client.get("/api/v1/roles", headers=_h(admin)).json()
    tech_role = next(r for r in roles if r["code"] == "technician")["id"]
    uid = [u for u in client.get("/api/v1/users", headers=_h(admin)).json()
           if u["email"] == "tech@acme.com"][0]["id"]
    client.patch(f"/api/v1/users/{uid}", headers=_h(admin), json={"role_id": tech_role})
    tech = client.post("/api/v1/auth/login", json={
        "email": "tech@acme.com", "password": "secret123",
        "company_slug": "acme"}).json()["access_token"]
    wid = client.post("/api/v1/work-orders", headers=_h(admin), json={"title": "t"}).json()["id"]
    # technician 不能建单
    assert client.post("/api/v1/work-orders", headers=_h(tech),
                       json={"title": "x"}).status_code == 403
    # 能转状态（edit）
    assert client.post(f"/api/v1/work-orders/{wid}/transition", headers=_h(tech),
                       json={"to_status": "IN_PROGRESS"}).status_code == 200
    # 不能删
    assert client.delete(f"/api/v1/work-orders/{wid}", headers=_h(tech)).status_code == 403
```

- [ ] **Step 2: 运行确认失败**

Run: `cd "/Users/yuming/Desktop/smart CMMS/SmartSOP/backend" && source .venv/bin/activate && python -m pytest tests/test_work_orders_api.py -v`
Expected: FAIL（404，路由不存在）。

- [ ] **Step 3: 实现路由**

Create `backend/app/routers/work_orders.py`:

```python
"""工单 API（/api/v1/work-orders，含 SOP 执行子资源）。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import permissions
from app.deps import get_db, require_permission
from app.errors import not_found
from app.models.user import User
from app.models.work_order import WorkOrder
from app.models.work_order_step_result import WorkOrderStepResult
from app.schemas.work_order import (
    ActivityRead, AssigneesSet, AttachProcedure, CommentCreate, ExecutionView,
    StepResultUpdate, TeamsSet, WorkOrderCreate, WorkOrderRead, WorkOrderTransition,
    WorkOrderUpdate,
)
from app.services import work_order_execution_service as exe
from app.services import work_order_service as svc

router = APIRouter(prefix="/api/v1/work-orders", tags=["work-orders"])


def _ensure(wo: WorkOrder | None, company_id: str) -> WorkOrder:
    if wo is None or wo.company_id != company_id:
        raise not_found("WORKORDER_NOT_FOUND", "工单不存在")
    return wo


def _ensure_step(sr: WorkOrderStepResult | None, work_order_id: str,
                 company_id: str) -> WorkOrderStepResult:
    if sr is None or sr.work_order_id != work_order_id or sr.company_id != company_id:
        raise not_found("STEP_RESULT_NOT_FOUND", "执行步骤不存在")
    return sr


@router.get("", response_model=list[WorkOrderRead])
def list_work_orders(status: str | None = None, priority: str | None = None,
                     asset_id: str | None = None, location_id: str | None = None,
                     assignee_id: str | None = None, procedure_attached: bool | None = None,
                     db: Session = Depends(get_db),
                     current_user: User = Depends(require_permission(permissions.WORK_ORDER_VIEW))):
    rows = svc.list_work_orders(
        db, status=status, priority=priority, asset_id=asset_id, location_id=location_id,
        assignee_id=assignee_id, procedure_attached=procedure_attached)
    return [svc.to_read(db, w) for w in rows]


@router.post("", response_model=WorkOrderRead, status_code=201)
def create_work_order(payload: WorkOrderCreate, db: Session = Depends(get_db),
                      current_user: User = Depends(require_permission(permissions.WORK_ORDER_CREATE))):
    wo = svc.create_work_order(db, payload, current_user.company_id, actor_user_id=current_user.id)
    if payload.procedure_id is not None:
        exe.attach_procedure(db, wo, payload.procedure_id, current_user.company_id,
                             actor_user_id=current_user.id)
    return svc.to_read(db, wo)


@router.get("/{work_order_id}", response_model=WorkOrderRead)
def get_work_order(work_order_id: str, db: Session = Depends(get_db),
                   current_user: User = Depends(require_permission(permissions.WORK_ORDER_VIEW))):
    wo = _ensure(svc.get_work_order(db, work_order_id), current_user.company_id)
    return svc.to_read(db, wo)


@router.patch("/{work_order_id}", response_model=WorkOrderRead)
def update_work_order(work_order_id: str, payload: WorkOrderUpdate, db: Session = Depends(get_db),
                      current_user: User = Depends(require_permission(permissions.WORK_ORDER_EDIT))):
    wo = _ensure(svc.get_work_order(db, work_order_id), current_user.company_id)
    wo = svc.update_work_order(db, wo, payload)
    return svc.to_read(db, wo)


@router.delete("/{work_order_id}", status_code=204)
def delete_work_order(work_order_id: str, db: Session = Depends(get_db),
                      current_user: User = Depends(require_permission(permissions.WORK_ORDER_DELETE))):
    wo = _ensure(svc.get_work_order(db, work_order_id), current_user.company_id)
    svc.delete_work_order(db, wo)


@router.put("/{work_order_id}/assignees", response_model=WorkOrderRead)
def set_assignees(work_order_id: str, payload: AssigneesSet, db: Session = Depends(get_db),
                  current_user: User = Depends(require_permission(permissions.WORK_ORDER_EDIT))):
    wo = _ensure(svc.get_work_order(db, work_order_id), current_user.company_id)
    wo = svc.set_assignees(db, wo, payload.user_ids, current_user.company_id)
    return svc.to_read(db, wo)


@router.put("/{work_order_id}/teams", response_model=WorkOrderRead)
def set_teams(work_order_id: str, payload: TeamsSet, db: Session = Depends(get_db),
              current_user: User = Depends(require_permission(permissions.WORK_ORDER_EDIT))):
    wo = _ensure(svc.get_work_order(db, work_order_id), current_user.company_id)
    wo = svc.set_teams(db, wo, payload.team_ids, current_user.company_id)
    return svc.to_read(db, wo)


@router.post("/{work_order_id}/transition", response_model=WorkOrderRead)
def transition(work_order_id: str, payload: WorkOrderTransition, db: Session = Depends(get_db),
               current_user: User = Depends(require_permission(permissions.WORK_ORDER_EDIT))):
    wo = _ensure(svc.get_work_order(db, work_order_id), current_user.company_id)
    wo = svc.transition(db, wo, payload, current_user.company_id, actor_user_id=current_user.id)
    return svc.to_read(db, wo)


@router.post("/{work_order_id}/attach-procedure", response_model=WorkOrderRead)
def attach_procedure(work_order_id: str, payload: AttachProcedure, db: Session = Depends(get_db),
                     current_user: User = Depends(require_permission(permissions.WORK_ORDER_EDIT))):
    wo = _ensure(svc.get_work_order(db, work_order_id), current_user.company_id)
    wo = exe.attach_procedure(db, wo, payload.procedure_id, current_user.company_id,
                              actor_user_id=current_user.id)
    return svc.to_read(db, wo)


@router.delete("/{work_order_id}/procedure", response_model=WorkOrderRead)
def detach_procedure(work_order_id: str, db: Session = Depends(get_db),
                     current_user: User = Depends(require_permission(permissions.WORK_ORDER_EDIT))):
    wo = _ensure(svc.get_work_order(db, work_order_id), current_user.company_id)
    wo = exe.detach_procedure(db, wo, current_user.company_id)
    return svc.to_read(db, wo)


@router.get("/{work_order_id}/execution", response_model=ExecutionView)
def execution_view(work_order_id: str, db: Session = Depends(get_db),
                   current_user: User = Depends(require_permission(permissions.WORK_ORDER_VIEW))):
    wo = _ensure(svc.get_work_order(db, work_order_id), current_user.company_id)
    return exe.execution_view(db, wo)


@router.patch("/{work_order_id}/steps/{result_id}", response_model=ExecutionView)
def update_step(work_order_id: str, result_id: str, payload: StepResultUpdate,
                db: Session = Depends(get_db),
                current_user: User = Depends(require_permission(permissions.WORK_ORDER_EXECUTE))):
    wo = _ensure(svc.get_work_order(db, work_order_id), current_user.company_id)
    sr = _ensure_step(exe.get_step_result(db, result_id), work_order_id, current_user.company_id)
    exe.update_step(db, wo, sr, payload, current_user.company_id, actor_user_id=current_user.id)
    return exe.execution_view(db, wo)


@router.get("/{work_order_id}/activities", response_model=list[ActivityRead])
def list_activities(work_order_id: str, db: Session = Depends(get_db),
                    current_user: User = Depends(require_permission(permissions.WORK_ORDER_VIEW))):
    _ensure(svc.get_work_order(db, work_order_id), current_user.company_id)
    return svc.list_activities(db, work_order_id)


@router.post("/{work_order_id}/activities", response_model=ActivityRead, status_code=201)
def add_comment(work_order_id: str, payload: CommentCreate, db: Session = Depends(get_db),
                current_user: User = Depends(require_permission(permissions.WORK_ORDER_VIEW))):
    wo = _ensure(svc.get_work_order(db, work_order_id), current_user.company_id)
    return svc.add_comment(db, wo, payload.comment, current_user.company_id,
                           actor_user_id=current_user.id)
```

> 路由顺序：所有静态子路径都在 `/{work_order_id}/...` 之下，无与 `/{work_order_id}` 裸段冲突，FastAPI 可正确匹配；`update_step` 的 `/steps/{result_id}` 是双段，更不冲突。

- [ ] **Step 4: 挂载路由**

Edit `backend/app/main.py`。把括号导入块中的 `teams,` 之前/之后按字母序加入 `work_orders,`。当前块：

```python
from app.routers import (
    asset_categories,
    assets,
    attachments,
    audit_logs,
    fields,
    folders,
    locations,
    nodes,
    parse,
    procedure_groups,
    procedures,
    teams,
)
```

替换为（在 `teams,` 后加 `work_orders,`）：

```python
from app.routers import (
    asset_categories,
    assets,
    attachments,
    audit_logs,
    fields,
    folders,
    locations,
    nodes,
    parse,
    procedure_groups,
    procedures,
    teams,
    work_orders,
)
```

并在 include 区（`app.include_router(teams.router)` 之后）加一行：

```python
app.include_router(work_orders.router)
```

改完执行 `python -c "import app.main"` 确认可导入。

- [ ] **Step 5: 运行确认通过**

Run: `cd "/Users/yuming/Desktop/smart CMMS/SmartSOP/backend" && source .venv/bin/activate && python -m pytest tests/test_work_orders_api.py -v`
Expected: PASS。

- [ ] **Step 6: 全量回归 + 提交**

Run: `cd "/Users/yuming/Desktop/smart CMMS/SmartSOP/backend" && source .venv/bin/activate && python -m pytest -q`
Expected: 全部 PASS。

```bash
git -C "/Users/yuming/Desktop/smart CMMS/SmartSOP" add backend/app/routers/work_orders.py backend/app/main.py backend/tests/test_work_orders_api.py
git -C "/Users/yuming/Desktop/smart CMMS/SmartSOP" commit -m "feat(workorder): work order API + SOP execution endpoints (/api/v1/work-orders)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: Alembic 迁移 + 重建 dev.db

本期所有表均为新建（`create_table`），无需 dialect 分支。

**Files:**
- Create: `backend/alembic/versions/20260530_0003_phase1b_workorder_loop.py`

- [ ] **Step 1: 确认模型已入 metadata**

Run: `cd "/Users/yuming/Desktop/smart CMMS/SmartSOP/backend" && source .venv/bin/activate && python -c "import app.models; from app.models.base import Base; need={'tb_work_order','tb_work_order_assignee','tb_work_order_team','tb_work_order_step_result','tb_work_order_activity'}; have=set(Base.metadata.tables); print('ALL_IN', need<=have); print('MISSING', need-have)"`
Expected: `ALL_IN True`，`MISSING set()`。

- [ ] **Step 2: 写迁移**

Create `backend/alembic/versions/20260530_0003_phase1b_workorder_loop.py`:

```python
"""phase1b workorder loop: work_order(+assignee/team), step_result, activity

Revision ID: phase1b_workorder_loop
Revises: phase1a_base_domain
Create Date: 2026-05-30

Hand-authored (MySQL prod + SQLite dev/test). All new tables -> create_table
works on both dialects, no dialect branching needed.
"""
from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

from app.models.base import DATETIME6

revision: str = "phase1b_workorder_loop"
down_revision: str | Sequence[str] | None = "phase1a_base_domain"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _ts() -> list[sa.Column]:
    return [
        sa.Column("created_at", DATETIME6, nullable=False),
        sa.Column("updated_at", DATETIME6, nullable=False),
    ]


def _soft() -> list[sa.Column]:
    return [
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", DATETIME6, nullable=True),
    ]


def _company_fk() -> sa.Column:
    return sa.Column(
        "company_id", sa.String(36),
        sa.ForeignKey("tb_company.id", ondelete="CASCADE"), nullable=False,
    )


def upgrade() -> None:
    op.create_table(
        "tb_work_order",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        sa.Column("custom_id", sa.String(20), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("status",
                  sa.Enum("OPEN", "IN_PROGRESS", "ON_HOLD", "COMPLETE", "CANCELED",
                          name="workorderstatus"),
                  nullable=False),
        sa.Column("priority",
                  sa.Enum("NONE", "LOW", "MEDIUM", "HIGH", name="workorderpriority"),
                  nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("asset_id", sa.String(36),
                  sa.ForeignKey("tb_asset.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("location_id", sa.String(36),
                  sa.ForeignKey("tb_location.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("primary_user_id", sa.String(36),
                  sa.ForeignKey("tb_user.id", ondelete="SET NULL"), nullable=True),
        sa.Column("procedure_id", sa.String(36), nullable=True),
        sa.Column("procedure_group_id", sa.String(36), nullable=True),
        sa.Column("procedure_attached_at", DATETIME6, nullable=True),
        sa.Column("completed_at", DATETIME6, nullable=True),
        *_ts(), *_soft(),
    )
    op.create_index("ix_tb_work_order_company_id", "tb_work_order", ["company_id"])
    op.create_index("ix_tb_work_order_asset_id", "tb_work_order", ["asset_id"])
    op.create_index("ix_tb_work_order_location_id", "tb_work_order", ["location_id"])
    op.create_index("ix_tb_work_order_primary_user_id", "tb_work_order", ["primary_user_id"])
    op.create_index("ix_tb_work_order_procedure_id", "tb_work_order", ["procedure_id"])
    op.create_index("ix_tb_work_order_is_active", "tb_work_order", ["is_active"])

    op.create_table(
        "tb_work_order_assignee",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        sa.Column("work_order_id", sa.String(36),
                  sa.ForeignKey("tb_work_order.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(36),
                  sa.ForeignKey("tb_user.id", ondelete="CASCADE"), nullable=False),
        *_ts(),
        sa.UniqueConstraint("work_order_id", "user_id", name="uq_work_order_assignee"),
    )
    op.create_index("ix_tb_work_order_assignee_company_id", "tb_work_order_assignee", ["company_id"])
    op.create_index("ix_tb_work_order_assignee_work_order_id", "tb_work_order_assignee", ["work_order_id"])
    op.create_index("ix_tb_work_order_assignee_user_id", "tb_work_order_assignee", ["user_id"])

    op.create_table(
        "tb_work_order_team",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        sa.Column("work_order_id", sa.String(36),
                  sa.ForeignKey("tb_work_order.id", ondelete="CASCADE"), nullable=False),
        sa.Column("team_id", sa.String(36),
                  sa.ForeignKey("tb_team.id", ondelete="CASCADE"), nullable=False),
        *_ts(),
        sa.UniqueConstraint("work_order_id", "team_id", name="uq_work_order_team"),
    )
    op.create_index("ix_tb_work_order_team_company_id", "tb_work_order_team", ["company_id"])
    op.create_index("ix_tb_work_order_team_work_order_id", "tb_work_order_team", ["work_order_id"])
    op.create_index("ix_tb_work_order_team_team_id", "tb_work_order_team", ["team_id"])

    op.create_table(
        "tb_work_order_step_result",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        sa.Column("work_order_id", sa.String(36),
                  sa.ForeignKey("tb_work_order.id", ondelete="CASCADE"), nullable=False),
        sa.Column("node_id", sa.String(36), nullable=False),
        sa.Column("node_code", sa.String(50), nullable=False, server_default=""),
        sa.Column("node_sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("response", sa.JSON(), nullable=True),
        sa.Column("is_done", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("done_by_user_id", sa.String(36), nullable=True),
        sa.Column("done_at", DATETIME6, nullable=True),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        *_ts(),
    )
    op.create_index("ix_tb_work_order_step_result_company_id", "tb_work_order_step_result", ["company_id"])
    op.create_index("ix_tb_work_order_step_result_work_order_id", "tb_work_order_step_result", ["work_order_id"])
    op.create_index("ix_tb_work_order_step_result_node_id", "tb_work_order_step_result", ["node_id"])

    op.create_table(
        "tb_work_order_activity",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        sa.Column("work_order_id", sa.String(36),
                  sa.ForeignKey("tb_work_order.id", ondelete="CASCADE"), nullable=False),
        sa.Column("activity_type", sa.String(20), nullable=False),
        sa.Column("actor_user_id", sa.String(36), nullable=True),
        sa.Column("from_status", sa.String(20), nullable=True),
        sa.Column("to_status", sa.String(20), nullable=True),
        sa.Column("comment", sa.Text(), nullable=False, server_default=""),
        *_ts(),
    )
    op.create_index("ix_tb_work_order_activity_company_id", "tb_work_order_activity", ["company_id"])
    op.create_index("ix_tb_work_order_activity_work_order_id", "tb_work_order_activity", ["work_order_id"])


def downgrade() -> None:
    for tbl in (
        "tb_work_order_activity", "tb_work_order_step_result",
        "tb_work_order_team", "tb_work_order_assignee", "tb_work_order",
    ):
        op.drop_table(tbl)
```

- [ ] **Step 3: 单 head + 全链 upgrade（SQLite）**

Run: `cd "/Users/yuming/Desktop/smart CMMS/SmartSOP/backend" && source .venv/bin/activate && python -c "from alembic.config import Config;from alembic.script import ScriptDirectory;print(ScriptDirectory.from_config(Config('alembic.ini')).get_heads())"`
Expected: `('phase1b_workorder_loop',)`（单 head）。

Run: `cd "/Users/yuming/Desktop/smart CMMS/SmartSOP/backend" && source .venv/bin/activate && rm -f /tmp/p1b.db && DATABASE_URL="sqlite:////tmp/p1b.db" alembic upgrade head`
Expected: 无错误，升到 `phase1b_workorder_loop`。

- [ ] **Step 4: downgrade -1 / upgrade head 往返**

Run: `cd "/Users/yuming/Desktop/smart CMMS/SmartSOP/backend" && source .venv/bin/activate && DATABASE_URL="sqlite:////tmp/p1b.db" alembic downgrade -1 && DATABASE_URL="sqlite:////tmp/p1b.db" alembic upgrade head`
Expected: 均成功（downgrade 回到 `phase1a_base_domain`，再升回 `phase1b_workorder_loop`）。

- [ ] **Step 5: 重建 dev.db**

Run: `cd "/Users/yuming/Desktop/smart CMMS/SmartSOP/backend" && source .venv/bin/activate && rm -f dev.db && alembic upgrade head`
Run: `cd "/Users/yuming/Desktop/smart CMMS/SmartSOP/backend" && source .venv/bin/activate && python -c "import sqlite3;c=sqlite3.connect('dev.db');t=set(r[0] for r in c.execute('SELECT name FROM sqlite_master WHERE type=\"table\"'));print('phase1b_ok', all(x in t for x in ('tb_work_order','tb_work_order_step_result','tb_work_order_activity')));print('ver', c.execute('SELECT version_num FROM alembic_version').fetchone()[0])"`
Expected: `phase1b_ok True` 且 `ver phase1b_workorder_loop`。

- [ ] **Step 6: 提交**

```bash
git -C "/Users/yuming/Desktop/smart CMMS/SmartSOP" add backend/alembic/versions/20260530_0003_phase1b_workorder_loop.py backend/dev.db
git -C "/Users/yuming/Desktop/smart CMMS/SmartSOP" commit -m "build(db): Alembic migration for Phase 1B work order tables + rebuild dev.db

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

> 若 `git add backend/dev.db` 报 `pathspec did not match`（dev.db 被 gitignore），跳过它，只 add 迁移文件。

---

## Task 9: 跨租户隔离端到端验收 + 全量回归

**Files:**
- Test: `backend/tests/test_phase1b_cross_tenant_e2e.py`

- [ ] **Step 1: 写测试**

Create `backend/tests/test_phase1b_cross_tenant_e2e.py`:

```python
from app import tenant
from app.models.company import Company
from app.models.node import ProcedureNode
from app.models.procedure import Procedure


def _register(client, company, email):
    r = client.post("/api/v1/auth/register", json={
        "company_name": company, "email": email, "password": "secret123", "name": "Admin"})
    assert r.status_code == 201, r.text
    return r.json()["access_token"]


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def _company_id(db, slug):
    return db.execute(Company.__table__.select().where(Company.slug == slug)).first().id


def test_work_orders_isolated(client):
    ta = _register(client, "Acme", "a@acme.com")
    tb = _register(client, "Globex", "b@globex.com")
    client.post("/api/v1/work-orders", headers=_h(ta), json={"title": "A单"})
    bid = client.post("/api/v1/work-orders", headers=_h(tb), json={"title": "B单"}).json()["id"]
    a_titles = {x["title"] for x in client.get("/api/v1/work-orders", headers=_h(ta)).json()}
    assert a_titles == {"A单"}
    assert client.get(f"/api/v1/work-orders/{bid}", headers=_h(ta)).status_code == 404
    assert client.patch(f"/api/v1/work-orders/{bid}", headers=_h(ta),
                        json={"title": "hack"}).status_code == 404
    assert client.delete(f"/api/v1/work-orders/{bid}", headers=_h(ta)).status_code == 404
    assert client.post(f"/api/v1/work-orders/{bid}/transition", headers=_h(ta),
                       json={"to_status": "IN_PROGRESS"}).status_code == 404


def test_custom_id_per_tenant_independent(client):
    ta = _register(client, "Acme", "a@acme.com")
    tb = _register(client, "Globex", "b@globex.com")
    a1 = client.post("/api/v1/work-orders", headers=_h(ta), json={"title": "x"}).json()["custom_id"]
    b1 = client.post("/api/v1/work-orders", headers=_h(tb), json={"title": "y"}).json()["custom_id"]
    assert a1 == "WO000001" and b1 == "WO000001"


def test_cross_tenant_cannot_attach_others_procedure(client, db):
    ta = _register(client, "Acme", "a@acme.com")
    _register(client, "Globex", "b@globex.com")
    # B 租户的程序
    bcid = _company_id(db, "globex")
    tenant.set_current_company_id(bcid)
    p = Procedure(procedure_group_id="g1", folder_id="f1", code="SOP-B", name="B程序",
                  version=1, level_of_use="reference", status="PUBLISHED", company_id=bcid)
    db.add(p); db.flush()
    db.add(ProcedureNode(procedure_id=p.id, sort_order=0, heading_level=None, kind="step",
                         body="s", code="S1", input_schema={}, company_id=bcid))
    db.commit()
    tenant.set_current_company_id(None)
    # A 租户建单并尝试挂 B 的程序 -> 404（跨租户读不可见）
    wid = client.post("/api/v1/work-orders", headers=_h(ta), json={"title": "t"}).json()["id"]
    r = client.post(f"/api/v1/work-orders/{wid}/attach-procedure", headers=_h(ta),
                    json={"procedure_id": p.id})
    assert r.status_code == 404
```

- [ ] **Step 2: 运行确认通过**

Run: `cd "/Users/yuming/Desktop/smart CMMS/SmartSOP/backend" && source .venv/bin/activate && python -m pytest tests/test_phase1b_cross_tenant_e2e.py -v`
Expected: PASS。若跨租户访问未被拦截，回 Task 5/6/7 检查 `_ensure*` 与 `attach_procedure` 的 `proc.company_id != company_id` 守卫。

- [ ] **Step 3: 净室合规检查**

Run: `cd "/Users/yuming/Desktop/smart CMMS/SmartSOP/backend" && source .venv/bin/activate && grep -rin "atlas" app/services/work_order_service.py app/services/work_order_execution_service.py app/routers/work_orders.py app/models/work_order*.py | wc -l`
Expected: `0`。

- [ ] **Step 4: 全量回归**

Run: `cd "/Users/yuming/Desktop/smart CMMS/SmartSOP/backend" && source .venv/bin/activate && python -m pytest -q`
Expected: 全部 PASS（Phase 0 + 1A + 1B + SOP）。

- [ ] **Step 5: 提交**

```bash
git -C "/Users/yuming/Desktop/smart CMMS/SmartSOP" add backend/tests/test_phase1b_cross_tenant_e2e.py
git -C "/Users/yuming/Desktop/smart CMMS/SmartSOP" commit -m "test(phase1b): cross-tenant isolation e2e acceptance

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## 验收清单（对照 spec §1.1 范围）

- [ ] WorkOrder CRUD + 软删 + customId(WO%06d)（Task 3/5/7）
- [ ] 状态机 5 态 + 合法转移守卫 + 专用 transition 端点（Task 2/5/7）
- [ ] 绑定 asset/location + primary_user + assignedTo 多人 + team（Task 3/5/7）
- [ ] SOP 挂接（仅 PUBLISHED 版本，弱引用钉定不可变）（Task 6/7）
- [ ] 仅 step 节点生成执行行 + 执行视图（outline 全节点 / steps 叠加响应）（Task 6/7）
- [ ] 填 step + required 字段校验 + done 盖章（Task 6/7）
- [ ] 完成校验（挂 SOP 须全 step done；未挂可直接完成）（Task 6/7）
- [ ] detach 仅非 COMPLETE，删执行行（Task 6/7）
- [ ] 活动时间线（STATUS_CHANGE/SOP_ATTACH/STEP_DONE 自动 + COMMENT 用户）（Task 5/6/7）
- [ ] RBAC work_order.*（execute 独立；technician view+execute+edit 非 delete）（Task 1/7）
- [ ] Alembic 迁移（SQLite up/down/up + 重建 dev.db）（Task 8）
- [ ] 跨租户隔离端到端（Task 9）
- [ ] 明确不做项保持未做：工时/成本/文件、Request、PM/仪表、工单 PDF、前端 UI

## 净室合规复核（实现完成后）

- [ ] 全部模型/代码原创，未参照 Atlas DDL/源码。
- [ ] 代码与产物中无 "Atlas" 字样、商标、文案、资源。
- [ ] `Task/TaskBase` 扁平清单未复刻——由 SOP 执行取代。
- [ ] 工单状态机、指派、执行记录、时间线为通用 CMMS/工作流领域模式，非受版权保护的具体表达。
