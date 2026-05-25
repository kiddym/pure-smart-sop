# 内容块降为步骤级（并入 step 表）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把「内容块」从章节表（`tb_procedure_chapter.content_type='content'`）迁到步骤表，成为 `ProcedureStep` 的一个种类（`kind='content'`），与步骤同级、可在同一章节下按 `sort_order` 交替；章节表删除 `content_type`/`rich_content`。

**Architecture:** 严格互斥（选项3）——一个章节要么放子章节、要么放叶子项（步骤+内容块），二者不混；故任一章节的孩子都来自单一表，无需跨表归并。内容块不编号、无标题、只有富文本（复用 `step.content`）。内容块↔步骤互转 = 客户端翻 `kind` 随批量保存提交。Word 导入新增一次「归一化」把「标题下正文+子标题」混合结构里的正文下沉为相邻子标题的内容块。执行运行时本期未实现（Q264），无影响。

**Tech Stack:** 后端 FastAPI + SQLAlchemy + Alembic + pytest（内存 SQLite，`backend/tests`，Factory 夹具）。前端 Vue3 + Pinia + Element Plus + vitest（`frontend/tests/unit`，`*.spec.ts`）。

**两大里程碑（按序）：**
- **Part A — 后端**：模型→迁移→编号→保存/校验→导入归一化→标记/转换→PDF→schema/路由/服务清理。完成判据：`cd backend && pytest` 全绿。
- **Part B — 前端**：类型→utils→store→详情面板→树/面板组件→层级标定→周边触点→api 清理。完成判据：`cd frontend && npm run typecheck && npm test` 全绿。

**命令速查：**
- 后端单测：`cd backend && pytest tests/unit/services/test_xxx.py::test_name -v`
- 后端迁移：`cd backend && alembic upgrade head` / `alembic downgrade -1`
- 前端单测：`cd frontend && npm test -- tests/unit/xxx.spec.ts`
- 前端类型：`cd frontend && npm run typecheck`

---

# Part A — 后端

## Task A1: `step.kind` 列 + 章节表瘦身（模型）

**Files:**
- Modify: `backend/app/models/step.py`
- Modify: `backend/app/models/chapter.py`

- [ ] **Step 1: 给 ProcedureStep 加 `kind` 列**

`step.py`：在 `attachment_marks` 之后、`procedure` 关系之前加：

```python
    # step / content（内容块=只有富文本的步骤，Q-content-as-step）
    kind: Mapped[str] = mapped_column(String(20), default="step", server_default="step")
```

在 `__table_args__` 末尾追加索引：

```python
        Index("ix_tb_procedure_step_kind", "kind"),
```

- [ ] **Step 2: 章节表删除 `content_type` / `rich_content`**

`chapter.py`：删除这两列定义（`content_type` 第 31-33 行、`rich_content` 第 35 行），并删除 `__table_args__` 里的 `Index("ix_tb_procedure_chapter_content_type", "content_type")`。更新类 docstring 为「章节节点（纯标题/分组容器）」。`mark_status`、`conversion_status`、`level`、`code`、`skip_numbering` 保留。

- [ ] **Step 3: 提交**

```bash
git add backend/app/models/step.py backend/app/models/chapter.py
git commit -m "feat(model): add step.kind; drop chapter content_type/rich_content"
```

> 说明：单测用 `Base.metadata.create_all()` 直接建表（不过迁移），故模型改完单测库即新结构。生产/开发库由 Task A2 迁移。

---

## Task A2: Alembic 迁移（加列、删列、1:1 数据搬运）

**Files:**
- Create: `backend/alembic/versions/20260526_0001_content_block_as_step.py`

- [ ] **Step 1: 写迁移文件**

```python
"""content block as step-level node

把 tb_procedure_chapter.content_type='content' 行搬到 tb_procedure_step
(kind='content')；step 加 kind 列；chapter 删 content_type/rich_content。
开发数据可重建，数据搬运为尽力而为的 1:1 直搬。
"""
from __future__ import annotations

import uuid
from datetime import datetime

import sqlalchemy as sa
from alembic import op

revision: str = "content_block_as_step"
down_revision: str | None = "drop_step_require_confirmation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tb_procedure_step",
        sa.Column("kind", sa.String(length=20), nullable=False, server_default="step"),
    )
    op.create_index("ix_tb_procedure_step_kind", "tb_procedure_step", ["kind"])

    bind = op.get_bind()
    now = datetime.utcnow()
    rows = bind.execute(
        sa.text(
            "SELECT id, procedure_id, parent_id, rich_content, sort_order, "
            "skip_numbering, is_active, deleted_at "
            "FROM tb_procedure_chapter WHERE content_type = 'content'"
        )
    ).fetchall()
    for r in rows:
        bind.execute(
            sa.text(
                "INSERT INTO tb_procedure_step "
                "(id, procedure_id, chapter_id, kind, title, code, content, "
                " sort_order, skip_numbering, input_schema, attachment_marks, "
                " is_active, deleted_at, created_at, updated_at) "
                "VALUES (:id, :pid, :cid, 'content', '', '', :content, :sort, "
                " :skip, '{}', '[]', :active, :deleted_at, :now, :now)"
            ),
            {
                "id": str(uuid.uuid4()),
                "pid": r.procedure_id,
                "cid": r.parent_id,
                "content": r.rich_content or "",
                "sort": r.sort_order,
                "skip": r.skip_numbering,
                "active": r.is_active,
                "deleted_at": r.deleted_at,
                "now": now,
            },
        )
    bind.execute(sa.text("DELETE FROM tb_procedure_chapter WHERE content_type = 'content'"))

    op.drop_index("ix_tb_procedure_chapter_content_type", table_name="tb_procedure_chapter")
    op.drop_column("tb_procedure_chapter", "content_type")
    op.drop_column("tb_procedure_chapter", "rich_content")


def downgrade() -> None:
    op.add_column(
        "tb_procedure_chapter",
        sa.Column("content_type", sa.String(length=20), nullable=False, server_default="chapter"),
    )
    op.add_column(
        "tb_procedure_chapter",
        sa.Column("rich_content", sa.Text(), nullable=False, server_default=""),
    )
    op.create_index(
        "ix_tb_procedure_chapter_content_type", "tb_procedure_chapter", ["content_type"]
    )

    bind = op.get_bind()
    now = datetime.utcnow()
    rows = bind.execute(
        sa.text(
            "SELECT id, procedure_id, chapter_id, content, sort_order, skip_numbering, "
            "is_active, deleted_at FROM tb_procedure_step WHERE kind = 'content'"
        )
    ).fetchall()
    for r in rows:
        bind.execute(
            sa.text(
                "INSERT INTO tb_procedure_chapter "
                "(id, procedure_id, parent_id, content_type, title, code, rich_content, "
                " sort_order, level, mark_status, skip_numbering, conversion_status, "
                " is_active, deleted_at, created_at, updated_at) "
                "VALUES (:id, :pid, :cid, 'content', '', '', :content, :sort, 1, "
                " 'unmarked', :skip, 'applied', :active, :deleted_at, :now, :now)"
            ),
            {
                "id": str(uuid.uuid4()),
                "pid": r.procedure_id,
                "cid": r.chapter_id,
                "content": r.content or "",
                "sort": r.sort_order,
                "skip": r.skip_numbering,
                "active": r.is_active,
                "deleted_at": r.deleted_at,
                "now": now,
            },
        )
    bind.execute(sa.text("DELETE FROM tb_procedure_step WHERE kind = 'content'"))

    op.drop_index("ix_tb_procedure_step_kind", table_name="tb_procedure_step")
    op.drop_column("tb_procedure_step", "kind")
```

