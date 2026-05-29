# B4a — Node-Native Paths Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the two remaining legacy builders (import, version clone/delete) plus the metadata PUT, publish-gate, and asset-scan to read/write `ProcedureNode` directly — while the legacy chapter/step code stays present so the full suite stays green.

**Architecture:** TDD, one path at a time. Each task drives a red test, makes it green, commits. Legacy services/tables/endpoints are untouched (their unit tests keep passing), so after every commit `cd backend && .venv/bin/python -m pytest -q` is green. Spec: `docs/superpowers/specs/2026-05-29-unified-node-model-b4-contract-design.md` (§5).

**Tech Stack:** FastAPI, SQLAlchemy 2.0, Pydantic v2, pytest. Python interpreter: `backend/.venv/bin/python` (no `uv` on this host). Frontend type-check: `cd frontend && npx vue-tsc --noEmit`.

**Conventions:**
- All test commands run from `backend/`. Full suite: `.venv/bin/python -m pytest -q`. Single: `.venv/bin/python -m pytest <path>::<test> -v`.
- All commits end with the trailer `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>` (omitted from the command blocks below for brevity).
- `META = RequestMeta(ip_address="127.0.0.1", user_agent="pytest", request_id="r1")` — already a module constant in the touched test files; reuse it.

---

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `backend/app/services/node_service.py` | Node CRUD | Add 5 MB body-size guard |
| `backend/app/services/asset_service.py` | Asset ref tracking | Scan `ProcedureNode.body` |
| `backend/app/services/procedure_service.py` | Procedure CRUD + transitions | Publish-gate → node review; add `signoff_enabled` to `update_procedure` |
| `backend/app/services/import_service.py` | Word-import persistence | Build `ProcedureNode` directly |
| `backend/app/services/version_flow_service.py` | Version fork/clone/delete | Clone & delete via `ProcedureNode` |
| `backend/app/routers/procedures.py` | Procedure routes | Wire `PUT /{id}` → `update_procedure` |
| `frontend/src/api/procedures.ts` | API client | `updateProcedure` return type |

---

## Task 1: Content-size guard on node writes

**Files:**
- Modify: `backend/app/services/node_service.py`
- Test: `backend/tests/unit/services/test_node_service.py` (create if absent)

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/unit/services/test_node_service.py`:

```python
import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.services import node_service
from tests.conftest import Factory


def test_create_node_rejects_oversize_body(db: Session, factory: Factory) -> None:
    folder = factory.folder(prefix="QC")
    proc = factory.procedure(folder.id)
    big = "x" * (5 * 1024 * 1024 + 1)
    with pytest.raises(HTTPException) as exc:
        node_service.create_node(db, proc.id, {"body": big, "kind": "node"})
    assert exc.value.detail["code"] == "CONTENT_TOO_LARGE"
```

- [ ] **Step 2: Run it; verify it fails**

Run: `.venv/bin/python -m pytest tests/unit/services/test_node_service.py::test_create_node_rejects_oversize_body -v`
Expected: FAIL — node is created, no exception raised.

- [ ] **Step 3: Implement the guard**

In `backend/app/services/node_service.py`: add `payload_too_large` to the `app.errors` import, and add near the top (after `_SORT_GAP`):

```python
CONTENT_MAX_BYTES = 5 * 1024 * 1024


def _body_size_guard(body: str) -> None:
    if len(body.encode("utf-8")) > CONTENT_MAX_BYTES:
        raise payload_too_large("CONTENT_TOO_LARGE", "节点正文超过 5 MB 上限")
```

Update the import line `from app.errors import bad_request, not_found` → `from app.errors import bad_request, not_found, payload_too_large`.

In `create_node`, immediately after computing `kind`/`heading_level` (before `enforce_node_invariants`), add:
```python
    _body_size_guard(data.get("body", ""))
```
In `patch_node`, inside the loop guard region (after the `unknown` check), add:
```python
    if "body" in changes:
        _body_size_guard(changes["body"])
