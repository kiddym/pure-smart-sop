# Phase 5A 站内通知（In-app Notifications）实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在已完成的 Phase 0–4 之上提供后端**站内通知**：领域事件（工单指派/状态、自动建单、请求/PO 审批）内联生成 + 到期提醒/低库存调度 tick（边沿去重），配 `/api/v1/notifications` feed/未读数/标记已读 API。

**Architecture:** 附加式观察者。新增 `app/models/notification.py`（2 表）+ `app/services/notification_service.py`（生成/接收人解析/边沿原语）+ `app/schemas/notification.py` + `app/routers/notifications.py` + `app/tasks/due_reminder.py`。在既有 service 的事件点、各自 `db.commit()` **之前**追加 `notify(...)` 调用以保证原子。调度 tick 仿 `pm_generate` 跨租户。**接收人按权限解析**（复用 `permissions.effective_codes`），**自抑制触发者本人**。

**Tech Stack:** FastAPI · SQLAlchemy 2.0 (sync) · Pydantic v2 · SQLite(测试)/MySQL(生产) · APScheduler · pytest。

**全局约定（每个 task 都遵守）：**
- 跑 python/pytest 前：`cd "/Users/yuming/Desktop/smart CMMS/SmartSOP/backend" && source .venv/bin/activate`
- 跑测试前清缓存：`find . -name __pycache__ -type d -exec rm -rf {} + ; rm -rf .pytest_cache` 且加 `PYTHONDONTWRITEBYTECODE=1`
- 共享文件（`main.py`/`scheduler.py`/`config.py`/既有 service）一律用 Edit 精确替换，禁 sed/re.sub；插入前先 Read 定位真实锚点。
- 提交 message 末行：`Co-Authored-By: Claude Opus 4.5 (1M context) <noreply@anthropic.com>`（注意是 "Claude Opus 4.5"，不是 4.8）。
- **只精确 `git add` 本 task 涉及的文件，禁 `git add .` / `git add -A`**（工作树可能有其他会话游离改动）。每次 commit 前 `git diff --cached --name-only` 确认仅本 task 文件；有非本期文件先 `git restore --staged`。
- 复用既有签名：`bad_request(code,msg)`（`app.errors`）；`app.deps.get_db`、`get_current_user`、`require_permission`；`app.models.base.utcnow`/`new_uuid`/`DATETIME6`；`app.permissions.effective_codes`。
- **基线（开工前已实测，勿照搬旧数字）**：全量 pytest **1040 passed**；alembic 单 head **`po_line_no`**。本期**新增 2 表 + 1 迁移**，迁移后 head 推进为 `phase5a_notification`。
- 设计依据：`docs/superpowers/specs/2026-05-31-phase-5a-notifications-design.md`。

**测试数据策略：**
- **单测**（service/model 层）用 `db` fixture 直插 ORM 行，统一 `company_id="co-1"`（无租户中间件→租户事件 no-op→service 见全部种子行）；时间字段显式传。SQLite 默认 FK 关闭，无需建 `tb_company`/`tb_user` 真实行即可用任意 id 字符串。
- **API 测**用 `client` + `db`（共享同一 in-memory engine，StaticPool）。先 `POST /api/v1/auth/register` 取 token，再用 `db` 按该公司 `company_id` 直插种子行（显式设 `company_id`）；公司 id 经 `select(Company).where(Company.slug==...)` 取（与 Phase 4 analytics API 测同构）。

---

## Task 1: config — notify_due_soon_days 设置项

**Files:**
- Modify: `backend/app/config.py`
- Test: `backend/tests/unit/test_config_notify.py`

- [ ] **Step 1: 写失败测试** `backend/tests/unit/test_config_notify.py`:
```python
from app.config import settings


def test_notify_due_soon_days_default():
    assert settings.notify_due_soon_days == 3


def test_notify_due_soon_days_is_int():
    assert isinstance(settings.notify_due_soon_days, int)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/test_config_notify.py -q`
Expected: FAIL（AttributeError: notify_due_soon_days）

- [ ] **Step 3: 改 `app/config.py`**

先 Read 文件，找到 `temp_upload_ttl_hours: int = 24` 行（约 51 行）。在其后插入一行：
```python
    notify_due_soon_days: int = 3  # 工单到期提醒提前天数（Phase 5A）
```

- [ ] **Step 4: 跑测试确认通过**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/test_config_notify.py -q`
Expected: PASS（2 passed）

- [ ] **Step 5: 提交**
```bash
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP" && git add backend/app/config.py backend/tests/unit/test_config_notify.py
git diff --cached --name-only
git commit -m "$(printf 'feat(phase-5a): add notify_due_soon_days setting\n\nCo-Authored-By: Claude Opus 4.5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 2: ORM 模型 — Notification + NotificationArm

**Files:**
- Create: `backend/app/models/notification.py`
- Test: `backend/tests/unit/test_notification_model.py`

- [ ] **Step 1: 写失败测试** `backend/tests/unit/test_notification_model.py`:
```python
from sqlalchemy.orm import Session

from app.models.notification import Notification, NotificationArm


def test_notification_defaults(db: Session):
    n = Notification(
        company_id="co-1", recipient_user_id="u-1", type="WO_ASSIGNED",
        entity_type="work_order", entity_id="wo-1", params='{"custom_id": "WO1"}',
    )
    db.add(n)
    db.commit()
    db.refresh(n)
    assert n.id and n.created_at is not None
    assert n.is_read is False and n.read_at is None
    assert n.actor_user_id is None and n.dedup_key is None


def test_notification_arm_unique(db: Session):
    db.add(NotificationArm(company_id="co-1", key="PART_LOW_STOCK:p-1"))
    db.commit()
    a = db.get(NotificationArm, db.query(NotificationArm).one().id)
    assert a.key == "PART_LOW_STOCK:p-1" and a.company_id == "co-1"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/test_notification_model.py -q`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 写实现** `backend/app/models/notification.py`:
```python
"""站内通知模型（Phase 5A）：通知行 + 边沿状态行。append-only，无软删。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    Base,
    DATETIME6,
    TenantMixin,
    TimestampMixin,
    UUIDMixin,
)


class Notification(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """单收件人一行；广播事件=每收件人一行。结构化 params 存 JSON 字符串。"""

    __tablename__ = "tb_notification"
    __table_args__ = (
        Index("ix_tb_notification_recipient_read", "company_id", "recipient_user_id", "is_read"),
        Index("ix_tb_notification_dedup", "company_id", "dedup_key"),
    )

    recipient_user_id: Mapped[str] = mapped_column(String(36), index=True)
    type: Mapped[str] = mapped_column(String(40))
    entity_type: Mapped[str | None] = mapped_column(String(40), default=None)
    entity_id: Mapped[str | None] = mapped_column(String(36), default=None)
    params: Mapped[str] = mapped_column(Text, default="{}", server_default="{}")
    actor_user_id: Mapped[str | None] = mapped_column(String(36), default=None)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", index=True)
    read_at: Mapped[datetime | None] = mapped_column(DATETIME6, default=None)
    dedup_key: Mapped[str | None] = mapped_column(String(120), default=None)


class NotificationArm(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """边沿状态：记录当前"已武装"的轮询条件（仿 meter is_armed）。"""

    __tablename__ = "tb_notification_arm"
    __table_args__ = (
        UniqueConstraint("company_id", "key", name="uq_notification_arm"),
    )

    key: Mapped[str] = mapped_column(String(120))
```

注意：`DATETIME6` 是否从 `app.models.base` 导出请先 Read `base.py` 确认（Phase 3 模型用 `from app.models.base import ... DATETIME6`）。若 `base.py` 未导出 `DATETIME6` 而是在别处，按真实导入路径调整 import。

- [ ] **Step 4: 跑测试确认通过**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/test_notification_model.py -q`
Expected: PASS（2 passed）

- [ ] **Step 5: 提交**
```bash
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP" && git add backend/app/models/notification.py backend/tests/unit/test_notification_model.py
git diff --cached --name-only
git commit -m "$(printf 'feat(phase-5a): add Notification + NotificationArm models\n\nCo-Authored-By: Claude Opus 4.5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 3: Alembic 迁移 — 建 tb_notification + tb_notification_arm

**Files:**
- Create: `backend/alembic/versions/20260531_0015_phase5a_notification.py`
- Test: 无（迁移由全量回归 + head 校验覆盖）

- [ ] **Step 1: 写迁移**

