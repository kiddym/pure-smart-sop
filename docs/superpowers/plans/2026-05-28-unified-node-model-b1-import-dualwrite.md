# 统一节点模型 Plan B1 — 导入双写 ProcedureNode 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 Word 导入在写 `ProcedureChapter`/`ProcedureStep` 的同时，把同一棵（已归一化的）导入树**并行落成 `ProcedureNode` 行**，使统一节点模型从导入侧开始有真实数据，且旧链路与运行中的 app 完全不受影响。

**Architecture:** 纯增量、双写（expand→migrate→contract 的 expand 阶段）。导入消费的是用户审查后的 `ImportNodeIn` 树（`content_type` + 嵌套深度），不是 `ParsedNode`，因此 B1 在 import 落库时**从该树派生** `heading_level`（chapter→深度、content→null），无需改 parser / `ParsedNode` / `ImportNodeIn` schema / 前端。新增一个纯函数把树前序展开为扁平行，import_service 负责图片 URL 提升 + 调 Plan A 的 `node_service.create_node` 落库。旧 chapter/step 写法一行不动；结构化 parser 扁平化（spec §5.1）与删旧写留给 B4。

**Tech Stack:** Python 3.11、FastAPI、SQLAlchemy 2.0、Pydantic v2、pytest + SQLite in-memory（conftest `Factory` + `client` 共享 StaticPool 引擎）。运行测试用 `backend/.venv/bin/python -m pytest`（本机无 uv，见 memory `uv-missing-use-venv-python`）。

**Spec:** `docs/superpowers/specs/2026-05-28-unified-node-model-design.md`（§5 parser/导入、§2 树派生、§1 模型）。

---

## 范围说明

**做（B1）：** 导入路径双写 `ProcedureNode`。spec §5.2「import 落库写 node 行」+ §2 派生语义在导入侧的体现。

**不做（留给后续阶段）：**
- **B2** — 下游读取切到 `ProcedureNode`（PDF / numbering / sign-off / editor / attachment，spec §7）。
- **B3** — 前端两面板 + 4 条输入路径 + 删 layerMark/标记模式 UI（spec §6）。
- **B4 contract** — 停双写、删 `ProcedureChapter`/`ProcedureStep.title`/`layer_apply_service`/`mark_service.apply_marks`/`chapter_service`、`structurer` 扁平化（spec §5.1）、删 import 的 `_normalize_for_exclusion`、重建 dev.db（spec §8/§9）。

### 调查得出的两点偏离（与 spec §5 措辞不同，已确认更小更安全）

1. **B1 不改 parser。** spec §5.1 写「`ParsedNode.content_type`→`heading_level`、`structurer` 产扁平 list」，那是删旧树路径（B4）才需要的终态。当前 import 消费的是 `ImportNodeIn` 树，B1 在 import 处从树派生 `heading_level` 即可，零 parser/schema/前端改动。把 §5.1 的 parser 扁平化挪到 B4。
2. **B1 无 seed 工作。** `backend/app/seed.py` 只 seed 系统文件夹/设置/示例字段，**不产 chapter/step 内容**，故无 procedure 内容可双写。spec §8「重写 seed 产 node」基于不成立的假设，删除该项。

### 关键设计点

- 导入树在 `import_procedure` 第 62 行 `_normalize_for_exclusion(chapters)` 处**就地归一化**（正文下沉至相邻子标题）。node 双写走**归一化之后**的同一棵 `chapters`，确保 node 结构与 chapter/step 行一致（B2 切下游读取时视觉不变）。
- chapter 的 `body` = 标题首段（spec §2.3）：把 plain `title` 包成 `<p>{escape(title)}</p>`；空标题 → 空 body（占位章节）。content 的 `body` = `rich_content` 原样（再过 `_promote_temp_urls` 提升临时图）。
- 导入只产 `kind='node'`（chapter 与 content 都是 node；表单 step 是后期人工升级，不来自导入）。
- `heading_level` 取导入树**嵌套深度**（根 chapter=1，其 chapter 子=2…），与旧 `_create_node` 的 `level=parent_level+1` 同义；content 恒 `None`。