```
In `batch_update`, inside the per-node loop after the `unknown` check, add:
```python
        if "body" in changes:
            _body_size_guard(changes["body"])
```

- [ ] **Step 4: Run it; verify it passes**

Run: `.venv/bin/python -m pytest tests/unit/services/test_node_service.py -v`
Expected: PASS.

- [ ] **Step 5: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/node_service.py backend/tests/unit/services/test_node_service.py
git commit -m "feat(node_service): 5MB body-size guard on create/patch/batch (B4a)"
```

---

## Task 2: Asset scan reads node bodies

**Files:**
- Modify: `backend/app/services/asset_service.py:184-193`
- Test: `backend/tests/unit/services/test_asset_service.py` (create if absent)

- [ ] **Step 1: Write the failing test**

```python
from sqlalchemy.orm import Session

from app.services import asset_service
from tests.conftest import Factory


def test_scan_referenced_asset_ids_reads_node_bodies(
    db: Session, factory: Factory, monkeypatch
) -> None:
    folder = factory.folder(prefix="QC")
    proc = factory.procedure(folder.id)
    factory.node(proc.id, body="NODE_REF", sort_order=1000)
    factory.step(proc.id, content="STEP_REF")  # legacy row must now be ignored
    monkeypatch.setattr(asset_service, "extract_asset_ids", lambda s: {s} if s else set())
    ids = asset_service._scan_referenced_asset_ids(db, proc.id)
    assert ids == {"NODE_REF"}
```

- [ ] **Step 2: Run it; verify it fails**

Run: `.venv/bin/python -m pytest tests/unit/services/test_asset_service.py::test_scan_referenced_asset_ids_reads_node_bodies -v`
Expected: FAIL — returns `{"STEP_REF"}` (still scans `ProcedureStep.content`).

- [ ] **Step 3: Implement**

In `backend/app/services/asset_service.py` replace `_scan_referenced_asset_ids` (lines 184-193) with:

```python
def _scan_referenced_asset_ids(db: Session, procedure_id: str) -> set[str]:
    ids: set[str] = set()
    for (body,) in db.execute(
        select(ProcedureNode.body).where(
            ProcedureNode.procedure_id == procedure_id, ProcedureNode.is_active.is_(True)
        )
    ):
        ids |= extract_asset_ids(body)
    return ids
```

Add `from app.models.node import ProcedureNode` to the imports. Remove the `ProcedureStep` import **only if** it is now unused in the file (grep first: `grep -n ProcedureStep backend/app/services/asset_service.py`).

- [ ] **Step 4: Run it; verify it passes**

Run: `.venv/bin/python -m pytest tests/unit/services/test_asset_service.py -v`
Expected: PASS.

- [ ] **Step 5: Full suite + commit**

```bash
.venv/bin/python -m pytest -q   # expect green
git add backend/app/services/asset_service.py backend/tests/unit/services/test_asset_service.py
git commit -m "feat(asset_service): scan ProcedureNode.body for asset refs (B4a)"
```

---

## Task 3: Publish-gate counts review nodes

**Files:**
- Modify: `backend/app/services/procedure_service.py:305-317` (the `transition` PUBLISHED block)
- Test: `backend/tests/unit/services/test_procedure_service.py` (append; create if absent)

- [ ] **Step 1: Write the failing test**

```python
import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.deps import RequestMeta
from app.schemas.procedure import TransitionIn
from app.services import procedure_service
from tests.conftest import Factory

META = RequestMeta(ip_address="127.0.0.1", user_agent="pytest", request_id="r1")


def test_publish_blocked_by_review_node(db: Session, factory: Factory) -> None:
    folder = factory.folder(prefix="QC")
    proc = factory.procedure(folder.id, status="DRAFT", version=1, is_current=True)
    factory.node(proc.id, body="<p>x</p>", heading_level=1, mark_status="review", sort_order=1000)
    with pytest.raises(HTTPException) as exc:
        procedure_service.transition(
            db, proc.id, TransitionIn(status="PUBLISHED"), proc.revision, META
        )
    assert exc.value.detail["code"] == "REVIEW_PENDING"
```