先 Read 一个既有迁移（如 `backend/alembic/versions/20260531_0014_po_line_no.py` 或 `phase3c_purchase_order` 那支）确认 `DATETIME6` 在迁移里的真实 import 来源与 `op` 用法。然后写 `backend/alembic/versions/20260531_0015_phase5a_notification.py`：
```python
"""phase5a notification tables

Revision ID: phase5a_notification
Revises: po_line_no
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.models.base import DATETIME6

revision: str = "phase5a_notification"
down_revision: str | Sequence[str] | None = "po_line_no"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _ts() -> list[sa.Column]:
    return [
        sa.Column("created_at", DATETIME6, nullable=False, index=True),
        sa.Column("updated_at", DATETIME6, nullable=False),
    ]


def _company_fk() -> sa.Column:
    return sa.Column(
        "company_id", sa.String(36),
        sa.ForeignKey("tb_company.id", ondelete="CASCADE"), nullable=False, index=True,
    )


def upgrade() -> None:
    op.create_table(
        "tb_notification",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        *_ts(),
        sa.Column("recipient_user_id", sa.String(36), nullable=False, index=True),
        sa.Column("type", sa.String(40), nullable=False),
        sa.Column("entity_type", sa.String(40), nullable=True),
        sa.Column("entity_id", sa.String(36), nullable=True),
        sa.Column("params", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("actor_user_id", sa.String(36), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default="0", index=True),
        sa.Column("read_at", DATETIME6, nullable=True),
        sa.Column("dedup_key", sa.String(120), nullable=True),
    )
    op.create_index("ix_tb_notification_recipient_read", "tb_notification",
                    ["company_id", "recipient_user_id", "is_read"])
    op.create_index("ix_tb_notification_dedup", "tb_notification",
                    ["company_id", "dedup_key"])

    op.create_table(
        "tb_notification_arm",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        *_ts(),
        sa.Column("key", sa.String(120), nullable=False),
        sa.UniqueConstraint("company_id", "key", name="uq_notification_arm"),
    )


def downgrade() -> None:
    op.drop_table("tb_notification_arm")
    op.drop_index("ix_tb_notification_dedup", table_name="tb_notification")
    op.drop_index("ix_tb_notification_recipient_read", table_name="tb_notification")
    op.drop_table("tb_notification")
```
注意：`index=True` 在 `sa.Column(...)` 里对 `created_at`/`recipient_user_id`/`is_read`/`company_id` 会自动建索引（命名 `ix_<table>_<col>`），与模型 mixin 的 `index=True` 对应。复合索引显式 `create_index`。若既有迁移风格是用独立 `op.create_index` 而非 column `index=True`，请照既有风格统一（先 Read 范例迁移）。

- [ ] **Step 2: 校验迁移可前后滚 + head 推进**

Run:
```bash
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP/backend" && source .venv/bin/activate
alembic heads
alembic upgrade head && alembic heads
alembic downgrade -1 && alembic upgrade head
```
Expected: `alembic heads` 最终唯一 head = `phase5a_notification`；upgrade/downgrade 无报错。
（若本地 alembic 连的是真实库且无法迁移，至少确认 `python -c "from alembic.config import Config; from alembic.script import ScriptDirectory; s=ScriptDirectory.from_config(Config('alembic.ini')); print(s.get_heads())"` 显示单 head `phase5a_notification`。）

- [ ] **Step 3: 提交**
```bash
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP" && git add backend/alembic/versions/20260531_0015_phase5a_notification.py
git diff --cached --name-only
git commit -m "$(printf 'feat(phase-5a): add notification tables migration\n\nCo-Authored-By: Claude Opus 4.5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 4: notification_service — notify + 接收人解析 + 边沿原语

**Files:**
- Create: `backend/app/services/notification_service.py`
- Test: `backend/tests/unit/test_notification_service.py`

- [ ] **Step 1: 写失败测试** `backend/tests/unit/test_notification_service.py`:
```python
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.notification import Notification, NotificationArm
from app.models.role import Role
from app.models.team import Team, TeamUser
from app.models.user import User, UserStatus
from app.models.work_order import WorkOrder, WorkOrderAssignee, WorkOrderTeam
from app.services import notification_service as svc

CO = "co-1"


def _user(db, uid, status=UserStatus.active, role_id=None):
    db.add(User(id=uid, email=f"{uid}@x.com", password_hash="x", name=uid,
                status=status, role_id=role_id, company_id=CO))
    db.commit()


def _wo(db, wid="wo-1", primary=None):
    wo = WorkOrder(id=wid, custom_id="WO1", title="t", primary_user_id=primary, company_id=CO)
    db.add(wo)
    db.commit()
    db.refresh(wo)
    return wo


def test_notify_one_row_per_recipient(db: Session):
    n = svc.notify(db, company_id=CO, recipient_ids={"u-1", "u-2"}, type="WO_ASSIGNED",
                   entity_type="work_order", entity_id="wo-1",
                   params={"custom_id": "WO1"}, actor_user_id=None)
    db.commit()
    assert n == 2
    rows = db.execute(select(Notification)).scalars().all()
    assert {r.recipient_user_id for r in rows} == {"u-1", "u-2"}
    assert json.loads(rows[0].params)["custom_id"] == "WO1"


def test_notify_empty_recipients_noop(db: Session):
    assert svc.notify(db, company_id=CO, recipient_ids=set(), type="X",
                      entity_type=None, entity_id=None, params={}, actor_user_id=None) == 0


def test_resolve_wo_recipients_merges_and_filters_active(db: Session):
    _user(db, "primary")
    _user(db, "a1")
    _user(db, "inactive", status=UserStatus.disabled)
    _user(db, "tm1")
    db.add(Team(id="team-1", name="T", company_id=CO))
    db.commit()
    db.add(TeamUser(team_id="team-1", user_id="tm1", company_id=CO))
    wo = _wo(db, primary="primary")
    db.add(WorkOrderAssignee(work_order_id=wo.id, user_id="a1", company_id=CO))
    db.add(WorkOrderAssignee(work_order_id=wo.id, user_id="inactive", company_id=CO))
    db.add(WorkOrderTeam(work_order_id=wo.id, team_id="team-1", company_id=CO))
    db.commit()
    got = svc.resolve_wo_recipients(db, wo, exclude_actor_id=None)
    assert got == {"primary", "a1", "tm1"}  # inactive 被过滤


def test_resolve_wo_recipients_excludes_actor(db: Session):
    _user(db, "primary")
    _user(db, "a1")
    wo = _wo(db, primary="primary")
    db.add(WorkOrderAssignee(work_order_id=wo.id, user_id="a1", company_id=CO))
    db.commit()
    assert svc.resolve_wo_recipients(db, wo, exclude_actor_id="a1") == {"primary"}


def test_resolve_permission_holders_by_code(db: Session):
    db.add(Role(id="r-appr", code="approver", name="A", permissions=["request.approve"], company_id=CO))
    db.add(Role(id="r-tech", code="technician", name="T", permissions=["work_order.view"], company_id=CO))
    db.commit()
    _user(db, "appr", role_id="r-appr")
    _user(db, "tech", role_id="r-tech")
    _user(db, "appr_off", status=UserStatus.disabled, role_id="r-appr")
    got = svc.resolve_permission_holders(db, CO, "request.approve", exclude_actor_id=None)
    assert got == {"appr"}  # 仅活跃且有该权限


def test_resolve_permission_holders_super_admin_wildcard(db: Session):
    db.add(Role(id="r-sa", code="super_admin", name="SA", permissions=[], company_id=CO))
    db.commit()
    _user(db, "sa", role_id="r-sa")
    # super_admin 通配 ALL_PERMISSIONS（含 part.edit）
    assert "sa" in svc.resolve_permission_holders(db, CO, "part.edit", exclude_actor_id=None)


def test_arm_disarm_cycle(db: Session):
    assert svc.is_armed(db, CO, "K1") is False
    svc.arm(db, CO, "K1")
    db.commit()
    assert svc.is_armed(db, CO, "K1") is True
    svc.disarm(db, CO, "K1")
    db.commit()
    assert svc.is_armed(db, CO, "K1") is False
    assert db.execute(select(NotificationArm)).scalars().all() == []
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/test_notification_service.py -q`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 写实现** `backend/app/services/notification_service.py`:
```python
"""站内通知生成服务（Phase 5A）。

附加式观察者：notify(...) 仅向 session add 行，由调用方所在事务提交。
接收人解析复用 permissions.effective_codes；边沿原语 arm/disarm 仿 meter is_armed。
所有查询显式按 company_id 过滤（不依赖租户事件），以便调度 tick 下也正确。
"""
from __future__ import annotations