---

## 文件结构

| 文件 | 职责 | 动作 |
|---|---|---|
| `backend/app/services/node_import.py` | `flatten_tree(chapters)` 纯函数：导入树→扁平 `FlatNode` 行 | 创建 |
| `backend/app/services/import_service.py` | 加 `_write_procedure_nodes`，在 `import_procedure` 里调用 | 修改 |
| `backend/tests/unit/services/test_node_import.py` | `flatten_tree` 单测 | 创建 |
| `backend/tests/integration/test_node_import_dualwrite.py` | 导入→`GET /nodes` 双写集成测试 | 创建 |

---

## Task 1: `flatten_tree` 纯函数（导入树 → 扁平行）

**Files:**
- Create: `backend/app/services/node_import.py`
- Test: `backend/tests/unit/services/test_node_import.py`

- [ ] **Step 1: 写失败测试**

Create `backend/tests/unit/services/test_node_import.py`:

```python
"""node_import.flatten_tree 单测（Plan B1 导入双写）。"""

from __future__ import annotations

from app.schemas.parse import ImportNodeIn
from app.services.node_import import FlatNode, flatten_tree


def _ch(title: str, children: list[ImportNodeIn] | None = None,
        mark_status: str = "unmarked", skip_numbering: bool = False) -> ImportNodeIn:
    return ImportNodeIn(
        title=title, content_type="chapter", children=children or [],
        mark_status=mark_status, skip_numbering=skip_numbering,
    )


def _co(rich: str, mark_status: str = "unmarked", skip_numbering: bool = False) -> ImportNodeIn:
    return ImportNodeIn(
        content_type="content", rich_content=rich,
        mark_status=mark_status, skip_numbering=skip_numbering,
    )


def test_flatten_preorder_and_levels() -> None:
    tree = [
        _ch("目的", [_co("<p>x</p>")]),
        _ch("职责", [_ch("质量部", [_co("<p>y</p>")])]),
    ]
    flat = flatten_tree(tree)
    assert [(f.heading_level, f.kind) for f in flat] == [
        (1, "node"), (None, "node"), (1, "node"), (2, "node"), (None, "node"),
    ]


def test_chapter_body_wraps_title() -> None:
    flat = flatten_tree([_ch("概述")])
    assert flat[0].body == "<p>概述</p>"


def test_empty_title_chapter_body_empty() -> None:
    flat = flatten_tree([_ch("   ")])
    assert flat[0].body == ""


def test_content_body_passthrough_and_level_none() -> None:
    flat = flatten_tree([_co("<p>原文<b>富</b></p>")])
    assert flat[0].body == "<p>原文<b>富</b></p>"
    assert flat[0].heading_level is None


def test_title_html_escaped() -> None:
    flat = flatten_tree([_ch("A & <B>")])
    assert flat[0].body == "<p>A &amp; &lt;B&gt;</p>"


def test_mark_status_and_skip_carried() -> None:
    flat = flatten_tree([_ch("待确认章", mark_status="review", skip_numbering=True)])
    assert flat[0].mark_status == "review"
    assert flat[0].skip_numbering is True


def test_dirty_mark_status_clamped_to_unmarked() -> None:
    flat = flatten_tree([_ch("章", mark_status="garbage")])
    assert flat[0].mark_status == "unmarked"
```

- [ ] **Step 2: 运行确认失败**

Run: `backend/.venv/bin/python -m pytest backend/tests/unit/services/test_node_import.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.node_import'`

- [ ] **Step 3: 实现**

Create `backend/app/services/node_import.py`:

```python
"""导入树 → ProcedureNode 扁平行（Plan B1 双写）。

把用户审查后的 `ImportNodeIn` 树（content_type + 嵌套深度）按文档顺序前序展开为
ProcedureNode 行的中间表示：chapter→heading_level=深度、content→heading_level=None，
全部 kind='node'。纯函数、不碰 DB；import_service 负责临时图 URL 提升与落库。
统一节点模型见 docs/superpowers/specs/2026-05-28-unified-node-model-design.md §5/§2。
"""

from __future__ import annotations

import html
from dataclasses import dataclass

from app.schemas.parse import ImportNodeIn


@dataclass
class FlatNode:
    """一行待落库的 ProcedureNode（body 为提升 URL 前的原始 HTML）。"""

    heading_level: int | None
    kind: str
    body: str
    mark_status: str
    skip_numbering: bool


def _chapter_body(title: str) -> str:
    """heading 的 body = 标题首段（spec §2.3）；空标题 → 空 body（占位章节）。"""
    title = title.strip()
    return f"<p>{html.escape(title)}</p>" if title else ""


def _clamp_mark_status(value: str) -> str:
    """统一模型 mark_status 只有 unmarked | review；脏值夹紧为 unmarked
    （沿用 import_service._create_node 的护栏语义）。"""
    return "review" if value == "review" else "unmarked"


def flatten_tree(chapters: list[ImportNodeIn]) -> list[FlatNode]:
    """前序展开为扁平行。chapters 应已过 import_service._normalize_for_exclusion。"""
    out: list[FlatNode] = []

    def walk(nodes: list[ImportNodeIn], level: int) -> None:
        for node in nodes:
            if node.content_type == "content":
                out.append(
                    FlatNode(
                        heading_level=None,
                        kind="node",
                        body=node.rich_content,
                        mark_status=_clamp_mark_status(node.mark_status),
                        skip_numbering=node.skip_numbering,
                    )
                )
                walk(node.children, level)  # content 一般无子；有也按同层处理
            else:
                out.append(
                    FlatNode(
                        heading_level=level,
                        kind="node",
                        body=_chapter_body(node.title),
                        mark_status=_clamp_mark_status(node.mark_status),
                        skip_numbering=node.skip_numbering,
                    )
                )
                walk(node.children, level + 1)

    walk(chapters, 1)
    return out
```

- [ ] **Step 4: 运行确认通过**

Run: `backend/.venv/bin/python -m pytest backend/tests/unit/services/test_node_import.py -v`
Expected: PASS（7 个）

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/node_import.py backend/tests/unit/services/test_node_import.py
git commit -m "feat(node_import): flatten_tree — import tree → ProcedureNode flat rows"
```

---

## Task 2: import_service 双写 ProcedureNode + 集成测试

**Files:**
- Modify: `backend/app/services/import_service.py`
- Test: `backend/tests/integration/test_node_import_dualwrite.py`

- [ ] **Step 1: 写失败测试**

Create `backend/tests/integration/test_node_import_dualwrite.py`:

```python
"""导入双写 ProcedureNode 集成测试（Plan B1）。

POST /procedures/import 写入用户审查后的树 → 既建旧 chapter/step，又建新
ProcedureNode 行；用 Plan A 的 GET /procedures/{id}/nodes 断言派生结构。
`client` 与导入共享同一 in-memory 引擎（conftest StaticPool）。
"""

from __future__ import annotations

from fastapi.testclient import TestClient

FOLDER = "/api/v1/folders"
IMPORT = "/api/v1/procedures/import"


def _leaf(client: TestClient, *, name: str = "B1夹", prefix: str = "B1") -> str:
    return client.post(FOLDER, json={"name": name, "prefix": prefix}).json()["id"]