- [ ] **Step 2: Run it; verify it fails**

Run: `.venv/bin/python -m pytest tests/unit/services/test_procedure_service.py::test_publish_blocked_by_review_node -v`
Expected: FAIL — gate counts review *chapters* (zero), so publish succeeds and no exception is raised.

- [ ] **Step 3: Implement**

In `backend/app/services/procedure_service.py`, add `from app.models.node import ProcedureNode` to the imports. Replace the pending-review query in `transition` (the block at lines 307-315 that uses `ProcedureChapter`) with:

```python
        pending = db.execute(
            select(func.count())
            .select_from(ProcedureNode)
            .where(
                ProcedureNode.procedure_id == proc.id,
                ProcedureNode.is_active.is_(True),
                ProcedureNode.mark_status == "review",
            )
        ).scalar_one()
```

(Leave the `if pending: raise bad_request("REVIEW_PENDING", ...)` line unchanged.)

- [ ] **Step 4: Run it; verify it passes**

Run: `.venv/bin/python -m pytest tests/unit/services/test_procedure_service.py::test_publish_blocked_by_review_node -v`
Expected: PASS.

- [ ] **Step 5: Full suite + commit**

```bash
.venv/bin/python -m pytest -q   # expect green
git add backend/app/services/procedure_service.py backend/tests/unit/services/test_procedure_service.py
git commit -m "feat(procedure_service): publish-gate counts review nodes not chapters (B4a)"
```

---

## Task 4: Import builds ProcedureNode directly

**Files:**
- Modify: `backend/app/services/import_service.py` (full rewrite of the build path)
- Test: `backend/tests/unit/services/test_import_service.py` (replace contents)
- Delete: `backend/tests/integration/test_node_import_dualwrite.py`

- [ ] **Step 1: Replace the test file**

Overwrite `backend/tests/unit/services/test_import_service.py` with:

```python
"""单元测试：import_service 直接落 ProcedureNode（B4a）。"""

from sqlalchemy.orm import Session

from app.deps import RequestMeta
from app.models.chapter import ProcedureChapter
from app.models.node import ProcedureNode
from app.models.step import ProcedureStep
from app.schemas.parse import ImportNodeIn
from app.services import import_service
from tests.conftest import Factory

META = RequestMeta(ip_address="127.0.0.1", user_agent="pytest", request_id="r1")


def _leaf(factory: Factory) -> str:
    leaf = factory.folder(name="叶子", prefix="QC", full_path="叶子")
    factory.sequence(leaf.id)
    return leaf.id


def test_import_builds_nodes_in_document_order(db: Session, factory: Factory, storage_tmp) -> None:
    # 「引言」下：正文A 然后 子标题「子节」（子节下含正文B）——不再下沉/归一化，保留文档序
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
    nodes = (
        db.query(ProcedureNode)
        .filter_by(procedure_id=proc.id, is_active=True)
        .order_by(ProcedureNode.sort_order)
        .all()
    )
    assert [(n.heading_level, n.kind, n.body) for n in nodes] == [
        (1, "node", "<p>引言</p>"),
        (None, "node", "<p>A</p>"),
        (2, "node", "<p>子节</p>"),
        (None, "node", "<p>B</p>"),
    ]
    # 不再建旧表行
    assert db.query(ProcedureChapter).filter_by(procedure_id=proc.id).count() == 0
    assert db.query(ProcedureStep).filter_by(procedure_id=proc.id).count() == 0


def test_import_carries_review_mark_on_heading(db: Session, factory: Factory, storage_tmp) -> None:
    proc = import_service.import_procedure(
        db, name="P", folder_id=_leaf(factory), description="",
        chapters=[ImportNodeIn(title="待审", content_type="chapter", mark_status="review")],
        meta=META,
    )
    n = db.query(ProcedureNode).filter_by(procedure_id=proc.id, is_active=True).one()
    assert n.mark_status == "review"
    assert n.heading_level == 1
    assert n.body == "<p>待审</p>"
```