import json

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.notification import Notification, NotificationArm
from app.models.role import Role
from app.models.team import TeamUser
from app.models.user import User, UserStatus
from app.models.work_order import WorkOrder, WorkOrderAssignee, WorkOrderTeam
from app.permissions import effective_codes


# --------------------------------------------------------------------------- #
# 落行
# --------------------------------------------------------------------------- #
def notify(
    db: Session, *, company_id: str, recipient_ids: set[str], type: str,
    entity_type: str | None, entity_id: str | None, params: dict,
    actor_user_id: str | None = None, dedup_key: str | None = None,
) -> int:
    """每个收件人 add 一行 Notification（不 commit）。返回新增行数。"""
    payload = json.dumps(params, ensure_ascii=False, default=str)
    count = 0
    for uid in recipient_ids:
        db.add(Notification(
            company_id=company_id, recipient_user_id=uid, type=type,
            entity_type=entity_type, entity_id=entity_id, params=payload,
            actor_user_id=actor_user_id, dedup_key=dedup_key,
        ))
        count += 1
    return count


# --------------------------------------------------------------------------- #
# 接收人解析
# --------------------------------------------------------------------------- #
def _active_subset(db: Session, company_id: str, ids: set[str],
                   exclude_actor_id: str | None) -> set[str]:
    if not ids:
        return set()
    rows = db.execute(
        select(User.id).where(
            User.company_id == company_id, User.id.in_(ids),
            User.status == UserStatus.active,
        )
    ).all()
    out = {r for (r,) in rows}
    if exclude_actor_id is not None:
        out.discard(exclude_actor_id)
    return out


def resolve_team_members(db: Session, company_id: str, team_ids: set[str]) -> set[str]:
    if not team_ids:
        return set()
    rows = db.execute(
        select(TeamUser.user_id).where(
            TeamUser.company_id == company_id, TeamUser.team_id.in_(team_ids)
        )
    ).all()
    return {r for (r,) in rows}


def resolve_wo_recipients(db: Session, wo: WorkOrder, *,
                          exclude_actor_id: str | None) -> set[str]:
    ids: set[str] = set()
    if wo.primary_user_id:
        ids.add(wo.primary_user_id)
    assignees = db.execute(
        select(WorkOrderAssignee.user_id).where(WorkOrderAssignee.work_order_id == wo.id)
    ).all()
    ids |= {r for (r,) in assignees}
    teams = db.execute(
        select(WorkOrderTeam.team_id).where(WorkOrderTeam.work_order_id == wo.id)
    ).all()
    ids |= resolve_team_members(db, wo.company_id, {r for (r,) in teams})
    return _active_subset(db, wo.company_id, ids, exclude_actor_id)


def resolve_permission_holders(db: Session, company_id: str, code: str, *,
                               exclude_actor_id: str | None) -> set[str]:
    rows = db.execute(
        select(User.id, Role.code, Role.permissions)
        .join(Role, User.role_id == Role.id, isouter=True)
        .where(User.company_id == company_id, User.status == UserStatus.active)
    ).all()
    out: set[str] = set()
    for uid, role_code, perms in rows:
        if code in effective_codes(role_code or "", perms or []):
            out.add(uid)
    if exclude_actor_id is not None:
        out.discard(exclude_actor_id)
    return out


def active_admins(db: Session, company_id: str) -> set[str]:
    rows = db.execute(
        select(User.id)
        .join(Role, User.role_id == Role.id)
        .where(User.company_id == company_id, User.status == UserStatus.active,
               Role.code.in_(["admin", "super_admin"]))
    ).all()
    return {r for (r,) in rows}


# --------------------------------------------------------------------------- #
# 边沿原语
# --------------------------------------------------------------------------- #
def is_armed(db: Session, company_id: str, key: str) -> bool:
    row = db.execute(
        select(NotificationArm.id).where(
            NotificationArm.company_id == company_id, NotificationArm.key == key
        )
    ).first()
    return row is not None


def arm(db: Session, company_id: str, key: str) -> None:
    db.add(NotificationArm(company_id=company_id, key=key))


def disarm(db: Session, company_id: str, key: str) -> None:
    db.execute(
        delete(NotificationArm).where(
            NotificationArm.company_id == company_id, NotificationArm.key == key
        )
    )
```

注意：`Role` 模型字段名（`code`、`permissions`）与 `app/models/role.py` 一致；`Role.permissions` 是 list[str]（与 `deps._user_permission_codes` 用法一致）。开工前 Read `app/models/role.py` 确认 `permissions` 列类型与字段名；若为关系而非标量 list，按真实结构调整 `resolve_permission_holders`（仍复用 `effective_codes`）。

- [ ] **Step 4: 跑测试确认通过**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/test_notification_service.py -q`
Expected: PASS（8 passed）

- [ ] **Step 5: 提交**
```bash
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP" && git add backend/app/services/notification_service.py backend/tests/unit/test_notification_service.py
git diff --cached --name-only
git commit -m "$(printf 'feat(phase-5a): add notification service (notify/recipients/arm)\n\nCo-Authored-By: Claude Opus 4.5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 5: notification_service 事件组合函数 + schema

**Files:**
- Modify: `backend/app/services/notification_service.py`（追加 on_* 事件函数）
- Create: `backend/app/schemas/notification.py`
- Test: `backend/tests/unit/test_notification_events.py`
- Test: `backend/tests/unit/test_notification_schema.py`

- [ ] **Step 1: 写失败测试** `backend/tests/unit/test_notification_events.py`:
```python
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.notification import Notification
from app.models.role import Role
from app.models.user import User, UserStatus
from app.models.work_order import WorkOrder, WorkOrderAssignee
from app.services import notification_service as svc

CO = "co-1"


def _user(db, uid, role_id=None, status=UserStatus.active):
    db.add(User(id=uid, email=f"{uid}@x.com", password_hash="x", name=uid,
                status=status, role_id=role_id, company_id=CO))
    db.commit()


def _wo(db, wid="wo-1", primary=None):
    wo = WorkOrder(id=wid, custom_id="WO1", title="泵维修", primary_user_id=primary, company_id=CO)
    db.add(wo)
    db.commit()
    db.refresh(wo)
    return wo


def test_on_wo_assigned_notifies_only_added_active_non_actor(db: Session):
    _user(db, "u1")
    _user(db, "actor")
    wo = _wo(db)
    svc.on_wo_assigned(db, wo, recipient_ids={"u1", "actor"}, actor_user_id="actor")
    db.commit()
    rows = db.execute(select(Notification)).scalars().all()
    assert len(rows) == 1 and rows[0].recipient_user_id == "u1"
    assert rows[0].type == "WO_ASSIGNED"
    assert json.loads(rows[0].params)["custom_id"] == "WO1"


def test_on_wo_status_changed_notifies_recipients(db: Session):
    _user(db, "primary")
    wo = _wo(db, primary="primary")
    svc.on_wo_status_changed(db, wo, from_status="OPEN", to_status="IN_PROGRESS",
                             actor_user_id=None)
    db.commit()
    row = db.execute(select(Notification)).scalars().one()
    assert row.type == "WO_STATUS_CHANGED"
    p = json.loads(row.params)
    assert p["from_status"] == "OPEN" and p["to_status"] == "IN_PROGRESS"


def test_on_wo_auto_generated_falls_back_to_admins(db: Session):
    db.add(Role(id="r-admin", code="admin", name="A", permissions=[], company_id=CO))
    db.commit()
    _user(db, "boss", role_id="r-admin")
    wo = _wo(db)  # 无指派人
    svc.on_wo_auto_generated(db, wo, actor_user_id=None)
    db.commit()
    rows = db.execute(select(Notification)).scalars().all()
    assert {r.recipient_user_id for r in rows} == {"boss"}
    assert rows[0].type == "WO_AUTO_GENERATED"


def test_on_request_submitted_notifies_approvers(db: Session):
    db.add(Role(id="r-appr", code="approver", name="A",
                permissions=["request.approve"], company_id=CO))
    db.commit()
    _user(db, "appr", role_id="r-appr")

    class _R:  # 轻量替身：on_request_submitted 只读 id/custom_id/title/company_id
        id = "rq-1"; custom_id = "RQ1"; title = "申请"; company_id = CO

    svc.on_request_submitted(db, _R(), actor_user_id=None)
    db.commit()
    row = db.execute(select(Notification)).scalars().one()
    assert row.type == "REQUEST_SUBMITTED" and row.recipient_user_id == "appr"
    assert row.entity_type == "request" and row.entity_id == "rq-1"