> 验证 `down_revision`：`cd backend && alembic heads` 应输出 `drop_step_require_confirmation`。若不同，改为实际 head。`level`/`mark_status`/`conversion_status` 的列名以 `chapter.py` 实际为准（参见模型）。

- [ ] **Step 2: 跑迁移验证可上可下**

```bash
cd backend && alembic upgrade head && alembic downgrade -1 && alembic upgrade head
```
Expected: 三步均无报错。

- [ ] **Step 3: 提交**

```bash
git add backend/alembic/versions/20260526_0001_content_block_as_step.py
git commit -m "feat(migration): move content blocks to step table (kind=content)"
```

---

## Task A3: schema 调整（`schemas/node.py`）

**Files:**
- Modify: `backend/app/schemas/node.py`

- [ ] **Step 1: 删 `ContentType`、章节 content 字段；step 系列加 `kind`**

1. 删除 `ContentType = Literal["chapter", "content"]`（第 13 行）。`MarkStatus` 保留。
2. `ChapterCreate`：删 `content_type`、`rich_content` 字段。
3. `ChapterUpdate`：删 `rich_content` 字段（只剩 `title`、`skip_numbering`）。
4. `ChapterUpsert`：删 `content_type`、`rich_content`。
5. `ChapterOut`、`ChapterTreeNode`：删 `content_type`、`rich_content`。
6. `StepCreate`、`StepUpdate`、`StepUpsert`、`StepOut`：各加一行
   ```python
   kind: Literal["step", "content"] = "step"
   ```
   （`StepOut` 用于 `from_attributes`，读模型的 `kind`。）
7. 删 `BatchContentToStepsIn`（content-to-steps 端点将移除，Task A8）。
8. 顶部 `from typing import Any, Literal` 保留（`Literal` 仍用）。

- [ ] **Step 2: 提交**

```bash
git add backend/app/schemas/node.py
git commit -m "refactor(schema): drop ContentType/chapter content fields; add step.kind"
```

---

## Task A4: 编号引擎跳过内容块（TDD）

**Files:**
- Modify: `backend/app/services/numbering_service.py`
- Test: `backend/tests/unit/services/test_numbering_service.py`

- [ ] **Step 1: 写失败测试**

`test_numbering_service.py` 追加（沿用文件内 `_proc` helper）：

```python
def test_content_step_unnumbered_and_not_counted(db: Session, factory: Factory) -> None:
    pid = _proc(factory)
    ch = factory.chapter(pid, title="操作", sort_order=0, level=1)
    s1 = factory.step(pid, chapter_id=ch.id, title="第一步", sort_order=0)
    c = factory.step(pid, chapter_id=ch.id, content="<p>说明</p>", sort_order=1, kind="content")
    s2 = factory.step(pid, chapter_id=ch.id, title="第二步", sort_order=2)
    numbering_service.recompute(db, pid)
    for s in (s1, c, s2):
        db.refresh(s)
    assert s1.code == "1.1"
    assert c.code == ""        # 内容块不编号
    assert s2.code == "1.2"    # 内容块不占序号位
```

> 需要 `Factory.step` 支持 `kind` 参数 —— 见 Task A4 Step 3 同步更新 conftest。

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && pytest tests/unit/services/test_numbering_service.py::test_content_step_unnumbered_and_not_counted -v`
Expected: FAIL（`Factory.step` 暂无 `kind`，或 content 步骤被编号）。

- [ ] **Step 3: 给 Factory.step 加 `kind`**

`backend/tests/conftest.py` 的 `Factory.step` 签名加 `kind: str = "step"`，并在构造 `ProcedureStep(...)` 时传 `kind=kind`。

- [ ] **Step 4: 改 numbering_service**

`number_steps` 跳过内容块：
```python
    def number_steps(chapter_id: str | None, prefix: str, silent: bool) -> None:
        seq = 0
        for st in steps_by_chapter.get(chapter_id, []):
            if silent or st.skip_numbering or st.kind == "content":
                st.code = ""
                continue
            seq += 1
            st.code = f"{prefix}.{seq}" if prefix else str(seq)
```

`number_chapters` 删除 `content_type == "content"` 分支（章节不再有 content）：
```python
    def number_chapters(parent_id: str | None, parent_code: str, silent: bool) -> None:
        seq = 0
        for ch in children.get(parent_id, []):
            if silent or ch.skip_numbering:
                ch.code = ""
                number_chapters(ch.id, "", True)
                number_steps(ch.id, "", True)
                continue
            seq += 1
            code = f"{parent_code}.{seq}" if parent_code else str(seq)
            ch.code = code
            number_chapters(ch.id, code, False)
            number_steps(ch.id, code, False)
```
更新模块 docstring 把「content：永远 code=''」一句改为针对 `step.kind=='content'`。

- [ ] **Step 5: 跑测试确认通过 + 全文件回归**

Run: `cd backend && pytest tests/unit/services/test_numbering_service.py -v`
Expected: 新测试 PASS；其余原 content（章节）相关测试若失败，按新模型改用 `factory.step(..., kind="content")` 重建数据。

- [ ] **Step 6: 提交**

```bash
git add backend/app/services/numbering_service.py backend/tests/conftest.py backend/tests/unit/services/test_numbering_service.py
git commit -m "feat(numbering): content-kind steps unnumbered and not counted"
```

---

## Task A5: 保存校验 Q25 重写（TDD）

**Files:**
- Modify: `backend/app/services/editor_service.py`
- Test: `backend/tests/unit/services/test_editor_service.py`

- [ ] **Step 1: 写失败测试**

`test_editor_service.py` 追加（沿用文件内 `_proc` / `_save` helper）：

```python
def test_step_and_content_coexist_under_chapter(db: Session, factory: Factory) -> None:
    proc = _proc(factory)
    _, id_map = _save(
        db, proc, 0,
        chapters=[ChapterUpsert(id="c1", title="操作", sort_order=0)],
        steps=[
            StepUpsert(id="s1", chapter_id="c1", title="做X", kind="step", sort_order=0),
            StepUpsert(id="c2", chapter_id="c1", content="<p>注</p>", kind="content", sort_order=1),
            StepUpsert(id="s2", chapter_id="c1", title="做Y", kind="step", sort_order=2),
        ],
    )
    assert set(id_map) == {"c1", "s1", "c2", "s2"}