- [ ] **Step 2: Run it; verify it fails**

Run: `.venv/bin/python -m pytest tests/unit/services/test_import_service.py -v`
Expected: FAIL — `test_import_builds_nodes_in_document_order` fails (legacy normalization reorders to `[引言, 子节, A, B]` and legacy rows exist).

- [ ] **Step 3: Rewrite `import_service`**

Overwrite `backend/app/services/import_service.py` with:

```python
"""导入编排（§9.1 / §19 / §25.2）。

把 /parse 返回（用户审查后）的 chapters[] 直接落成 ProcedureNode 行：前序展开导入树，
heading 节点 → heading_level=层级、body=<p>标题</p>；content 节点 → heading_level=None、
body=正文（临时图 URL 提升为永久 asset）。统一 gap 序赋 sort_order → node_numbering 重算 code
→ 重建 asset 引用 → 存源 docx。review 持久态随 heading 带入草稿。
"""

from __future__ import annotations

import html
import re

from sqlalchemy.orm import Session

from app.deps import RequestMeta
from app.errors import unprocessable
from app.models.node import ProcedureNode
from app.models.procedure import Procedure
from app.schemas.parse import ImportNodeIn
from app.schemas.procedure import LevelOfUse, ProcedureCreate
from app.services import asset_service, node_numbering, procedure_service, source_docx_service

_DEFAULT_LEVEL_OF_USE: LevelOfUse = "reference"
_TEMP_SRC_RE = re.compile(r'src="/api/v1/uploads/([^/"]+)/media/([^"]+)"')
_SORT_GAP = 1000


def _chapter_body(title: str) -> str:
    title = title.strip()
    return f"<p>{html.escape(title)}</p>" if title else ""


def import_procedure(
    db: Session,
    *,
    name: str,
    folder_id: str,
    description: str,
    chapters: list[ImportNodeIn],
    upload_token: str | None = None,
    meta: RequestMeta,
) -> Procedure:
    name = name.strip()
    if not name:
        raise unprocessable("VALIDATION_FAILED", "程序名不能为空", field="name")

    proc = procedure_service.create_procedure(
        db,
        ProcedureCreate(
            folder_id=folder_id,
            name=name,
            level_of_use=_DEFAULT_LEVEL_OF_USE,
            description=description,
        ),
        meta,
    )

    seq = 0

    def next_sort() -> int:
        nonlocal seq
        seq += 1
        return seq * _SORT_GAP

    def walk(nodes: list[ImportNodeIn], level: int) -> None:
        for n in nodes:
            if n.content_type == "content":
                db.add(
                    ProcedureNode(
                        procedure_id=proc.id,
                        sort_order=next_sort(),
                        heading_level=None,
                        kind="node",
                        body=_promote_temp_urls(db, proc.id, n.rich_content),
                        skip_numbering=n.skip_numbering,
                        mark_status="unmarked",
                    )
                )
            else:  # chapter（标题容器）
                db.add(
                    ProcedureNode(
                        procedure_id=proc.id,
                        sort_order=next_sort(),
                        heading_level=level,
                        kind="node",
                        body=_chapter_body(n.title),
                        skip_numbering=n.skip_numbering,
                        mark_status="review" if n.mark_status == "review" else "unmarked",
                    )
                )
                walk(n.children, level + 1)

    walk(chapters, 1)
    db.flush()
    node_numbering.recompute(db, proc.id)
    asset_service.rebuild_references(db, proc.id)
    source_docx_service.store_from_token(
        db, procedure_group_id=proc.procedure_group_id, upload_token=upload_token
    )
    db.flush()
    return proc


def _promote_temp_urls(db: Session, procedure_id: str, html_text: str) -> str:
    """把 rich_content 内临时图 URL 提升为永久 asset URL（sha256 去重）。"""

    def repl(match: re.Match[str]) -> str:
        token, filename = match.group(1), match.group(2)
        asset = asset_service.promote_temp(db, token, filename, source_meta={"docx_token": token})
        if asset is None:  # 临时图已过期/丢失：原样保留，降级不阻断导入
            return match.group(0)
        return f'src="{asset_service.asset_url(procedure_id, asset.id)}"'

    return _TEMP_SRC_RE.sub(repl, html_text)
```