def test_on_po_approved_notifies_po_approvers(db: Session):
    db.add(Role(id="r-poa", code="po", name="P",
                permissions=["purchase_order.approve"], company_id=CO))
    db.commit()
    _user(db, "poappr", role_id="r-poa")

    class _PO:
        id = "po-1"; custom_id = "PO1"; company_id = CO

    svc.on_po_approved(db, _PO(), actor_user_id=None)
    db.commit()
    row = db.execute(select(Notification)).scalars().one()
    assert row.type == "PO_APPROVED" and row.recipient_user_id == "poappr"
```

`backend/tests/unit/test_notification_schema.py`:
```python
from datetime import datetime

from app.schemas.notification import NotificationRead, UnreadCount


def test_notification_read_params_dict():
    m = NotificationRead(
        id="n-1", type="WO_ASSIGNED", entity_type="work_order", entity_id="wo-1",
        params={"custom_id": "WO1"}, actor_user_id=None, is_read=False,
        read_at=None, created_at=datetime(2026, 1, 1, 0, 0, 0),
    )
    assert m.params["custom_id"] == "WO1" and m.is_read is False


def test_unread_count():
    assert UnreadCount(count=5).count == 5
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/test_notification_events.py tests/unit/test_notification_schema.py -q`
Expected: FAIL（AttributeError on_* / ModuleNotFoundError schema）

- [ ] **Step 3a: 追加事件函数到 `app/services/notification_service.py`**（文件末尾）:
```python
# --------------------------------------------------------------------------- #
# 事件组合（内联调用；均不 commit，由调用方事务提交）
# --------------------------------------------------------------------------- #
def on_wo_assigned(db: Session, wo: WorkOrder, *, recipient_ids: set[str],
                   actor_user_id: str | None) -> None:
    recips = _active_subset(db, wo.company_id, set(recipient_ids), actor_user_id)
    notify(db, company_id=wo.company_id, recipient_ids=recips, type="WO_ASSIGNED",
           entity_type="work_order", entity_id=wo.id,
           params={"custom_id": wo.custom_id, "title": wo.title},
           actor_user_id=actor_user_id)


def on_wo_status_changed(db: Session, wo: WorkOrder, *, from_status: str,
                         to_status: str, actor_user_id: str | None) -> None:
    recips = resolve_wo_recipients(db, wo, exclude_actor_id=actor_user_id)
    notify(db, company_id=wo.company_id, recipient_ids=recips, type="WO_STATUS_CHANGED",
           entity_type="work_order", entity_id=wo.id,
           params={"custom_id": wo.custom_id, "from_status": from_status,
                   "to_status": to_status},
           actor_user_id=actor_user_id)


def on_wo_auto_generated(db: Session, wo: WorkOrder, *,
                         actor_user_id: str | None) -> None:
    recips = resolve_wo_recipients(db, wo, exclude_actor_id=actor_user_id)
    if not recips:
        recips = active_admins(db, wo.company_id)
        if actor_user_id is not None:
            recips.discard(actor_user_id)
    notify(db, company_id=wo.company_id, recipient_ids=recips, type="WO_AUTO_GENERATED",
           entity_type="work_order", entity_id=wo.id,
           params={"custom_id": wo.custom_id, "title": wo.title},
           actor_user_id=actor_user_id)


def on_request_submitted(db: Session, request, *, actor_user_id: str | None) -> None:
    recips = resolve_permission_holders(db, request.company_id, "request.approve",
                                        exclude_actor_id=actor_user_id)
    notify(db, company_id=request.company_id, recipient_ids=recips,
           type="REQUEST_SUBMITTED", entity_type="request", entity_id=request.id,
           params={"custom_id": request.custom_id, "title": request.title},
           actor_user_id=actor_user_id)


def on_po_submitted(db: Session, po, *, actor_user_id: str | None) -> None:
    _notify_po(db, po, "PO_SUBMITTED", actor_user_id)


def on_po_approved(db: Session, po, *, actor_user_id: str | None) -> None:
    _notify_po(db, po, "PO_APPROVED", actor_user_id)


def _notify_po(db: Session, po, type_: str, actor_user_id: str | None) -> None:
    recips = resolve_permission_holders(db, po.company_id, "purchase_order.approve",
                                        exclude_actor_id=actor_user_id)
    notify(db, company_id=po.company_id, recipient_ids=recips, type=type_,
           entity_type="purchase_order", entity_id=po.id,
           params={"custom_id": po.custom_id}, actor_user_id=actor_user_id)