def test_chapter_with_subchapter_cannot_hold_step(db: Session, factory: Factory) -> None:
    proc = _proc(factory)
    with pytest.raises(Exception):  # SIBLING_TYPE_CONFLICT
        _save(
            db, proc, 0,
            chapters=[
                ChapterUpsert(id="c1", title="父", sort_order=0),
                ChapterUpsert(id="c2", parent_id="c1", title="子", sort_order=0),
            ],
            steps=[StepUpsert(id="s1", chapter_id="c1", title="混入", kind="step", sort_order=1)],
        )
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && pytest tests/unit/services/test_editor_service.py::test_step_and_content_coexist_under_chapter -v`
Expected: FAIL（`StepUpsert` 暂无 `kind` / 校验逻辑旧）。

- [ ] **Step 3: 改 `_validate_and_recompute_levels`**

- 父引用校验去掉 `content_type` 判定（章节都是容器）：
  ```python
    for ch in chapters:
        if ch.parent_id is not None and chapter_by_id.get(ch.parent_id) is None:
            raise bad_request("SIBLING_TYPE_CONFLICT", "章节的父节点无效")
    for st in steps:
        if st.chapter_id is not None and chapter_by_id.get(st.chapter_id) is None:
            raise bad_request("SIBLING_TYPE_CONFLICT", "步骤所属章节无效")
  ```
- Q25 保留（步骤含两种 kind）：`if by_parent.get(pid) and steps_by_chapter.get(pid): raise SIBLING_TYPE_CONFLICT(...)`。
- 删除「content 强制叶子」整段。
- 深度校验 `walk` 去掉 `content_type == "chapter"` 条件：
  ```python
    def walk(parent_id: str | None, level: int) -> None:
        for ch in sorted(by_parent.get(parent_id, []), key=lambda c: (c.sort_order, c.id)):
            if level > MAX_DEPTH:
                raise bad_request("CHAPTER_DEPTH_EXCEEDED", f"章节嵌套不能超过 {MAX_DEPTH} 级")
            ch.level = level
            visited.add(ch.id)
            walk(ch.id, level + 1)
  ```

- [ ] **Step 4: 改 `save_procedure` 的 upsert**

章节 upsert 去掉 content 字段处理：
```python
    for cu in data.chapters:
        ch_node = existing_chapters.get(cu.id)
        if ch_node is None:
            ch_node = ProcedureChapter(id=id_map[cu.id], procedure_id=proc.id)
            db.add(ch_node)
        ch_node.parent_id = resolve(cu.parent_id)
        ch_node.title = cu.title
        ch_node.skip_numbering = cu.skip_numbering
        ch_node.sort_order = cu.sort_order
```

步骤 upsert 处理 kind（内容块清空表单/标题/附件、跳过表单型校验、仍做 5MB 校验）：
```python
    for su in data.steps:
        if su.kind == "step" and su.input_schema.get("type") not in FORM_TYPES:
            raise unprocessable("VALIDATION_FAILED", "无效的执行表单类型", field="input_schema.type")
        _content_size_guard(su.content, "步骤正文超过 5 MB 上限")
        st_node = existing_steps.get(su.id)
        if st_node is None:
            st_node = ProcedureStep(id=id_map[su.id], procedure_id=proc.id)
            db.add(st_node)
        is_content = su.kind == "content"
        st_node.chapter_id = resolve(su.chapter_id)
        st_node.kind = su.kind
        st_node.title = "" if is_content else su.title
        st_node.content = su.content
        st_node.input_schema = {} if is_content else su.input_schema
        st_node.attachment_marks = [] if is_content else su.attachment_marks
        st_node.skip_numbering = su.skip_numbering
        st_node.sort_order = su.sort_order
```
更新模块 docstring：把「content 强制叶子、chapter rich_content 恒空」换成「Q25 章节∕叶子项互斥；内容块=kind='content' 步骤」。

- [ ] **Step 5: 跑测试确认通过 + 文件回归**

Run: `cd backend && pytest tests/unit/services/test_editor_service.py -v`
Expected: 新测试 PASS。旧测试里用 `ChapterUpsert(content_type="content", rich_content=...)` 的，改写为 `StepUpsert(kind="content", content=...)` 并调整断言。

- [ ] **Step 6: 提交**

```bash
git add backend/app/services/editor_service.py backend/tests/unit/services/test_editor_service.py
git commit -m "feat(save): Q25 rewrite — steps+content coexist; drop chapter content handling"
```

---

## Task A6: 导入映射 + 归一化（TDD）

**Files:**
- Modify: `backend/app/services/import_service.py`
- Test: `backend/tests/unit/services/test_import_service.py`（新建；或并入既有 `test_parse_service.py`）

- [ ] **Step 1: 写失败测试**

新建 `backend/tests/unit/services/test_import_service.py`：

```python
import pytest
from sqlalchemy.orm import Session

from app.deps import RequestMeta
from app.models.chapter import ProcedureChapter
from app.models.step import ProcedureStep
from app.schemas.parse import ImportNodeIn
from app.services import import_service
from tests.conftest import Factory

META = RequestMeta(actor_id="u1", actor_name="U", request_id="r1", ip="127.0.0.1")


def _leaf(factory: Factory) -> str:
    leaf = factory.folder(name="叶子", prefix="QC", full_path="叶子")
    factory.sequence(leaf.id)
    return leaf.id


def test_content_node_imported_as_content_step(db: Session, factory: Factory, storage_tmp) -> None:
    proc = import_service.import_procedure(
        db, name="P", folder_id=_leaf(factory), description="",
        chapters=[ImportNodeIn(title="操作", content_type="chapter", children=[
            ImportNodeIn(content_type="content", rich_content="<p>正文</p>"),
        ])],
        meta=META,
    )
    steps = db.query(ProcedureStep).filter_by(procedure_id=proc.id, is_active=True).all()
    assert len(steps) == 1
    assert steps[0].kind == "content"
    assert steps[0].content == "<p>正文</p>"


def test_import_normalizes_intro_text_under_grouping_heading(db: Session, factory: Factory, storage_tmp) -> None:
    # 「1 引言」下：正文A + 子标题1.1 —— 正文A 必须下沉为 1.1 的前置内容块
    proc = import_service.import_procedure(
        db, name="P", folder_id=_leaf(factory), description="",
        chapters=[ImportNodeIn(title="引言", content_type="chapter", children=[
            ImportNodeIn(content_type="content", rich_content="<p>A</p>"),
            ImportNodeIn(title="子节", content_type="chapter", children=[
                ImportNodeIn(content_type="content", rich_content="<p>B</p>"),
            ]),
        ])],
        meta=META,
    )
    intro = db.query(ProcedureChapter).filter_by(procedure_id=proc.id, title="引言").one()
    sub = db.query(ProcedureChapter).filter_by(procedure_id=proc.id, title="子节").one()
    # 引言 直接挂的 step 为 0（A 已下沉）；子节 下有 2 个内容块（A 前置 + B）
    assert db.query(ProcedureStep).filter_by(chapter_id=intro.id, is_active=True).count() == 0
    contents = (
        db.query(ProcedureStep)
        .filter_by(chapter_id=sub.id, is_active=True)
        .order_by(ProcedureStep.sort_order)
        .all()
    )
    assert [c.content for c in contents] == ["<p>A</p>", "<p>B</p>"]
```

- [ ] **Step 2: 跑确认失败**

Run: `cd backend && pytest tests/unit/services/test_import_service.py -v`
Expected: FAIL（content 仍建成章节行 / 无归一化）。

- [ ] **Step 3: 加归一化 + 改 `_create_node`**

`import_service.py` 顶部 import `ProcedureStep`。在 `import_procedure` 的创建循环前加一行 `_normalize_for_exclusion(chapters)`：

```python
    _normalize_for_exclusion(chapters)
    for i, node in enumerate(chapters):
        _create_node(db, proc, node, parent_id=None, parent_level=0, sort_order=i)