- [ ] **Step 4: Run it; verify it passes**

Run: `.venv/bin/python -m pytest tests/unit/services/test_import_service.py -v`
Expected: PASS.

- [ ] **Step 5: Delete the obsolete dual-write integration test**

```bash
git rm backend/tests/integration/test_node_import_dualwrite.py
```

- [ ] **Step 6: Full suite + commit**

Run: `.venv/bin/python -m pytest -q`
Expected: green. (If any other test imports `import_service._create_node`/`_normalize_for_exclusion`, update it — those helpers no longer exist.)

```bash
git add backend/app/services/import_service.py backend/tests/unit/services/test_import_service.py
git commit -m "feat(import): build ProcedureNode directly from parse tree; drop legacy build + Q25 normalization (B4a)"
```

---

## Task 5: Version clone & group-delete go node-native

**Files:**
- Modify: `backend/app/services/version_flow_service.py` (`_clone_tree`, `delete_group`, imports/constants)
- Test: `backend/tests/unit/services/test_version_flow_service.py` (add 2 tests; update 2 existing)

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/unit/services/test_version_flow_service.py`:

```python
def test_clone_tree_copies_nodes(db: Session, factory: Factory) -> None:
    from app.models.node import ProcedureNode

    folder = _leaf(factory)
    src = factory.procedure(folder.id, code="QC-1")
    dst = factory.procedure(
        folder.id, code="QC-1", procedure_group_id=src.procedure_group_id,
        version=2, is_current=False,
    )
    factory.node(src.id, body="<p>章</p>", heading_level=1, sort_order=1000)
    factory.node(src.id, body="<p>正文</p>", heading_level=None, kind="node", sort_order=2000)

    version_flow_service._clone_tree(db, src.id, dst.id)

    cloned = (
        db.query(ProcedureNode)
        .filter_by(procedure_id=dst.id, is_active=True)
        .order_by(ProcedureNode.sort_order)
        .all()
    )
    assert [(n.heading_level, n.body) for n in cloned] == [(1, "<p>章</p>"), (None, "<p>正文</p>")]


def test_delete_group_removes_nodes(db: Session, factory: Factory) -> None:
    from app.models.node import ProcedureNode

    folder = _leaf(factory)
    proc = factory.procedure(folder.id, version=1, status="DRAFT", is_current=True)
    factory.node(proc.id, body="<p>章</p>", heading_level=1, sort_order=1000)
    factory.node(proc.id, body="<p>正文</p>", sort_order=2000)

    version_flow_service.delete_group(db, proc.procedure_group_id, "删", META)

    assert version_flow_service._group_records(db, proc.procedure_group_id) == []
    assert db.query(ProcedureNode).filter_by(procedure_id=proc.id).count() == 0
```

Also update the two existing legacy-clone tests:

In `test_upgrade_forks_new_draft`, replace `factory.chapter(proc.id, title="章A")` with `factory.node(proc.id, body="<p>章A</p>", heading_level=1, sort_order=1000)`, and replace the trailing `ProcedureChapter` block (the `from app.models.chapter import ProcedureChapter` and the `cloned` query/assert) with:
```python
    from app.models.node import ProcedureNode

    cloned = list(
        db.execute(
            ProcedureNode.__table__.select().where(ProcedureNode.procedure_id == new.id)
        )
    )
    assert len(cloned) == 1