```

- [ ] **Step 3b: 写 schema** `backend/app/schemas/notification.py`:
```python
"""站内通知响应 schema（Phase 5A）。"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class NotificationRead(BaseModel):
    id: str
    type: str
    entity_type: str | None
    entity_id: str | None
    params: dict
    actor_user_id: str | None
    is_read: bool
    read_at: datetime | None
    created_at: datetime


class UnreadCount(BaseModel):
    count: int


class ReadAllResult(BaseModel):
    updated: int
```

- [ ] **Step 4: 跑测试确认通过**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/test_notification_events.py tests/unit/test_notification_schema.py -q`
Expected: PASS（5 + 2 = 7 passed）

- [ ] **Step 5: 提交**
```bash
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP" && git add backend/app/services/notification_service.py backend/app/schemas/notification.py backend/tests/unit/test_notification_events.py backend/tests/unit/test_notification_schema.py
git diff --cached --name-only
git commit -m "$(printf 'feat(phase-5a): add notification event composers + schemas\n\nCo-Authored-By: Claude Opus 4.5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 6: router — feed/未读数/标记已读 + main 挂载

**Files:**
- Create: `backend/app/routers/notifications.py`
- Modify: `backend/app/main.py`（import 块 + include_router）
- Test: `backend/tests/test_notifications_api.py`

- [ ] **Step 1: 写失败测试** `backend/tests/test_notifications_api.py`:
```python
"""站内通知 API（Phase 5A）：鉴权/分页/未读数/标记已读/只见自己/跨租户。"""
from __future__ import annotations

import json

from sqlalchemy import select

from app.models.company import Company
from app.models.notification import Notification


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _admin(client, *, company="Acme", email="admin@acme.com"):
    return client.post("/api/v1/auth/register", json={
        "company_name": company, "email": email,
        "password": "secret123", "name": "Admin"}).json()["access_token"]


def _company_id(db, slug):
    return db.execute(select(Company).where(Company.slug == slug)).scalar_one().id


def _me_id(client, token):
    return client.get("/api/v1/auth/me", headers=_h(token)).json()["id"]


def _seed(db, *, company_id, recipient, type="WO_ASSIGNED", is_read=False):
    n = Notification(company_id=company_id, recipient_user_id=recipient, type=type,
                     entity_type="work_order", entity_id="wo-1",
                     params=json.dumps({"custom_id": "WO1"}), is_read=is_read)
    db.add(n)
    db.commit()
    db.refresh(n)
    return n


def test_requires_auth(client):
    assert client.get("/api/v1/notifications").status_code == 401


def test_feed_returns_own_paginated(client, db):
    t = _admin(client)
    co = _company_id(db, "acme")
    me = _me_id(client, t)
    for i in range(3):
        _seed(db, company_id=co, recipient=me)
    body = client.get("/api/v1/notifications?page=1&page_size=2", headers=_h(t)).json()
    assert body["total"] == 3 and len(body["items"]) == 2
    assert body["page"] == 1 and body["page_size"] == 2 and body["total_pages"] == 2
    assert body["items"][0]["params"]["custom_id"] == "WO1"


def test_feed_only_sees_own(client, db):
    t = _admin(client)
    co = _company_id(db, "acme")
    me = _me_id(client, t)
    _seed(db, company_id=co, recipient=me)
    _seed(db, company_id=co, recipient="someone-else")
    body = client.get("/api/v1/notifications", headers=_h(t)).json()
    assert body["total"] == 1 and body["items"][0]["params"]["custom_id"] == "WO1"


def test_feed_filter_is_read(client, db):
    t = _admin(client)
    co = _company_id(db, "acme")
    me = _me_id(client, t)
    _seed(db, company_id=co, recipient=me, is_read=False)
    _seed(db, company_id=co, recipient=me, is_read=True)
    body = client.get("/api/v1/notifications?is_read=false", headers=_h(t)).json()
    assert body["total"] == 1


def test_unread_count(client, db):
    t = _admin(client)
    co = _company_id(db, "acme")
    me = _me_id(client, t)
    _seed(db, company_id=co, recipient=me, is_read=False)
    _seed(db, company_id=co, recipient=me, is_read=False)
    _seed(db, company_id=co, recipient=me, is_read=True)
    assert client.get("/api/v1/notifications/unread-count", headers=_h(t)).json()["count"] == 2


def test_mark_one_read(client, db):
    t = _admin(client)
    co = _company_id(db, "acme")
    me = _me_id(client, t)
    n = _seed(db, company_id=co, recipient=me)
    assert client.post(f"/api/v1/notifications/{n.id}/read", headers=_h(t)).status_code == 200
    assert client.get("/api/v1/notifications/unread-count", headers=_h(t)).json()["count"] == 0


def test_mark_one_read_not_owner_404(client, db):
    t = _admin(client)
    co = _company_id(db, "acme")
    n = _seed(db, company_id=co, recipient="not-me")
    assert client.post(f"/api/v1/notifications/{n.id}/read", headers=_h(t)).status_code == 404


def test_mark_all_read(client, db):
    t = _admin(client)
    co = _company_id(db, "acme")
    me = _me_id(client, t)
    _seed(db, company_id=co, recipient=me)
    _seed(db, company_id=co, recipient=me)
    r = client.post("/api/v1/notifications/read-all", headers=_h(t)).json()
    assert r["updated"] == 2
    assert client.get("/api/v1/notifications/unread-count", headers=_h(t)).json()["count"] == 0


def test_tenant_isolation(client, db):
    ta = _admin(client, company="Acme", email="a@acme.com")
    tb = _admin(client, company="Beta", email="b@beta.com")
    co_b = _company_id(db, "beta")
    me_a = _me_id(client, ta)
    # 给 B 公司插一条 recipient 恰为 A 用户 id（同 id 跨租户也不可见）
    _seed(db, company_id=co_b, recipient=me_a)
    assert client.get("/api/v1/notifications", headers=_h(ta)).json()["total"] == 0
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/test_notifications_api.py -q`
Expected: FAIL（404 路由不存在）

- [ ] **Step 3: 写 router** `backend/app/routers/notifications.py`:
```python
"""站内通知 API（/api/v1/notifications）。个人数据：仅本人，无需额外权限码。"""
from __future__ import annotations

import json
import math
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db
from app.errors import not_found
from app.models.base import utcnow
from app.models.notification import Notification
from app.models.user import User
from app.schemas.common import Page
from app.schemas.notification import NotificationRead, ReadAllResult, UnreadCount

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


def _to_read(n: Notification) -> NotificationRead:
    return NotificationRead(
        id=n.id, type=n.type, entity_type=n.entity_type, entity_id=n.entity_id,
        params=json.loads(n.params or "{}"), actor_user_id=n.actor_user_id,
        is_read=n.is_read, read_at=n.read_at, created_at=n.created_at,
    )


@router.get("", response_model=Page[NotificationRead])
def list_notifications(
    is_read: bool | None = None,
    type: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conds = [Notification.recipient_user_id == current_user.id]
    if is_read is not None:
        conds.append(Notification.is_read.is_(is_read))
    if type is not None:
        conds.append(Notification.type == type)
    if date_from is not None:
        conds.append(Notification.created_at >= datetime(date_from.year, date_from.month, date_from.day))
    if date_to is not None:
        end = datetime(date_to.year, date_to.month, date_to.day)
        conds.append(Notification.created_at < end + timedelta(days=1))

    total = db.execute(select(func.count()).select_from(Notification).where(*conds)).scalar_one()
    rows = db.execute(
        select(Notification).where(*conds)
        .order_by(Notification.created_at.desc())
        .limit(page_size).offset((page - 1) * page_size)
    ).scalars().all()
    return Page[NotificationRead](
        items=[_to_read(n) for n in rows], total=total, page=page, page_size=page_size,
        total_pages=math.ceil(total / page_size) if page_size else 0,
    )


@router.get("/unread-count", response_model=UnreadCount)
def unread_count(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    n = db.execute(
        select(func.count()).select_from(Notification).where(
            Notification.recipient_user_id == current_user.id,
            Notification.is_read.is_(False),
        )
    ).scalar_one()
    return UnreadCount(count=n)


@router.post("/{notification_id}/read", response_model=NotificationRead)
def mark_read(
    notification_id: str,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    n = db.get(Notification, notification_id)
    if n is None or n.recipient_user_id != current_user.id:
        raise not_found("NOTIFICATION_NOT_FOUND", "通知不存在")
    if not n.is_read:
        n.is_read = True
        n.read_at = utcnow()
        db.commit()
        db.refresh(n)
    return _to_read(n)


@router.post("/read-all", response_model=ReadAllResult)
def mark_all_read(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    rows = db.execute(
        select(Notification).where(
            Notification.recipient_user_id == current_user.id,
            Notification.is_read.is_(False),
        )
    ).scalars().all()
    now = utcnow()
    for n in rows:
        n.is_read = True
        n.read_at = now
    db.commit()
    return ReadAllResult(updated=len(rows))
```
注意：
- `not_found(code,msg)` 来自 `app.errors`（与既有 router 同构）；若签名不同（如需 `field=`）按真实签名调整。
- `Page` 来自 `app/schemas/common.py`（含 `total_pages`）；先 Read 确认其字段名与本计划一致。
- 通过 `get_current_user` 注入本人；feed/未读数/标记已读全部以 `recipient_user_id == current_user.id` 过滤。跨租户：`get_current_user` 已 `set_current_company_id`，`with_loader_criteria` 对 Notification（TenantMixin）生效，故跨租户同 id 的行不可见（测试 `test_tenant_isolation` 覆盖）。

- [ ] **Step 4: 挂载到 `app/main.py`**（用 Edit 精确插入）

先 Read 文件。在 `from app.routers import (...)` 块内 `analytics,` 行之后插入一行 `    notifications,`。在 `app.include_router(analytics.router)` 行之后插入 `app.include_router(notifications.router)`。

- [ ] **Step 5: 跑测试 + 导入冒烟**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/test_notifications_api.py -q && python -c "import app.main"`
Expected: PASS（9 passed）+ 无导入错误

- [ ] **Step 6: 提交**
```bash
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP" && git add backend/app/routers/notifications.py backend/app/main.py backend/tests/test_notifications_api.py
git diff --cached --name-only
git commit -m "$(printf 'feat(phase-5a): add notifications feed/unread/read API + mount\n\nCo-Authored-By: Claude Opus 4.5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 7: 内联挂钩 — 工单指派 / 状态变更

**Files:**
- Modify: `backend/app/services/work_order_service.py`（`set_assignees`/`set_teams`/`transition` 三处，各在 `db.commit()` 前插入 notify）
- Test: `backend/tests/unit/test_notify_hook_work_order.py`

- [ ] **Step 1: 写失败测试** `backend/tests/unit/test_notify_hook_work_order.py`:
```python
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.notification import Notification
from app.models.user import User, UserStatus
from app.models.work_order import WorkOrder, WorkOrderAssignee
from app.schemas.work_order import WorkOrderTransition
from app.models.work_order_status import WorkOrderStatus
from app.services import work_order_service as wos

CO = "co-1"


def _user(db, uid):
    db.add(User(id=uid, email=f"{uid}@x.com", password_hash="x", name=uid,
                status=UserStatus.active, company_id=CO))
    db.commit()


def _wo(db, primary=None, status=WorkOrderStatus.OPEN):
    wo = WorkOrder(custom_id="WO1", title="t", status=status,
                   primary_user_id=primary, company_id=CO)
    db.add(wo)
    db.commit()
    db.refresh(wo)
    return wo


def test_set_assignees_notifies_newly_added_only(db: Session):
    _user(db, "u1")
    _user(db, "u2")
    wo = _wo(db)
    wos.set_assignees(db, wo, ["u1"], CO, actor_user_id="boss")  # 首次加 u1
    wos.set_assignees(db, wo, ["u1", "u2"], CO, actor_user_id="boss")  # 再加 u2
    rows = db.execute(select(Notification).where(Notification.type == "WO_ASSIGNED")).scalars().all()
    # u1 仅在第一次被通知；第二次仅 u2
    recips = sorted(r.recipient_user_id for r in rows)
    assert recips == ["u1", "u2"]


def test_set_assignees_excludes_actor(db: Session):
    _user(db, "boss")
    wo = _wo(db)
    wos.set_assignees(db, wo, ["boss"], CO, actor_user_id="boss")
    assert db.execute(select(Notification)).scalars().all() == []


def test_transition_notifies_recipients(db: Session):
    _user(db, "primary")
    wo = _wo(db, primary="primary")
    wos.transition(db, wo, WorkOrderTransition(to_status=WorkOrderStatus.IN_PROGRESS, note=""),
                   CO, actor_user_id=None)
    row = db.execute(select(Notification).where(Notification.type == "WO_STATUS_CHANGED")).scalars().one()
    assert row.recipient_user_id == "primary"
```
（注：`WorkOrderTransition` 的字段名/构造若与此不符，先 Read `app/schemas/work_order.py` 按真实签名调整测试构造，保持断言意图不变。）

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/test_notify_hook_work_order.py -q`
Expected: FAIL（无通知行）

- [ ] **Step 3: 改 `app/services/work_order_service.py`**

先 Read 文件。在文件顶部 import 区加（与既有 import 同区）：
```python
from app.services import notification_service as _notif
```
若担心循环依赖，改为在各函数内部 `from app.services import notification_service as _notif`（`notification_service` 不 import `work_order_service`，模块级安全；但若 Read 后发现既有风格是函数内 import，则照既有风格）。

在 `set_assignees` 内：在 `db.execute(delete(WorkOrderAssignee)...)` **之前**捕获旧集合，在 `_log(...)` **之后、`db.commit()` 之前**插入 notify：
```python
def set_assignees(db, wo, user_ids, company_id, actor_user_id=None):
    prior = {r for (r,) in db.execute(
        select(WorkOrderAssignee.user_id).where(WorkOrderAssignee.work_order_id == wo.id)
    ).all()}
    db.execute(delete(WorkOrderAssignee).where(WorkOrderAssignee.work_order_id == wo.id))
    for uid in dict.fromkeys(user_ids):
        db.add(WorkOrderAssignee(work_order_id=wo.id, user_id=uid, company_id=company_id))
    _log(db, wo.id, company_id, "ASSIGN", actor_user_id=actor_user_id)
    added = set(dict.fromkeys(user_ids)) - prior
    _notif.on_wo_assigned(db, wo, recipient_ids=added, actor_user_id=actor_user_id)
    db.commit()
    db.refresh(wo)
    return wo
```
（`select` 已在该文件 import；若没有则在顶部补 `from sqlalchemy import select`，先 Read 确认。）

在 `set_teams` 内同理：捕获旧 team 集，计算新增 team，展开成员后 notify：
```python
def set_teams(db, wo, team_ids_, company_id, actor_user_id=None):
    prior = {r for (r,) in db.execute(
        select(WorkOrderTeam.team_id).where(WorkOrderTeam.work_order_id == wo.id)
    ).all()}
    db.execute(delete(WorkOrderTeam).where(WorkOrderTeam.work_order_id == wo.id))
    for tid in dict.fromkeys(team_ids_):
        db.add(WorkOrderTeam(work_order_id=wo.id, team_id=tid, company_id=company_id))
    _log(db, wo.id, company_id, "ASSIGN", actor_user_id=actor_user_id)
    added_teams = set(dict.fromkeys(team_ids_)) - prior
    members = _notif.resolve_team_members(db, company_id, added_teams)
    _notif.on_wo_assigned(db, wo, recipient_ids=members, actor_user_id=actor_user_id)
    db.commit()
    db.refresh(wo)
    return wo
```

在 `transition` 内：在 `_log(...)` **之后、`db.commit()` 之前**插入：
```python
    _log(db, wo.id, company_id, "STATUS_CHANGE", actor_user_id=actor_user_id,
         from_status=src.value, to_status=dst.value, comment=payload.note)
    _notif.on_wo_status_changed(db, wo, from_status=src.value, to_status=dst.value,
                                actor_user_id=actor_user_id)
    db.commit()
```

- [ ] **Step 4: 跑测试确认通过 + 既有工单测试不破**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/test_notify_hook_work_order.py -q && PYTHONDONTWRITEBYTECODE=1 pytest tests/ -q -k "work_order"`
Expected: PASS（新测 3 + 既有工单测试仍绿）

- [ ] **Step 5: 提交**
```bash
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP" && git add backend/app/services/work_order_service.py backend/tests/unit/test_notify_hook_work_order.py
git diff --cached --name-only
git commit -m "$(printf 'feat(phase-5a): emit notifications on WO assign/status change\n\nCo-Authored-By: Claude Opus 4.5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 8: 内联挂钩 — PM / Meter 自动建单

**Files:**
- Modify: `backend/app/services/pm_service.py`（`generate_once`，`db.commit()` 前）
- Modify: `backend/app/services/meter_trigger_service.py`（`generate_from_trigger`，`return wo` 前）
- Test: `backend/tests/unit/test_notify_hook_autogen.py`

- [ ] **Step 1: 写失败测试** `backend/tests/unit/test_notify_hook_autogen.py`:
```python
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.notification import Notification
from app.models.user import User, UserStatus
from app.models.work_order import WorkOrder
from app.services import notification_service as notif

CO = "co-1"


def test_on_wo_auto_generated_notifies_primary(db: Session):
    db.add(User(id="p1", email="p1@x.com", password_hash="x", name="p1",
                status=UserStatus.active, company_id=CO))
    db.commit()
    wo = WorkOrder(custom_id="WO9", title="自动单", primary_user_id="p1", company_id=CO)
    db.add(wo)
    db.commit()
    db.refresh(wo)
    notif.on_wo_auto_generated(db, wo, actor_user_id=None)
    db.commit()
    row = db.execute(select(Notification)).scalars().one()
    assert row.type == "WO_AUTO_GENERATED" and row.recipient_user_id == "p1"
    assert row.entity_id == wo.id
```
（说明：PM/meter 端到端建单链路较重，本 task 单测验证挂钩函数语义；真实 service 调用在 Step 3 接线，由 Step 4 既有 pm/meter 测试回归保证不破。）

- [ ] **Step 2: 跑测试确认失败/通过**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/test_notify_hook_autogen.py -q`
Expected: PASS（on_wo_auto_generated 已在 Task 5 实现，故此单测应 PASS）。若已 PASS，仍继续 Step 3 接线（接线由既有 pm/meter 回归覆盖）。

- [ ] **Step 3: 接线**

**`app/services/pm_service.py`** `generate_once`：先 Read 定位 `wo = wos.create_work_order(...)` 与函数末尾 `db.commit()`。在 `pm.next_due_date = _advance_due(...)` 之后、`db.commit()` 之前插入：
```python
    from app.services import notification_service as _notif
    _notif.on_wo_auto_generated(db, wo, actor_user_id=actor_user_id)
```
（用函数内 import，因 pm_service 既有风格即在函数内 import `wos`，避免循环依赖。）

**`app/services/meter_trigger_service.py`** `generate_from_trigger`：在 `trig.is_armed = False` 之后、`return wo` 之前插入：
```python
    from app.services import notification_service as _notif
    _notif.on_wo_auto_generated(db, wo, actor_user_id=actor_user_id)
```
（注：此处不 commit；通知行随调用方 `meter_service` 末尾 commit 落地，与 trigger 字段变更一致。）

- [ ] **Step 4: 跑测试确认通过 + 既有 pm/meter 回归**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/test_notify_hook_autogen.py -q && PYTHONDONTWRITEBYTECODE=1 pytest tests/ -q -k "pm or meter"`
Expected: PASS（新测 + 既有 pm/meter 测试仍绿）

- [ ] **Step 5: 提交**
```bash
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP" && git add backend/app/services/pm_service.py backend/app/services/meter_trigger_service.py backend/tests/unit/test_notify_hook_autogen.py
git diff --cached --name-only
git commit -m "$(printf 'feat(phase-5a): emit notifications on PM/Meter auto-generated WO\n\nCo-Authored-By: Claude Opus 4.5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 9: 内联挂钩 — 请求提交 / PO 提交 / PO 审批

**Files:**
- Modify: `backend/app/services/request_service.py`（`create_request`，`db.commit()` 前；需先 `db.flush()` 取 id）
- Modify: `backend/app/services/purchase_order_service.py`（`submit_purchase_order` 与 `approve_purchase_order`，各 `db.commit()` 前）
- Test: `backend/tests/unit/test_notify_hook_approval.py`

- [ ] **Step 1: 写失败测试** `backend/tests/unit/test_notify_hook_approval.py`:
```python
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.notification import Notification
from app.models.role import Role
from app.models.user import User, UserStatus
from app.schemas.request import RequestCreate
from app.services import request_service as reqs

CO = "co-1"


def _approver(db, code_perm):
    db.add(Role(id=f"r-{code_perm}", code="appr", name="A",
                permissions=[code_perm], company_id=CO))
    db.commit()
    db.add(User(id="appr", email="appr@x.com", password_hash="x", name="appr",
                status=UserStatus.active, role_id=f"r-{code_perm}", company_id=CO))
    db.commit()


def test_create_request_notifies_approvers(db: Session):
    _approver(db, "request.approve")
    reqs.create_request(db, RequestCreate(title="申请X"), CO, actor_user_id=None)
    row = db.execute(select(Notification).where(Notification.type == "REQUEST_SUBMITTED")).scalars().one()
    assert row.recipient_user_id == "appr" and row.entity_type == "request"
```
（注：`RequestCreate` 必填字段若不止 `title`，先 Read `app/schemas/request.py` 补齐最小构造；保持断言意图不变。PO 的提交/审批端到端较重，PO 通知语义已由 Task 5 `test_on_po_*` 单测覆盖，本 task 仅验证 request 接线 + 由 Step 4 既有 PO 回归保证 PO 接线不破。）

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/test_notify_hook_approval.py -q`
Expected: FAIL（无通知行）

- [ ] **Step 3: 接线**

**`app/services/request_service.py`** `create_request`：先 Read 定位 `db.add(r)` 与 `db.commit()`。改为先 flush 取 id，再 notify，再 commit：
```python
    db.add(r)
    db.flush()
    from app.services import notification_service as _notif
    _notif.on_request_submitted(db, r, actor_user_id=actor_user_id)
    db.commit()
    db.refresh(r)
    return r
```

**`app/services/purchase_order_service.py`**：
- `submit_purchase_order`：在 `_log(...)` 之后、`db.commit()` 之前插入：
```python
    from app.services import notification_service as _notif
    _notif.on_po_submitted(db, po, actor_user_id=actor_user_id)
```
- `approve_purchase_order`：在两条 `_log(...)`（STATUS_CHANGE + RECEIVED）之后、`db.commit()` 之前插入：
```python
    from app.services import notification_service as _notif
    _notif.on_po_approved(db, po, actor_user_id=actor_user_id)
```

- [ ] **Step 4: 跑测试确认通过 + 既有 request/PO 回归**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/test_notify_hook_approval.py -q && PYTHONDONTWRITEBYTECODE=1 pytest tests/ -q -k "request or purchase_order"`
Expected: PASS（新测 + 既有 request/PO 测试仍绿）

- [ ] **Step 5: 提交**
```bash
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP" && git add backend/app/services/request_service.py backend/app/services/purchase_order_service.py backend/tests/unit/test_notify_hook_approval.py
git diff --cached --name-only
git commit -m "$(printf 'feat(phase-5a): emit notifications on request submit & PO submit/approve\n\nCo-Authored-By: Claude Opus 4.5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 10: 调度 tick — 到期提醒 + 低库存（边沿去重）

**Files:**
- Create: `backend/app/tasks/due_reminder.py`
- Modify: `backend/app/tasks/scheduler.py`（import + `_run_due_reminder` wrapper + `add_job`）
- Test: `backend/tests/unit/test_due_reminder.py`

- [ ] **Step 1: 写失败测试** `backend/tests/unit/test_due_reminder.py`:
```python
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.notification import Notification, NotificationArm
from app.models.part import Part
from app.models.user import User, UserStatus
from app.models.work_order import WorkOrder
from app.models.work_order_status import WorkOrderStatus
from app.tasks import due_reminder

CO = "co-1"
NOW = datetime(2026, 1, 15, 8, 0, 0)
TODAY = NOW.date()


def _user(db, uid):
    db.add(User(id=uid, email=f"{uid}@x.com", password_hash="x", name=uid,
                status=UserStatus.active, company_id=CO))
    db.commit()


def _wo(db, *, wid, due, status=WorkOrderStatus.OPEN, primary="p1"):
    wo = WorkOrder(id=wid, custom_id=wid, title="t", status=status,
                   due_date=due, primary_user_id=primary, company_id=CO)
    db.add(wo)
    db.commit()
    return wo


def test_due_soon_fires_once_and_arms(db: Session):
    _user(db, "p1")
    _wo(db, wid="wo-soon", due=TODAY + timedelta(days=2))  # 在 [today, today+3)
    due_reminder.run(db, now=NOW)
    rows = db.execute(select(Notification).where(Notification.type == "WO_DUE_SOON")).scalars().all()
    assert len(rows) == 1 and rows[0].recipient_user_id == "p1"
    assert rows[0].dedup_key == f"WO_DUE_SOON:wo-soon:{(TODAY + timedelta(days=2)).isoformat()}"
    # 第二次 tick 不重复（已 armed）
    due_reminder.run(db, now=NOW)
    assert len(db.execute(select(Notification).where(Notification.type == "WO_DUE_SOON")).scalars().all()) == 1


def test_overdue_fires(db: Session):
    _user(db, "p1")
    _wo(db, wid="wo-late", due=TODAY - timedelta(days=1))
    due_reminder.run(db, now=NOW)
    rows = db.execute(select(Notification).where(Notification.type == "WO_OVERDUE")).scalars().all()
    assert len(rows) == 1


def test_terminal_status_excluded(db: Session):
    _user(db, "p1")
    _wo(db, wid="wo-done", due=TODAY - timedelta(days=1), status=WorkOrderStatus.COMPLETE)
    due_reminder.run(db, now=NOW)
    assert db.execute(select(Notification)).scalars().all() == []


def test_due_date_change_rearms(db: Session):
    _user(db, "p1")
    wo = _wo(db, wid="wo-x", due=TODAY + timedelta(days=2))
    due_reminder.run(db, now=NOW)
    # 改期到另一天 -> 旧 arm 失配应被 disarm，新条件再 fire
    wo.due_date = TODAY + timedelta(days=1)
    db.commit()
    due_reminder.run(db, now=NOW)
    keys = {a.key for a in db.execute(select(NotificationArm)).scalars().all()}
    assert keys == {f"WO_DUE_SOON:wo-x:{(TODAY + timedelta(days=1)).isoformat()}"}
    assert len(db.execute(select(Notification).where(Notification.type == "WO_DUE_SOON")).scalars().all()) == 2


def test_low_stock_edge(db: Session):
    db.add(Part(id="pt-1", custom_id="PRT1", name="轴承", cost=Decimal("0"),
                quantity=Decimal("1"), min_quantity=Decimal("5"), company_id=CO))
    db.commit()
    due_reminder.run(db, now=NOW)  # 无接收人也 arm（无 part.edit 用户）
    assert {a.key for a in db.execute(select(NotificationArm)).scalars().all()} == {"PART_LOW_STOCK:pt-1"}
    # 回升 -> disarm
    p = db.get(Part, "pt-1")
    p.quantity = Decimal("9")
    db.commit()
    due_reminder.run(db, now=NOW)
    assert db.execute(select(NotificationArm).where(NotificationArm.key == "PART_LOW_STOCK:pt-1")).scalars().all() == []
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/test_due_reminder.py -q`
Expected: FAIL（ModuleNotFoundError app.tasks.due_reminder）

- [ ] **Step 3: 写实现** `backend/app/tasks/due_reminder.py`:
```python
"""到期提醒 + 低库存调度任务（Phase 5A）。