```

新增归一化（自顶向下，正文下沉进相邻子标题；终止性由「内容只向下挪一级、深度≤3」保证）：

```python
def _normalize_for_exclusion(nodes: list[ImportNodeIn]) -> None:
    """保证每个标题节点的直接孩子要么全是子标题、要么全是正文（严格互斥）。
    标题下若同时有正文与子标题，正文下沉为相邻子标题的前置/后置内容块。"""
    for n in nodes:
        _relocate_stray_content(n)
        _normalize_for_exclusion(n.children)


def _relocate_stray_content(node: ImportNodeIn) -> None:
    children = node.children
    if not any(c.content_type == "chapter" for c in children):
        return  # 叶子（纯正文）或纯分组：合法
    new_children: list[ImportNodeIn] = []
    pending_leading: list[ImportNodeIn] = []
    last_chapter: ImportNodeIn | None = None
    for c in children:
        if c.content_type == "chapter":
            if pending_leading:
                c.children = pending_leading + c.children
                pending_leading = []
            new_children.append(c)
            last_chapter = c
        elif last_chapter is None:
            pending_leading.append(c)        # 第一个子标题之前的正文 → 前置
        else:
            last_chapter.children.append(c)   # 某子标题之后的正文 → 该子标题后置
    node.children = new_children
```

改 `_create_node`：content 节点建步骤，chapter 节点建章节行（去掉 content_type/rich_content 字段）：

```python
def _create_node(db, proc, node, *, parent_id, parent_level, sort_order):
    if node.content_type == "content":
        content = _promote_temp_urls(db, proc.id, node.rich_content)
        step = ProcedureStep(
            procedure_id=proc.id,
            chapter_id=parent_id,
            kind="content",
            title="",
            content=content,
            input_schema={},
            attachment_marks=[],
            sort_order=sort_order,
            skip_numbering=node.skip_numbering,
        )
        db.add(step)
        db.flush()
        return
    level = parent_level + 1
    row = ProcedureChapter(
        procedure_id=proc.id,
        parent_id=parent_id,
        title=node.title,
        level=level,
        sort_order=sort_order,
        skip_numbering=node.skip_numbering,
        mark_status="review" if node.mark_status == "review" else "unmarked",
    )
    db.add(row)
    db.flush()
    for j, child in enumerate(node.children):
        _create_node(db, proc, child, parent_id=row.id, parent_level=level, sort_order=j)
```

> 归一化在导入期静默执行（导入无 warning 返回通道；用户随后在编辑器复核结构）。

- [ ] **Step 4: 跑确认通过 + 集成回归**

Run: `cd backend && pytest tests/unit/services/test_import_service.py tests/integration/test_word_import.py -v`
Expected: PASS。集成测试若断言了旧的 content 章节结构，按新模型（content→step）更新断言。

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/import_service.py backend/tests/unit/services/test_import_service.py
git commit -m "feat(import): content nodes -> content-kind steps; normalize mixed headings"
```

---

## Task A7: apply-marks 重写（TDD）

**Files:**
- Modify: `backend/app/services/mark_service.py`
- Test: `backend/tests/unit/services/test_mark_service.py`

- [ ] **Step 1: 写失败测试**

`test_mark_service.py` 追加：

```python
def test_mark_chapter_as_step_creates_step_kind(db: Session, factory: Factory) -> None:
    proc = _proc(factory)
    ch = _chapter(db, proc.id, title="其实是步骤")
    mark_service.set_mark_status(db, ch.id, "step", META)
    result = mark_service.apply_marks(db, proc.id, META)
    assert len(result.created) == 1
    st = db.query(ProcedureStep).filter_by(id=result.created[0]).one()
    assert st.kind == "step" and st.title == "其实是步骤"


def test_mark_chapter_as_content_creates_content_kind(db: Session, factory: Factory) -> None:
    proc = _proc(factory)
    ch = _chapter(db, proc.id, title="其实是正文")
    mark_service.set_mark_status(db, ch.id, "content", META)
    result = mark_service.apply_marks(db, proc.id, META)
    st = db.query(ProcedureStep).filter_by(id=result.created[0]).one()
    assert st.kind == "content" and "其实是正文" in st.content
```

> `_chapter` helper 在该文件已有；建 chapter 时不再传 `ct`/`rich`（章节无这些字段了），旧用例需相应改写或迁到 import/save 测试。

- [ ] **Step 2: 跑确认失败**

Run: `cd backend && pytest tests/unit/services/test_mark_service.py::test_mark_chapter_as_content_creates_content_kind -v`
Expected: FAIL。

- [ ] **Step 3: 重写 `apply_marks`**

去掉 `from app.services.conversion_service import split_top_level_blocks`。重写执行段（标记目标含 step 与 content；都建步骤，按 kind 区分；都要求叶子）：

```python
    marked = list(db.execute(select(ProcedureChapter).where(
        ProcedureChapter.procedure_id == proc.id,
        ProcedureChapter.is_active.is_(True),
        ProcedureChapter.mark_status.in_(["step", "content"]),
    )).scalars())
    targets = [n for n in marked if n.mark_status in ("step", "content")]

    # 1. 叶子校验：含子节点的章节不能转
    for n in targets:
        if _has_children(db, n.id):
            raise bad_request("CHAPTER_HAS_CHILDREN", f"章节「{n.title}」含子节点，不能转换")

    # 2. 最终态互斥：某 parent 下若有转换，其余未转章节必须为空（否则 chapter+step 混）
    target_ids = {n.id for n in targets}
    for parent_id in {n.parent_id for n in targets}:
        remaining = [c for c in _active_children(db, proc.id, parent_id) if c.id not in target_ids]
        if remaining:
            raise bad_request("SIBLING_TYPE_CONFLICT", "同级仍有未转换的章节，应用会违反互斥规则")

    # 3. 执行
    created, deleted = [], []
    now = utcnow()
    by_parent: dict[str | None, list[ProcedureChapter]] = {}
    for n in targets:
        by_parent.setdefault(n.parent_id, []).append(n)
    for parent_id, nodes in by_parent.items():
        nodes.sort(key=lambda c: (c.sort_order, c.id))
        for seq, n in enumerate(nodes):
            if n.mark_status == "step":
                step = ProcedureStep(
                    procedure_id=proc.id, chapter_id=parent_id, kind="step",
                    title=n.title, content="", input_schema={"type": "COMMON"}, sort_order=seq,
                )
                action = "convert-to-step"
            else:  # content
                body = f"<p>{_escape(n.title)}</p>" if n.title.strip() else ""
                step = ProcedureStep(
                    procedure_id=proc.id, chapter_id=parent_id, kind="content",
                    title="", content=body, input_schema={}, sort_order=seq,
                )
                action = "mark-to-content"
            db.add(step); db.flush()
            created.append(step.id)
            _audit(db, proc, target_id=step.id, action=action, meta=meta, old_value={"chapter_id": n.id})
            n.is_active = False
            n.deleted_at = now
            deleted.append(n.id)

    for n in marked:
        if n.is_active:
            n.mark_status = "unmarked"
```