```

In `test_copy_creates_new_group`, replace `factory.chapter(src.id, title="章")` with `factory.node(src.id, body="<p>章</p>", heading_level=1, sort_order=1000)`.

Delete `test_delete_group_topological_chapter_delete` entirely (the topological chapter delete no longer exists; `test_delete_group_removes_nodes` covers the node case).

- [ ] **Step 2: Run them; verify they fail**

Run: `.venv/bin/python -m pytest tests/unit/services/test_version_flow_service.py -v`
Expected: `test_clone_tree_copies_nodes` FAILS (dst has 0 nodes — legacy `_clone_tree` clones chapters/steps, not nodes), `test_delete_group_removes_nodes` FAILS (orphan nodes remain), `test_upgrade_forks_new_draft` FAILS.

- [ ] **Step 3: Rewrite `_clone_tree` and `delete_group`**

In `backend/app/services/version_flow_service.py`:

Replace the copy-field constants (`_CHAPTER_COPY`, `_STEP_COPY`) with:
```python
_NODE_COPY = (
    "sort_order",
    "heading_level",
    "kind",
    "body",
    "skip_numbering",
    "input_schema",
    "attachment_marks",
)
```

Replace `_clone_tree` with:
```python
def _clone_tree(db: Session, src_id: str, dst_id: str) -> None:
    """深拷贝 src 程序的 ProcedureNode 行到 dst（新 id；标记态重置；重算编号）。"""
    nodes = db.execute(
        select(ProcedureNode)
        .where(ProcedureNode.procedure_id == src_id, ProcedureNode.is_active.is_(True))
        .order_by(ProcedureNode.sort_order, ProcedureNode.id)
    ).scalars()
    for n in nodes:
        db.add(
            ProcedureNode(
                id=new_uuid(),
                procedure_id=dst_id,
                mark_status="unmarked",  # 标记态为编辑期瞬态，复制版重置干净
                **{f: getattr(n, f) for f in _NODE_COPY},
            )
        )
    db.flush()
    node_numbering.recompute(db, dst_id)
```

In `delete_group`, replace the legacy delete block — the `db.execute(delete(ProcedureStep)...)` line, the `rows = db.execute(select(ProcedureChapter.id, ...))` topological loop (through `remaining -= leaves`) — with:
```python
    db.execute(delete(ProcedureNode).where(ProcedureNode.procedure_id == proc.id))
```
Keep the `ProcedureAssetReference`, `ProcedureAttachment`, `source_docx_service.delete_for_group`, and `delete(Procedure)` lines that follow.

Imports: remove `from app.models.chapter import ProcedureChapter` and `from app.models.step import ProcedureStep`; replace `numbering_service` in the `app.services` import group with `node_numbering`; add `from app.models.node import ProcedureNode`. Then grep the file to confirm `numbering_service`, `ProcedureChapter`, `ProcedureStep` are no longer referenced: `grep -nE "numbering_service|ProcedureChapter|ProcedureStep" backend/app/services/version_flow_service.py` → expect no matches.

- [ ] **Step 4: Run the file; verify green**

Run: `.venv/bin/python -m pytest tests/unit/services/test_version_flow_service.py -v`
Expected: PASS (all, including the updated upgrade/copy tests and the attachment tests).

- [ ] **Step 5: Full suite + commit**

```bash
.venv/bin/python -m pytest -q   # expect green
git add backend/app/services/version_flow_service.py backend/tests/unit/services/test_version_flow_service.py
git commit -m "feat(version_flow): clone & delete_group via ProcedureNode (B4a)"
```

---

## Task 6: PUT /procedures/{id} → metadata-only

**Files:**
- Modify: `backend/app/services/procedure_service.py` (`update_procedure` — add `signoff_enabled`)
- Modify: `backend/app/routers/procedures.py:232-244` (the `save_procedure` handler)
- Test: `backend/tests/unit/services/test_procedure_service.py` (add unit test), `backend/tests/integration/test_editor.py` (replace structural-save tests with meta-only)

- [ ] **Step 1: Write the failing unit test (signoff)**

Append to `backend/tests/unit/services/test_procedure_service.py`:

```python
def test_update_procedure_persists_signoff_enabled(db: Session, factory: Factory) -> None:
    from app.schemas.procedure import ProcedureUpdate

    folder = factory.folder(prefix="QC")
    proc = factory.procedure(folder.id, status="DRAFT", is_current=True)
    procedure_service.update_procedure(
        db,
        proc.id,
        ProcedureUpdate(name="N", level_of_use="reference", signoff_enabled=True),
        proc.revision,
        META,
    )
    db.refresh(proc)
    assert proc.signoff_enabled is True