跨租户扫描（bypass_tenant_scope）计算"应武装"条件集，与现有 arm 行做集合差：
新增条件 -> 解析接收人 + notify + arm；消失条件 -> disarm。边沿语义，零刷屏。
CLI：python -m app.tasks.due_reminder
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import SessionLocal
from app.logging_config import configure_logging
from app.models.base import utcnow
from app.models.notification import NotificationArm
from app.models.part import Part
from app.models.work_order import WorkOrder
from app.models.work_order_status import WorkOrderStatus
from app.services import notification_service as notif
from app.tenant import (
    bypass_tenant_scope,
    reset_current_company_id,
    set_current_company_id,
)

logger = logging.getLogger(__name__)
TASK_NAME = "due_reminder"

_TERMINAL = (WorkOrderStatus.COMPLETE, WorkOrderStatus.CANCELED)


def _compute_should(db: Session, today, soon_cutoff) -> dict[tuple[str, str], dict]:
    """跨租户计算应武装条件集：{(company_id, key): info}。"""
    should: dict[tuple[str, str], dict] = {}
    wo_rows = db.execute(
        select(WorkOrder.id, WorkOrder.company_id, WorkOrder.custom_id,
               WorkOrder.title, WorkOrder.due_date, WorkOrder.status)
        .where(WorkOrder.is_active.is_(True), WorkOrder.due_date.is_not(None),
               WorkOrder.status.not_in(_TERMINAL))
    ).all()
    for wid, cid, cust, title, due, _status in wo_rows:
        if due < today:
            key = f"WO_OVERDUE:{wid}:{due.isoformat()}"
            kind = "WO_OVERDUE"
        elif due < soon_cutoff:
            key = f"WO_DUE_SOON:{wid}:{due.isoformat()}"
            kind = "WO_DUE_SOON"
        else:
            continue
        should[(cid, key)] = {
            "kind": kind, "key": key, "company_id": cid, "entity_id": wid,
            "entity_type": "work_order",
            "params": {"custom_id": cust, "title": title, "due_date": due.isoformat()},
        }
    part_rows = db.execute(
        select(Part.id, Part.company_id, Part.custom_id, Part.name,
               Part.quantity, Part.min_quantity)
        .where(Part.is_active.is_(True), Part.non_stock.is_(False),
               Part.quantity < Part.min_quantity)
    ).all()
    for pid, cid, cust, name, qty, minq in part_rows:
        key = f"PART_LOW_STOCK:{pid}"
        should[(cid, key)] = {
            "kind": "PART_LOW_STOCK", "key": key, "company_id": cid, "entity_id": pid,
            "entity_type": "part",
            "params": {"custom_id": cust, "name": name,
                       "quantity": str(qty), "min_quantity": str(minq)},
        }
    return should