def test_import_dualwrites_nodes(client: TestClient) -> None:
    leaf = _leaf(client)
    chapters = [
        {"title": "目的", "content_type": "chapter", "children": [
            {"content_type": "content", "rich_content": "<p>本程序规定...</p>"}]},
        {"title": "职责", "content_type": "chapter", "children": [
            {"title": "质量部", "content_type": "chapter", "children": [
                {"content_type": "content", "rich_content": "<p>归口管理</p>"}]}]},
    ]
    resp = client.post(
        IMPORT, json={"name": "记录控制程序", "folder_id": leaf, "chapters": chapters}
    )
    assert resp.status_code == 201, resp.text
    pid = resp.json()["id"]

    nodes = client.get(f"/api/v1/procedures/{pid}/nodes").json()
    assert [(n["heading_level"], n["body"], n["code"]) for n in nodes] == [
        (1, "<p>目的</p>", "1"),
        (None, "<p>本程序规定...</p>", ""),
        (1, "<p>职责</p>", "2"),
        (2, "<p>质量部</p>", "2.1"),
        (None, "<p>归口管理</p>", ""),
    ]
    # 派生父子（不存 parent_id，GET /nodes 返回派生值）
    assert nodes[0]["parent_id"] is None
    assert nodes[1]["parent_id"] == nodes[0]["id"]
    assert nodes[3]["parent_id"] == nodes[2]["id"]
    assert nodes[4]["parent_id"] == nodes[3]["id"]
    # sort_order 升序
    assert [n["sort_order"] for n in nodes] == sorted(n["sort_order"] for n in nodes)
    # 旧 chapter/step 路径仍在（双写并存）
    detail = client.get(f"/api/v1/procedures/{pid}").json()
    assert [c["title"] for c in detail["chapters"]] == ["目的", "职责"]


def test_import_carries_review_and_skip(client: TestClient) -> None:
    leaf = _leaf(client, name="B1夹2", prefix="B2")
    chapters = [
        {"title": "存疑章", "content_type": "chapter", "mark_status": "review",
         "skip_numbering": True, "children": [
            {"content_type": "content", "rich_content": "<p>z</p>"}]},
    ]
    resp = client.post(IMPORT, json={"name": "P2", "folder_id": leaf, "chapters": chapters})
    assert resp.status_code == 201, resp.text
    pid = resp.json()["id"]

    nodes = client.get(f"/api/v1/procedures/{pid}/nodes").json()
    head = nodes[0]
    assert head["heading_level"] == 1
    assert head["mark_status"] == "review"
    assert head["skip_numbering"] is True
    assert head["code"] == ""  # skip_numbering → 不编号
```

- [ ] **Step 2: 运行确认失败**

Run: `backend/.venv/bin/python -m pytest backend/tests/integration/test_node_import_dualwrite.py -v`
Expected: FAIL — 导入仍只写 chapter/step，`GET /nodes` 返回 `[]`，断言列表不相等（`AssertionError`，非 404/500）。

- [ ] **Step 3: 实现**

In `backend/app/services/import_service.py`, add `node_import` and `node_service` to the existing `from app.services import (...)` block (around line 22-28), so it reads:

```python
from app.services import (
    asset_service,
    editor_service,
    node_import,
    node_service,
    numbering_service,
    procedure_service,
    source_docx_service,
)
```

Then add this helper after `_create_node` (after line 149, before `_promote_temp_urls`):

```python
def _write_procedure_nodes(
    db: Session, proc: Procedure, chapters: list[ImportNodeIn]
) -> None:
    """Plan B1 双写：把同一棵（已归一化的）导入树落成统一 ProcedureNode 行。
    与 chapter/step 行并存；B2 切下游读取后、B4 删旧写。chapters 须已过
    _normalize_for_exclusion。body 复用 _promote_temp_urls 提升临时图（对
    chapter 的 <p>标题</p> 是 no-op）。create_node 顺序追加 → sort_order gap 序。"""
    for flat in node_import.flatten_tree(chapters):
        node_service.create_node(
            db,
            proc.id,
            {
                "body": _promote_temp_urls(db, proc.id, flat.body),
                "heading_level": flat.heading_level,
                "kind": flat.kind,
                "skip_numbering": flat.skip_numbering,
                "mark_status": flat.mark_status,
            },
        )