文件内加最小转义工具：
```python
def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
```
更新模块 docstring 的映射表（chapter→step / chapter→content 都建步骤；删 content 拆分行）。

- [ ] **Step 4: 跑确认通过 + 文件回归**

Run: `cd backend && pytest tests/unit/services/test_mark_service.py -v`
Expected: 新测试 PASS。旧的「content 章节标 step 拆分」用例删除或改为 import+save 路径。

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/mark_service.py backend/tests/unit/services/test_mark_service.py
git commit -m "feat(marks): chapter step/content marks both create steps (by kind)"
```

---

## Task A8: 转换服务与路由清理（TDD）

**Files:**
- Modify: `backend/app/services/conversion_service.py`
- Modify: `backend/app/routers/chapters.py`、`backend/app/routers/steps.py`（按需）
- Test: `backend/tests/unit/services/test_conversion_service.py`、`backend/tests/integration/`（按需）

- [ ] **Step 1: 删除内容块拆分相关；调整章节↔步骤转换**

`conversion_service.py`：
- 删除 `_content_to_steps_core`、`content_to_steps`、`batch_content_to_steps`、`convert_to_content`。
- 保留 `split_top_level_blocks`（独立工具 + 其测试不动）。
- `_convert_chapter_to_step_core`：删 `if ch.content_type != "chapter"` 这行（章节都是容器）；建步骤显式 `kind="step"`。
- `convert_to_chapter`（step→chapter）：把 step 正文落成新章节下的**内容块步骤**而非 content 章节子节点：
  ```python
      body = st.content
      created = [chapter.id]
      if body.strip():
          content_step = ProcedureStep(
              procedure_id=proc.id, chapter_id=chapter.id, kind="content",
              title="", content=body, input_schema={}, sort_order=0,
          )
          db.add(content_step); db.flush()
          created.append(content_step.id)
  ```
  并删去新建 `ProcedureChapter` 时的 `content_type="chapter"`、`rich_content=""` 入参。

- [ ] **Step 2: 删路由与 schema 引用**

- `routers/chapters.py`：删 `content-to-steps`、`batch-content-to-steps` 两个路由及其 import；保留 `convert-to-step`、`convert-root-to-step`、`mark-status`。删 `convert-to-content` 路由（若存在）。
- `routers/steps.py`：`convert-to-chapter` 路由保留。
- 确认 `schemas/node.py` 的 `BatchContentToStepsIn` 已在 Task A3 删除，移除其在路由的 import。

- [ ] **Step 3: 跑确认 + 回归**

Run: `cd backend && pytest tests/unit/services/test_conversion_service.py -v`
Expected: `split_top_level_blocks` 测试仍 PASS；引用已删函数的用例删除或改写。再跑相关集成测试。

- [ ] **Step 4: 提交**

```bash
git add backend/app/services/conversion_service.py backend/app/routers/chapters.py backend/app/routers/steps.py backend/tests/unit/services/test_conversion_service.py
git commit -m "refactor(convert): drop content-to-steps; step->chapter body to content step"
```

---

## Task A9: PDF 渲染交替（TDD）

**Files:**
- Modify: `backend/app/services/pdf/context.py`
- Modify: `backend/app/services/pdf/sections.py`
- Test: `backend/tests/unit/services/pdf/test_context.py`、`test_sections.py`（或 `test_engine.py`）

- [ ] **Step 1: 写失败测试**

`test_sections.py`（或新增）断言：内容块步骤与普通步骤按 `sort_order` 交替进入 flowables，内容块无编号无标题。建议用现有 `_render_chapter`/`build_content` 直接渲染一个含 `[step, content-step, step]` 的 ChapterData，断言产物顺序与内容块渲染走 `render_html`。（参照 `test_engine.py` 的 `_rich_proc` 建数据方式，把 content 改为 `factory.step(..., kind="content", content=...)`。）

- [ ] **Step 2: 改 `context.py`**

- `StepData` 加 `kind: str` 字段；`_to_step` 传 `kind=s.kind`。
- `ChapterData` 删 `content_type`、`rich_content`；`build_chapter` 去掉这两个入参（`children` 现仅子章节）。
- 预取资源 `htmls`：去掉 `[c.rich_content for c in chapters]`，仅 `htmls = [s.content for s in steps]`（内容块步骤已在 steps 中）。

- [ ] **Step 3: 改 `sections.py`**

- `display_code(code, level, skip)` 去掉 `content_type` 参数与 `content_type == "content"` 分支；所有调用处（`build_toc`、`toc_chapters`、`_render_chapter`）相应更新。
- `toc_chapters`、`_find_attachment_chapter`、`_next_attachment_number`：去掉 `n.content_type == "chapter"` 条件（章节都是 chapter）。
- `_render_chapter`：删 `if ch.content_type == "content"` 分支（章节不再有 content）。
- `_render_step` 顶部按 kind 分流：
  ```python
  def _render_step(st: StepData, data: RenderData, out: list[Flowable]) -> None:
      if st.kind == "content":
          out.extend(render_html(st.content, data.assets, base_style="content"))
          return
      ...  # 原有 step 渲染
  ```

- [ ] **Step 4: 跑确认通过 + PDF 测试回归**

Run: `cd backend && pytest tests/unit/services/pdf -v`
Expected: PASS；旧的 content 章节渲染用例改为内容块步骤。

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/pdf/context.py backend/app/services/pdf/sections.py backend/tests/unit/services/pdf
git commit -m "feat(pdf): render content-kind steps inline, interleaved with steps"
```

---

## Task A10: 章节/步骤 CRUD 服务清理 + 后端全绿

**Files:**
- Modify: `backend/app/services/chapter_service.py`、`backend/app/services/step_service.py`（按引用）
- Modify: 任何仍引用 `content_type`/`rich_content` 的后端文件

- [ ] **Step 1: 全仓搜剩余引用**

```bash
cd backend && grep -rn "content_type\|rich_content\|BatchContentToSteps\|content_to_steps\|convert_to_content" app
```
对每处：`chapter_service.create_chapter`/`update_chapter` 去掉 content 字段写入；`step_service.create_step`/`update_step` 加 `kind` 透传；输出装配（如有 ChapterTreeNode 组装）去掉 content 字段。

- [ ] **Step 2: 后端全量测试**

Run: `cd backend && pytest`
Expected: 全绿。逐个修复残留用例（多为把 content 章节夹具改为内容块步骤）。

- [ ] **Step 3: 提交**

```bash
git add -A backend
git commit -m "chore(backend): purge content_type/rich_content references; pytest green"
```

---

# Part B — 前端

## Task B1: 类型调整（`types/node.ts` + `types/parse.ts`）

**Files:**
- Modify: `frontend/src/types/node.ts`
- Modify: `frontend/src/types/parse.ts`

- [ ] **Step 1: 改 `types/node.ts`**

- 删 `export type ContentType`。
- `EditorChapter`、`ChapterTreeNode`、`ChapterOut`、`ChapterUpsert`：删 `content_type`、`rich_content`。
- `EditorStep`、`StepOut`、`StepUpsert`：加 `kind: 'step' | 'content'`。
- `NodeKind`（`'chapter' | 'content' | 'step'`）保留。
- 删 `ChapterUpdate` 等里 `rich_content`（如有）。