def _fire(db: Session, info: dict) -> None:
    cid = info["company_id"]
    kind = info["kind"]
    if kind in ("WO_DUE_SOON", "WO_OVERDUE"):
        wo = db.get(WorkOrder, info["entity_id"])
        recips = notif.resolve_wo_recipients(db, wo, exclude_actor_id=None) if wo else set()
    else:  # PART_LOW_STOCK
        recips = notif.resolve_permission_holders(db, cid, "part.edit", exclude_actor_id=None)
    notif.notify(db, company_id=cid, recipient_ids=recips, type=kind,
                 entity_type=info["entity_type"], entity_id=info["entity_id"],
                 params=info["params"], actor_user_id=None, dedup_key=info["key"])
    notif.arm(db, cid, info["key"])


def run(db: Session, *, now: datetime | None = None) -> dict[str, int]:
    started = now or utcnow()
    today = started.date()
    soon_cutoff = today + timedelta(days=settings.notify_due_soon_days)

    with bypass_tenant_scope():
        should = _compute_should(db, today, soon_cutoff)
        armed = {(a.company_id, a.key)
                 for a in db.execute(select(NotificationArm)).scalars().all()}

    fired = 0
    for (cid, key), info in should.items():
        if (cid, key) in armed:
            continue
        token = set_current_company_id(cid)
        try:
            _fire(db, info)
            fired += 1
        finally:
            reset_current_company_id(token)

    disarmed = 0
    should_keys = set(should.keys())
    for cid, key in armed:
        if (cid, key) in should_keys:
            continue
        token = set_current_company_id(cid)
        try:
            notif.disarm(db, cid, key)
            disarmed += 1
        finally:
            reset_current_company_id(token)

    db.commit()
    summary = {"fired": fired, "disarmed": disarmed, "armed_before": len(armed)}
    logger.info(json.dumps({"task": TASK_NAME, "started_at": started.isoformat(), **summary},
                           ensure_ascii=False))
    return summary