```

Then in `import_procedure`, insert the call right after the `_create_node` loop (after line 64), before the `editor_service._validate_and_recompute_levels` line:

```python
    _normalize_for_exclusion(chapters)
    for i, node in enumerate(chapters):
        _create_node(db, proc, node, parent_id=None, parent_level=0, sort_order=i)

    # Plan B1 双写：同一棵（已归一化）导入树并行落成统一 ProcedureNode 行。
    _write_procedure_nodes(db, proc, chapters)

    editor_service._validate_and_recompute_levels(db, proc.id)
    numbering_service.recompute(db, proc.id)
    asset_service.rebuild_references(db, proc.id)
    source_docx_service.store_from_token(db, procedure_group_id=proc.procedure_group_id, upload_token=upload_token)
    db.flush()
    return proc
```

注：`node_service.create_node`（Plan A）内部已 `enforce_node_invariants` + `db.flush` + `node_numbering.recompute`；顺序调用产出 `sort_order` 1000/2000/…（按 flatten 文档序）。最后一次 recompute 落定 node `code`。`_promote_temp_urls` 的 sha256 去重使「同一临时图被 step 路径与 node 路径各提升一次」幂等，返回同一 asset。

- [ ] **Step 4: 运行确认通过**

Run: `backend/.venv/bin/python -m pytest backend/tests/integration/test_node_import_dualwrite.py -v`
Expected: PASS（2 个）

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/import_service.py backend/tests/integration/test_node_import_dualwrite.py
git commit -m "feat(import): dual-write ProcedureNode rows from import tree (Plan B1)"
```

---

## Task 3: 全量回归 + mypy

**Files:** 无新增

- [ ] **Step 1: 跑全部后端测试**

Run: `cd backend && .venv/bin/python -m pytest -q`
Expected: 旧 Word 导入测试（`test_word_import.py`）**全部仍绿**（双写未动 chapter/step 写法）；新 B1 测试通过。基线 = 此前的 649 passed + 9 个新 B1 测试（7 unit + 2 integration）= 658 passed，仍有且仅有 1 个先存失败 `test_editor.py::test_create_chapter_and_nested_get`（与本计划无关，出范围）。

- [ ] **Step 2: 类型检查**

Run: `cd backend && .venv/bin/python -m mypy app/services/node_import.py app/services/import_service.py 2>&1 | tail -20`
Expected: 无 **新增** error（`node_import.py` 干净；`import_service.py` 若有先存 error 与本计划无关，逐条确认非新增）。

- [ ] **Step 3: Commit（若有修正）**

```bash
git add -A
git commit -m "chore: type fixes for Plan B1 import dual-write"
```

---

## 完成标准（B1）

1. 导入一棵审查后的树后，`GET /procedures/{id}/nodes` 返回与 chapter/step 一致的派生结构：chapter→`heading_level=深度`、content→`null`，body/编号/父子/排序正确。
2. `review`/`skip_numbering` 从导入树带进 `ProcedureNode`；脏 `mark_status` 夹紧为 `unmarked`。
3. 旧 `ProcedureChapter`/`ProcedureStep` 写法与所有旧导入测试**一行未动、全绿**（双写并存）。
4. parser / `ParsedNode` / `ImportNodeIn` schema / 前端 / seed **零改动**。

## 交接给 B2 的事实

- 导入后数据同时存在于 chapter/step 与 ProcedureNode 两套表（内容等价；node 的 body 对 chapter = `<p>标题</p>`、对 content = 原 rich_content）。
- B2 把 PDF/numbering/sign-off/editor/attachment 的读取从 chapter/step 切到 ProcedureNode（spec §7），切完 app 跑在 node 数据上；旧表仍被双写但不再被读。
- B1 未删 `_normalize_for_exclusion`、未改 parser；这些在 B4 contract 阶段随删旧写一起处理。