- [ ] **Step 2: 改 `types/parse.ts`**

`ImportNodeIn`（前端镜像）保留 `content_type`/`rich_content`（解析侧分类不变）；如有引用 `ContentType` 改为 `'chapter' | 'content'` 字面量。

- [ ] **Step 3: 提交**（类型改完会让大量文件报错，后续任务逐个修复；本步只提交类型）

```bash
git add frontend/src/types/node.ts frontend/src/types/parse.ts
git commit -m "refactor(types): drop ContentType/chapter content fields; add step.kind"
```

---

## Task B2: 编号镜像与 Q25（`utils/editor.ts`，TDD）

**Files:**
- Modify: `frontend/src/utils/editor.ts`
- Test: `frontend/tests/unit/editorNumbering.spec.ts`、`frontend/tests/unit/editorUtils.spec.ts`

- [ ] **Step 1: 写失败测试**

`editorUtils.spec.ts` 的 `getAddButtonState` 用例改为新规则：
```typescript
it('已有 content → 不能加章节，但能加 step/content', () => {
  expect(getAddButtonState(['content'])).toEqual({
    canAddChapter: false, canAddContent: true, canAddStep: true,
  })
})
it('已有 chapter → 不能加 step/content', () => {
  expect(getAddButtonState(['chapter'])).toEqual({
    canAddChapter: true, canAddContent: false, canAddStep: false,
  })
})
```
`editorNumbering.spec.ts` 改「content 不占位」用例为内容块步骤：
```typescript
it('内容块步骤无号、不占步骤序号位', () => {
  const { stepCodes } = recomputeCodes(
    [ch('a', null, 0)],
    [st('s1', 'a', 0), stc('c', 'a', 1), st('s2', 'a', 2)],
  )
  expect(stepCodes.get('s1')).toBe('1.1')
  expect(stepCodes.get('c')).toBe('')
  expect(stepCodes.get('s2')).toBe('1.2')
})
```
（`st`/`ch` helper 去掉 content_type；新增 `stc` = `st` 但 `kind:'content'`。）

- [ ] **Step 2: 跑确认失败**

Run: `cd frontend && npm test -- tests/unit/editorUtils.spec.ts tests/unit/editorNumbering.spec.ts`
Expected: FAIL。

- [ ] **Step 3: 改 `utils/editor.ts`**

`getAddButtonState`：
```typescript
export function getAddButtonState(childKinds: NodeKind[]): AddButtonState {
  const types = new Set(childKinds)
  return {
    canAddChapter: !types.has('step') && !types.has('content'),
    canAddContent: !types.has('chapter'),
    canAddStep: !types.has('chapter'),
  }
}
```
`recomputeCodes`：`numberSteps` 跳过内容块；`numberChapters` 去掉 `content_type==='content'` 分支：
```typescript
  function numberSteps(chapterId, prefix, silent) {
    let seq = 0
    for (const st of stepsByChapter.get(chapterId) ?? []) {
      if (silent || st.skip_numbering || st.kind === 'content') { stepCodes.set(st.id, ''); continue }
      seq += 1
      stepCodes.set(st.id, prefix ? `${prefix}.${seq}` : String(seq))
    }
  }
  function numberChapters(parentId, parentCode, silent) {
    let seq = 0
    for (const ch of children.get(parentId) ?? []) {
      if (silent || ch.skip_numbering) {
        chapterCodes.set(ch.id, ''); numberChapters(ch.id, '', true); numberSteps(ch.id, '', true); continue
      }
      seq += 1
      const code = parentCode ? `${parentCode}.${seq}` : String(seq)
      chapterCodes.set(ch.id, code); numberChapters(ch.id, code, false); numberSteps(ch.id, code, false)
    }
  }
```
`formatCode`：开头加 `if (params.kind === 'content') return ''`。`computeFallback`：`'content'` 分支保留。

- [ ] **Step 4: 跑确认通过；提交**

Run: `cd frontend && npm test -- tests/unit/editorUtils.spec.ts tests/unit/editorNumbering.spec.ts`
```bash
git add frontend/src/utils/editor.ts frontend/tests/unit/editorUtils.spec.ts frontend/tests/unit/editorNumbering.spec.ts
git commit -m "feat(editor-utils): Q25 new rule; content-kind steps unnumbered"
```

---

## Task B3: Store 改造（`store/procedureEditor.ts`，TDD）

**Files:**
- Modify: `frontend/src/store/procedureEditor.ts`
- Test: `frontend/tests/unit/procedureEditorStore.spec.ts`

- [ ] **Step 1: 写失败测试**

追加：
```typescript
describe('内容块=步骤 kind', () => {
  it('addStepNode 可建 content kind 并置脏', () => {
    const store = useProcedureEditorStore(); store.procedure = meta()
    store.chapters = [chapter('c1', '操作', null, 0)]; store.steps = []
    const id = store.addStepNode('c1', null, 'content')
    const st = store.stepMap.get(id)!
    expect(st.kind).toBe('content')
    expect(store.dirtySteps.has(id)).toBe(true)
  })
  it('setStepKind 翻转 kind 并置脏', () => {
    const store = useProcedureEditorStore(); store.procedure = meta()
    store.steps = [{ id: 's1', chapter_id: 'c1', title: 'x', content: '', kind: 'step',
      input_schema: { type: 'COMMON' }, attachment_marks: [], skip_numbering: false, sort_order: 0 }]
    store.setStepKind('s1', 'content')
    expect(store.stepMap.get('s1')!.kind).toBe('content')
    expect(store.dirtySteps.has('s1')).toBe(true)
  })
  it('flatRows 把 content 步骤渲染为 content 行', () => {
    const store = useProcedureEditorStore(); store.procedure = meta()
    store.chapters = [chapter('c1', '操作', null, 0)]; store.expanded = { c1: true }
    store.steps = [{ id: 'k', chapter_id: 'c1', title: '', content: '<p>x</p>', kind: 'content',
      input_schema: {}, attachment_marks: [], skip_numbering: false, sort_order: 0 }]
    const row = store.flatRows.find((r) => r.id === 'k')!
    expect(row.kind).toBe('content')
    expect(row.code).toBe('')
  })
})
```
（`chapter()` helper 去掉 `content_type`/`rich_content`；store 测试 mock 里 `@/api/chapters` 移除 `contentToSteps`。）

- [ ] **Step 2: 跑确认失败**；然后改 store

主要改动：
- import 去掉 `ContentType`、`contentToSteps as contentToStepsApi`；保留 `convertChapterToStep`、`convertRootToStep`、`setChapterMarkStatus`、`convertStepToChapter`。
- `emptyStep(chapterId, sortOrder, kind='step')` 加 `kind` 入参并写入返回对象。
- `ingestStep`：加 `kind: s.kind`。
- `ingestChapters`：去掉 `content_type`/`rich_content`。
- `childKindsOf`：步骤按 kind 归类：
  ```typescript
  for (const s of this.steps) if (s.chapter_id === parentId) kinds.push(s.kind === 'content' ? 'content' : 'step')
  ```
  （章节循环只 push `'chapter'`。）