```

- [ ] **Step 2: Run it; verify it fails**

Run: `.venv/bin/python -m pytest tests/unit/services/test_procedure_service.py::test_update_procedure_persists_signoff_enabled -v`
Expected: FAIL — `signoff_enabled` stays `False` (update_procedure never assigns it).

- [ ] **Step 3: Add `signoff_enabled` to `update_procedure`**

In `backend/app/services/procedure_service.py` `update_procedure`: add `"signoff_enabled": proc.signoff_enabled,` to both the `before` and `after` diff dicts, add the assignment `proc.signoff_enabled = data.signoff_enabled` alongside the other field assignments (before `optimistic_lock.bump(proc)`).

- [ ] **Step 4: Run it; verify it passes**

Run: `.venv/bin/python -m pytest tests/unit/services/test_procedure_service.py::test_update_procedure_persists_signoff_enabled -v`
Expected: PASS.

- [ ] **Step 5: Write the failing integration test (PUT wiring)**

Replace the structural-save test(s) in `backend/tests/integration/test_editor.py` with a meta-only test (keep the file's existing imports/fixtures; if the file becomes empty of relevant tests, this is the only test):

```python
def test_put_procedure_updates_meta_only(client, factory) -> None:
    folder = factory.folder(prefix="QC")
    proc = factory.procedure(folder.id, status="DRAFT", is_current=True)
    resp = client.put(
        f"/api/v1/procedures/{proc.id}",
        headers={"If-Match": str(proc.revision)},
        json={"name": "新名", "level_of_use": "reference", "signoff_enabled": True},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "新名"
    assert body["signoff_enabled"] is True
    assert body["revision"] == proc.revision + 1
    assert "id_map" not in body


def test_put_procedure_rejects_non_draft(client, factory) -> None:
    folder = factory.folder(prefix="QC")
    proc = factory.procedure(folder.id, status="PUBLISHED", is_current=True)
    resp = client.put(
        f"/api/v1/procedures/{proc.id}",
        headers={"If-Match": str(proc.revision)},
        json={"name": "x", "level_of_use": "reference"},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "PROCEDURE_READONLY"
```

(Delete any remaining test in `test_editor.py` that posts `chapters`/`steps` to the PUT — that payload is no longer accepted.)

- [ ] **Step 6: Run it; verify it fails**

Run: `.venv/bin/python -m pytest tests/integration/test_editor.py -v`
Expected: FAIL — response still contains `id_map` (ProcedureSaveResult) and `signoff_enabled` is `False` (routes to `editor_service.save_procedure`).

- [ ] **Step 7: Rewire the PUT handler**

In `backend/app/routers/procedures.py` replace the `save_procedure` handler (lines 232-244) with:

```python
@router.put("/{procedure_id}", response_model=ProcedureMeta)
def update_procedure(
    procedure_id: str,
    payload: ProcedureUpdate,
    db: Session = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
    if_match: str | None = Header(default=None, alias="If-Match"),
) -> ProcedureMeta:
    """更新程序元数据（仅 is_current 且 DRAFT；结构改动走 /nodes 颗粒度端点）。"""
    expected = ensure_if_match(if_match)
    proc = procedure_service.update_procedure(db, procedure_id, payload, expected, meta)
    db.commit()
    return procedure_service.to_meta(db, proc)
```

Update the router imports: ensure `ProcedureUpdate` and `ProcedureMeta` are imported from `app.schemas.procedure`; remove `ProcedureSaveIn`, `ProcedureSaveResult`, and `editor_service` from the imports **iff** no longer used elsewhere in the file (grep: `grep -nE "ProcedureSaveIn|ProcedureSaveResult|editor_service" backend/app/routers/procedures.py`). `apply_marks`/`apply_layer_roles` remain for now (deleted in B4b).

- [ ] **Step 8: Run it; verify it passes**

Run: `.venv/bin/python -m pytest tests/integration/test_editor.py -v`
Expected: PASS.

- [ ] **Step 9: Full suite + commit**

```bash
.venv/bin/python -m pytest -q   # expect green
git add backend/app/services/procedure_service.py backend/app/routers/procedures.py backend/tests/unit/services/test_procedure_service.py backend/tests/integration/test_editor.py
git commit -m "feat(procedures): PUT /{id} is metadata-only via update_procedure; persist signoff_enabled (B4a)"
```

---

## Task 7: Frontend return-type alignment + final verification

**Files:**
- Modify: `frontend/src/api/procedures.ts` (`updateProcedure` return type, if needed)

- [ ] **Step 1: Check the frontend type**

Open `frontend/src/api/procedures.ts`, find `updateProcedure`. The PUT now returns `ProcedureMeta` (no `id_map`). If the declared return type names a save-result type or references `id_map`, change it to the metadata type already used for the GET-detail `procedure` field (see `frontend/src/types/procedure.ts`). The store consumes only `.revision`, so no logic change is needed.

- [ ] **Step 2: Type-check the frontend**

Run: `cd frontend && npx vue-tsc --noEmit`
Expected: no errors. If errors point at the response type, align it per Step 1 and re-run.

- [ ] **Step 3: Run frontend unit tests**

Run: `cd frontend && npm test`
Expected: green (302 passing baseline; no behavior change here).

- [ ] **Step 4: Commit (only if the file changed)**

```bash
git add frontend/src/api/procedures.ts
git commit -m "chore(fe): align updateProcedure return type to ProcedureMeta (B4a)"
```

- [ ] **Step 5: Manual smoke via the dev stack**

Per `.claude/skills/running-smartsop-dev`: launch backend + frontend, then drive with chrome-devtools MCP:
1. Import a Word doc through the wizard → confirm the new procedure opens in the node editor with the expected tree (headings + content in document order).
2. Edit metadata (name) in the editor → confirm it persists on reload (PUT path).
3. From the library, "复制为新程序" → confirm the copy opens with the same node tree.
4. Confirm zero console errors on `/edit` and `/view`.

- [ ] **Step 6: Final full suite**

Run (from `backend/`): `.venv/bin/python -m pytest -q`
Expected: all green.

- [ ] **Step 7: Finish the branch**

Use **superpowers:finishing-a-development-branch** to verify tests, present merge options, and complete.

---

## Self-Review Notes

- **Legacy stays green:** Tasks 1-6 never touch `chapter_service`/`step_service`/`conversion_service`/`mark_service`/`layer_apply_service`/`numbering_service`/`node_sync`/`editor_service`; their unit tests keep passing. `editor_service.save_procedure` becomes uncalled after Task 6 but still compiles (deleted in B4b).
- **Red-green integrity:** import (Task 4) and version (Task 5) are genuine red→green because the dual-write/clone for node-only procedures currently produces the *wrong* result (reordered nodes; zero cloned nodes), not merely an absent one.
- **`_promote_temp_urls` rename:** the rewrite renames the local `html` param to `html_text` to avoid shadowing the `import html` module — verify no other reference to the old name.