def main() -> None:  # pragma: no cover
    configure_logging()
    db = SessionLocal()
    try:
        run(db)
    finally:
        db.close()


if __name__ == "__main__":  # pragma: no cover
    main()
```
注意：
- `WorkOrderStatus.not_in` 用 `.not_in([...])`（SQLAlchemy 2.0）；若该枚举列以字符串存储，比较 `WorkOrder.status.not_in(_TERMINAL)` 中 `_TERMINAL` 应为枚举成员（SAEnum 列可直接与枚举成员比较）。先确认 work_order_analytics（Phase 4）里同类查询写法，保持一致。
- `bypass_tenant_scope` / `set_current_company_id` / `reset_current_company_id` 从 `app.tenant` 导入（与 `pm_generate.py` 完全一致）。
- 单次 `db.commit()`；若某 `_fire` 抛错则整 tick 回滚（数据为读+add，风险低）。

- [ ] **Step 4: 注册到 `app/tasks/scheduler.py`**（用 Edit 精确插入）

先 Read 文件。
- 在顶部 `from app.tasks import asset_gc, cleanup_attachments, cleanup_uploads, pm_generate` 行，改为追加 `due_reminder`：
```python
from app.tasks import asset_gc, cleanup_attachments, cleanup_uploads, due_reminder, pm_generate
```
- 在 `_run_pm_generate()` wrapper 之后，新增 wrapper：
```python
def _run_due_reminder() -> None:
    db = SessionLocal()
    try:
        due_reminder.run(db)
    finally:
        db.close()
```
- 在 `build_scheduler()` 内 `pm_generate` 的 `add_job(...)` 之后、`return sched` 之前，新增：
```python
    sched.add_job(
        _run_due_reminder,
        CronTrigger(hour=settings.cleanup_hour, minute=15),
        id="due_reminder",
        replace_existing=True,
    )
```

- [ ] **Step 5: 跑测试确认通过 + 调度装配冒烟**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/test_due_reminder.py -q && python -c "from app.tasks.scheduler import build_scheduler; s=build_scheduler(); assert s.get_job('due_reminder') is not None; print('ok')"`
Expected: PASS（5 passed）+ `ok`

- [ ] **Step 6: 提交**
```bash
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP" && git add backend/app/tasks/due_reminder.py backend/app/tasks/scheduler.py backend/tests/unit/test_due_reminder.py
git diff --cached --name-only
git commit -m "$(printf 'feat(phase-5a): add due-reminder & low-stock scheduler tick (edge-armed)\n\nCo-Authored-By: Claude Opus 4.5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 11: 全量回归 + ruff + 收尾

**Files:** 无新增（仅验证）

- [ ] **Step 1: 清缓存跑全量测试，tee 到唯一文件**

```bash
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP/backend" && source .venv/bin/activate
find . -name __pycache__ -type d -exec rm -rf {} + ; rm -rf .pytest_cache
PYTHONDONTWRITEBYTECODE=1 pytest -q 2>&1 | tee /tmp/p5a_fullrun_$(date +%s).txt | tail -5
```
Expected: 末行 `N passed`（N ≥ 1040 + 本期新增；0 failed）。Read tee 文件确认真实摘要行。

- [ ] **Step 2: ruff 静态检查（仅本期文件）**

```bash
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP/backend" && source .venv/bin/activate
ruff check app/models/notification.py app/services/notification_service.py app/schemas/notification.py app/routers/notifications.py app/tasks/due_reminder.py
```
Expected: `All checks passed!`（若报未用 import/变量等，用 Edit 精确修正后重跑）。

- [ ] **Step 3: alembic 单 head + Atlas 扫描 + 工作树**

```bash
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP/backend" && source .venv/bin/activate && alembic heads
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP" && grep -ric atlas backend/app/models/notification.py backend/app/services/notification_service.py backend/app/routers/notifications.py backend/app/tasks/due_reminder.py backend/app/schemas/notification.py
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP" && git log --oneline -12
```
Expected: `alembic heads` 单 head `phase5a_notification`；Atlas 计数全 0；提交链含 Task 1–10。

> 注：`git status --porcelain` 可能显示其他会话遗留的游离改动（非本期）；只需确认**本期文件**均已提交，勿提交非本期改动。

---

## 完成标准（Definition of Done）

- 全量 pytest 0 failed（含通知模型/service/事件/schema 单测 + API 测 + 各内联挂钩测 + due_reminder tick 测 + config 测）。
- `/api/v1/notifications` feed（分页/过滤）+ 未读数 + 标记单条/全部已读工作；仅本人可见可改；跨租户隔离正确（聚合只见本租户）。
- 9 个事件类型按设计 §4 生成；内联事件与领域动作同事务原子；自抑制触发者本人。
- 到期提醒/低库存边沿触发各一次、改期/回升 re-arm；调度器注册 `due_reminder` job。
- ruff 干净；clean-room 无 "Atlas"；接收人按权限解析复用 `effective_codes`。
- alembic 单 head 推进为 `phase5a_notification`（本期 +2 表 +1 迁移），未修改任何既有领域模型字段。