- `flatRows`：章节循环 `kind = 'chapter'`；步骤循环 `kind: st.kind === 'content' ? 'content' : 'step'`，`code` 用 `formatCode({ kind, level: 0, code: stepCodes.get(st.id) ?? '', skipNumbering: st.skip_numbering })`，`form_type: st.kind === 'content' ? null : (st.input_schema?.type ?? 'COMMON')`，`fallback: computeFallback(st.kind === 'content' ? 'content' : 'step', st.content)`。`has_children`/`expanded` 仍 false。
- `expandAll`：`for (const c of this.chapters) next[c.id] = true`（章节都是容器）。
- `missingTitleCount`、`validateForSave`：空标题只数章节（`this.chapters`，不再过滤 content_type）；oversize 改为 `this.steps`（含 content）按 `content` 字节，章节不再有正文。
- `layerRows`/`chapterDocRows`：去 `content_type`（见 Task B6 层级标定，可能改为只含章节）。本步先让其编译（章节 content_type 恒 'chapter'）。
- 删 `toggleContentType`、`promoteContentToChapter`、`contentToSteps` action。
- 新增 `addStepNode(chapterId, afterId=null, kind='step')`：构造 `emptyStep(chapterId, ..., kind)`；其余逻辑不变。
- 新增 `setStepKind(id, kind)`：`pushUndo()`；翻 `st.kind`；若转 content 则清空 `input_schema={}`/`attachment_marks=[]`/`title=''`，若转 step 则 `input_schema={type:'COMMON'}`；`dirtySteps.add(id)`。
- `convertToStep`/`convertRootToStep`/`convertToChapter`：保留（章节↔步骤后端转换）。
- `markedNodes`、`setMark`、`cycleMark`、`applyAllMarks`、`acceptReview`、`acceptAllReviews`：保留（仍作用于章节）。
- `buildPayload`：章节映射去 `content_type`/`rich_content`；步骤映射加 `kind: s.kind`。

- [ ] **Step 3: 跑确认通过 + store 测试回归；提交**

Run: `cd frontend && npm test -- tests/unit/procedureEditorStore.spec.ts`
```bash
git add frontend/src/store/procedureEditor.ts frontend/tests/unit/procedureEditorStore.spec.ts
git commit -m "feat(store): content blocks as content-kind steps; addStepNode(kind)/setStepKind"
```

---

## Task B4: 内容块详情面板（`ContentDetailPanel.vue` + 装配，TDD）

**Files:**
- Modify: `frontend/src/components/editor/ContentDetailPanel.vue`
- Modify: `frontend/src/views/procedures/ProcedureEditorView.vue`
- Test: `frontend/tests/unit/`（新增 `ContentDetailPanel.spec.ts`）

- [ ] **Step 1: 改 `ContentDetailPanel.vue` 绑定内容块步骤**

```vue
<script setup lang="ts">
import { computed } from 'vue'
import RichTextEditor from './RichTextEditor.vue'
import { useProcedureEditorStore } from '@/store/procedureEditor'

// 内容块详情：内容块=kind='content' 的步骤，仅富文本（无标题/表单/附件/review）。
const store = useProcedureEditorStore()
const content = computed(() => store.selectedStep)
const ro = computed(() => !store.editable)

function onChange(value: string): void {
  const id = content.value?.id
  if (id) store.updateStepFields(id, { content: value }, `content:${id}`)
}
</script>

<template>
  <div v-if="content" class="content-detail">
    <RichTextEditor
      :key="`${content.id}:${ro}`"
      :model-value="content.content"
      variant="full"
      :readonly="ro"
      :procedure-id="store.procedure?.id"
      placeholder="输入内容块正文…"
      @update:model-value="onChange"
    />
  </div>
</template>

<style scoped>
.content-detail { height: 100%; }
</style>
```
（移除原 review 横幅与 `acceptReview`、`selectedChapter`、`rich_content`。）

- [ ] **Step 2: 改 `ProcedureEditorView.vue` 的 kind 判定**

```typescript
const kind = computed<'chapter' | 'content' | 'step' | null>(() => {
  const sid = store.selectedId
  if (!sid) return null
  if (store.chapterMap.has(sid)) return 'chapter'
  const s = store.stepMap.get(sid)
  return s ? (s.kind === 'content' ? 'content' : 'step') : null
})
```
面板条件渲染（`ChapterDetailPanel`/`ContentDetailPanel`/`StepDetailPanel`）保持按 `kind` 分支不变。

- [ ] **Step 3: 写测试**

`ContentDetailPanel.spec.ts`：mount + 选中一个 content kind step，断言渲染 `RichTextEditor` 且 `model-value === step.content`，无「接受待确认」按钮。

- [ ] **Step 4: 跑通过；提交**

```bash
git add frontend/src/components/editor/ContentDetailPanel.vue frontend/src/views/procedures/ProcedureEditorView.vue frontend/tests/unit/ContentDetailPanel.spec.ts
git commit -m "feat(editor): ContentDetailPanel binds content-kind step (rich text only)"
```

---

## Task B5: 树行互转菜单 + 树面板新增（`TreeRow.vue` / `ChapterTreePanel.vue` / `ChapterDetailPanel.vue`，TDD）

**Files:**
- Modify: `frontend/src/components/editor/TreeRow.vue`
- Modify: `frontend/src/components/editor/ChapterTreePanel.vue`
- Modify: `frontend/src/components/editor/ChapterDetailPanel.vue`
- Test: `frontend/tests/unit/TreeRow.spec.ts`、`ChapterTreePanel.spec.ts`

- [ ] **Step 1: `TreeRow.vue` ⋮ 菜单加「内容块↔步骤」互转**

在 ⋮ 下拉的 `el-dropdown-menu` 内，删除项之外按行类型加互转项：
```vue
        <el-dropdown-item v-if="row.kind === 'content'" command="to-step">转为步骤</el-dropdown-item>
        <el-dropdown-item v-if="row.kind === 'step'" command="to-content">转为内容块</el-dropdown-item>
        <el-dropdown-item command="remove" divided>删除</el-dropdown-item>
```
保留现有 `remove` emit，**新增** `(e: 'convert', dir: 'to-step' | 'to-content'): void`。⋮ 的 `@command` 处理器改为分发：
```ts
function onMore(c: 'to-step' | 'to-content' | 'remove'): void {
  if (c === 'remove') emit('remove')
  else emit('convert', c)
}
```
模板 `<el-dropdown ... @command="onMore">`。`＋新增 ▾` 的 command 仍 `emit('add', c)`。（现有「⋮ → remove」测试不受影响：command='remove' 仍 emit('remove')。）

- [ ] **Step 2: `ChapterTreePanel.vue` 接线**

- `onAdd(kind)`：`kind==='content'` → `store.addStepNode(target.parentId, target.afterId, 'content')`；`kind==='step'` → `store.addStepNode(...,'step')`；`kind==='chapter'` → `store.addChapterNode(...)`。`addTargetFor` 对 content 行按「同父级、该行之后」（与 step 一致，用 `chapter_id`）。
- 处理 ⋮ 互转：`to-step` → `store.setStepKind(id,'step')`；`to-content` → `store.setStepKind(id,'content')`。
- 删除对 `store.contentToSteps`、`promoteContentToChapter`、`toggleContentType` 的任何引用。
- 标记模式 `applyBatch`/`cycleMark`：仍只作用于章节行（content 行现为 step，不显示 mark 复选框，TreeRow 模板 `v-if="markMode && row.kind !== 'step'"` 需改为 `row.kind === 'chapter'`）。

- [ ] **Step 3: `ChapterDetailPanel.vue` 去掉节点类型切换与「提升为章节」**

- 删「节点类型」`el-form-item`（chapter/content radio）与「提升为章节」按钮（`toggleContentType`/`promoteContentToChapter` 已不存在）。
- 保留 review 横幅（章节仍可能 review）、标题、跳号、子节点列表。子节点列表 `kind` 改为：章节 `'chapter'`，步骤 `s.kind==='content'?'content':'step'`，文本回退用 `computeFallback(kind, s.content)`。

- [ ] **Step 4: 测试**

- `TreeRow.spec.ts`：新增——content 行 ⋮ 菜单含「转为步骤」command（沿用 el-dropdown 约定：取末个 `ElDropdown`，`vm.$emit('command','to-step')`，断言组件 emit）。
- `ChapterTreePanel.spec.ts`：`onAdd('content')` 调 `addStepNode(...,'content')`；互转命令调 `setStepKind`。

- [ ] **Step 5: 跑通过；提交**

```bash
git add frontend/src/components/editor/TreeRow.vue frontend/src/components/editor/ChapterTreePanel.vue frontend/src/components/editor/ChapterDetailPanel.vue frontend/tests/unit/TreeRow.spec.ts frontend/tests/unit/ChapterTreePanel.spec.ts
git commit -m "feat(editor): add content blocks at step level; content<->step convert menu"
```

---

## Task B6: 层级标定适配（`utils/layerMark.ts` / `EditorLayerMarking.vue` / store `applyLayerRoles`，TDD）

**Files:**
- Modify: `frontend/src/utils/layerMark.ts`
- Modify: `frontend/src/store/procedureEditor.ts`（`layerRows`、`applyLayerRoles`）
- Modify: `frontend/src/components/editor/EditorLayerMarking.vue`
- Test: `frontend/tests/unit/`（layerMark 相关 spec）

- [ ] **Step 1: 明确新语义**

层级标定只列**章节**行（内容块现为步骤，不参与重排）。角色仍含 `content`：把某章节标 `content` = 在 `applyLayerRoles` 里**把该章节转成内容块步骤**（删章节、在解析出的父级下建 `kind='content'` 步骤，`content` 取该章节标题包成 `<p>…</p>`，类比 apply-marks 的 content 分支）。`chapter_1/2/3` 角色仍重排章节层级。

- [ ] **Step 2: 改 `layerMark.ts`**

`LayerRow` 去掉 `content_type` 字段（行恒为章节）；`defaultLayerRole(level)` 只按 level 给 `chapter_n`；`effectiveRole` 的 `hasStepChildren` 改为 `hasLeafChildren`（含步骤或内容块子 → 不可降 content）。`LayerUpdate` 删 `content_type`，**新增** `toContentStep: boolean`（role 为 `content` 时 `true`，表示该章节应转成内容块步骤；否则 `false` 表示仍是章节，按 `parent_id`/`sort_order` 重排）。保留纯函数测试覆盖。

- [ ] **Step 3: 改 store `layerRows` / `applyLayerRoles`**

- `layerRows`：只遍历 `this.chapters`，`hasLeafChildren = steps.some(s => s.chapter_id === c.id)`。
- `applyLayerRoles`：对 `content` 角色项——`removeNodeLocal(chapterId)` 后 `addStepNode(parentId, null, 'content')` 并写入标题正文；对 `chapter_n` 项——改 `parent_id`/`sort_order`（不再写 `content_type`）。置脏。

- [ ] **Step 4: 改 `EditorLayerMarking.vue`**

去掉对 `content_type` 的展示依赖；缩进用 `computeLayerIndents`（签名同步）。角色选择项文案保留「正文（内容块）」。

- [ ] **Step 5: 测试 + 跑通过；提交**

```bash
git add frontend/src/utils/layerMark.ts frontend/src/store/procedureEditor.ts frontend/src/components/editor/EditorLayerMarking.vue frontend/tests/unit/*layer*.spec.ts
git commit -m "feat(layer-marking): adapt to content-as-step model"
```

---

## Task B7: 周边触点 + api 清理 + 前端全绿

**Files:**
- Modify: `frontend/src/api/chapters.ts`、`frontend/src/api/steps.ts`
- Modify: `frontend/src/components/editor/PublishChecklistDialog.vue`
- Modify: `frontend/src/components/PdfPreview/pdfModel.ts`
- Modify: `frontend/src/utils/treeDnd.ts`
- Modify: 任何 `npm run typecheck` 报错的残留处

- [ ] **Step 1: api 清理**

`api/chapters.ts`：删 `contentToSteps`、`batchContentToSteps`。保留 `convertChapterToStep`、`convertRootToStep`、`setChapterMarkStatus`。`api/steps.ts`：`convertStepToChapter` 保留。

- [ ] **Step 2: 周边文件适配**

- `PublishChecklistDialog.vue`：若按 `content_type` 统计内容块，改为统计 `kind==='content'` 步骤。
- `pdfModel.ts`：PDF 预览前端模型去 `content_type`/`rich_content`，按 `kind` 渲染（与后端一致）。
- `treeDnd.ts`：拖拽落点合法性按新 Q25（章节∕叶子项互斥；步骤与内容块同属叶子项可同级）；内容块判定改 `kind==='content'`。

- [ ] **Step 3: 全量类型 + 测试**

```bash
cd frontend && grep -rn "content_type\|rich_content\|promoteContentToChapter\|contentToSteps\|toggleContentType" src
cd frontend && npm run typecheck && npm test
```
Expected: grep 仅剩 `types/parse.ts` 等解析侧合法引用；typecheck + 单测全绿。

- [ ] **Step 4: 提交**

```bash
git add -A frontend
git commit -m "chore(frontend): purge content-chapter refs; typecheck + tests green"
```

---

## Task B8: 端到端联调（手测）

- [ ] **Step 1:** 后端 + 前端起服务，导入一篇含「标题下正文+子标题」的 Word，确认正文下沉为相邻子标题的内容块、编号正确。
- [ ] **Step 2:** 编辑器里在一个章节下交替新增步骤与内容块，互转 kind，保存→刷新→PDF 预览，确认顺序、编号、内容块内联渲染一致。
- [ ] **Step 3:** 提交（如有手测中发现的小修）。

---

## 自查与风险

- **前后端编号必须等价**：`recomputeCodes`（B2）与 `numbering_service`（A4）对内容块跳过逻辑两端一致——各自单测锁定，B8 端到端再核。
- **迁移仅尽力而为**：开发数据可重建；生产前需在 MySQL test schema 跑 upgrade/downgrade。
- **导入归一化静默**：导入无 warning 通道，正文下沉不弹提示，用户在编辑器复核结构（可接受）。
- **顺序依赖**：Part A 必须先于 Part B（前端依赖 `StepOut.kind` 与 `ChapterOut` 去字段的契约）。Part A 内 A1→A2→A3 打底，A4–A10 可并行小步；Part B 内 B1 打底，B2–B7 顺序推进。
