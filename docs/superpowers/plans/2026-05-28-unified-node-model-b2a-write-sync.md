# 统一节点模型 Plan B2a — 双写补全（旧树 → ProcedureNode 全量重建）实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让**每一条**结构写入路径（导入、编辑器保存、章节/步骤颗粒度增删改/转换、版本 fork）都把当前旧 `ProcedureChapter`/`ProcedureStep` 树同步成统一 `ProcedureNode` 行，使 node 数据对**所有**程序（不止导入的）始终与旧树一致，为 B2b 把 PDF 读取切到 node 铺平道路。

**Architecture:** 新增纯重建函数 `node_sync.rebuild_from_legacy(procedure_id)`：硬删该程序现有 node 行 → 前序展开旧树 → 按文档序 gap 赋 `sort_order` 重插 → 重算 node `code`。因为**没有任何外键指向 node id**（B2 调查确认：签核是 procedure 级 bool、附件挂 procedure_id、版本 fork 重映射的是 chapter/step id——均不引用 node），全量重建安全。把它挂在 `numbering_service.recompute(db, procedure_id)` 末尾——这是**所有结构写入唯一汇聚点**（chapter_service / step_service / conversion_service / editor_service / import_service / version_flow_service / layer_apply_service / mark_service 全部在收尾调它），故一处 hook 覆盖全部路径。B1 仅覆盖导入的 `_write_procedure_nodes`/`flatten_tree` 就此被这条统一路径取代并删除。属 expand 阶段脚手架，B4 删旧表时连同 `numbering_service` 一并删除。

**Tech Stack:** Python 3.11、FastAPI、SQLAlchemy 2.0、Pydantic v2、pytest + SQLite in-memory（conftest `db`/`factory`/`client` 共享 StaticPool 引擎）。运行测试用 `backend/.venv/bin/python -m pytest`（本机无 uv，见 memory `uv-missing-use-venv-python`）。

**Spec:** `docs/superpowers/specs/2026-05-28-unified-node-model-design.md`（§2 树派生语义、§7 下游适配）。本计划是 Plan B「4 阶段渐进双写」的 **B2a**（B2 = 切下游读取；拆为 B2a 写补全 + B2b PDF 读切，见下）。

---

## 范围说明

**做（B2a）：** 把旧树→node 的双写从「仅导入」补全到「所有结构写入」。新增 `node_sync.rebuild_from_legacy` + 在 `numbering_service.recompute` 末尾挂一处 hook；删 B1 留下的、现已冗余的导入专用双写（`_write_procedure_nodes` + `node_import.py`）。

**不做（留给后续阶段）：**
- **B2b** — 把 PDF（`services/pdf/context.py:load_render_data`）从读 chapter/step 切到读 `ProcedureNode`，含「heading title 从 body 首段派生」（spec §2.3，B1/ B2a 都把章节标题存成 `body=<p>标题</p>`，B2b 渲染时反解出标题文本）。numbering 读取 = `node.code`（已由本阶段维护）。sign-off/attachment/version-read 经 B2 调查确认是 no-op。
- **B3** — 前端两面板 + 编辑器改读/写 `ProcedureNode`（届时编辑器**直接写 node**，本阶段给 editor_service 的重建脚手架随之退役）。
- **B4 contract** — 停双写、删 `ProcedureChapter`/`ProcedureStep`/`numbering_service`/`node_sync`/`layer_apply_service`/`mark_service.apply_marks`/`chapter_service`、parser 扁平化、重建 dev.db。

### 调查得出的关键事实（写本计划时用真实代码确认）

1. **node id 无入边外键。** 签核 = `Procedure.signoff_enabled`（bool，无 FK）；附件 = `ProcedureAttachment.procedure_id`（procedure 级，`attachment_marks` 是行内 JSON 不是 FK）；版本 fork `_clone_tree` 重映射的是 chapter/step id。⇒ node 行可**整程序硬删重建**，无引用会断。
2. **唯一汇聚点 = `numbering_service.recompute`。** 所有改旧结构的 service 收尾都调它（含 `version_flow_service._clone_tree` 第 177 行对 dst、`editor_service.save_procedure` 第 253 行、`import_service.import_procedure`、各颗粒度 mutator）。一处 hook 即全覆盖。
3. **旧 `ProcedureChapter.mark_status` 携带 `review`。**（model 注释 `unmarked / step / content / review`；`import_service.py:149` 写入。）⇒ 重建时 `review→review、其余→unmarked` 的夹紧**保住** B1 导入的 review 态。
4. **Q25 保证无交错。** 同一父下子章节与叶子项（step/content）互斥，根级同理；故前序「先所有子章节（各自递归）后所有 step」无歧义。
5. **颗粒度 chapter/step 端点前端在用**（`frontend/src/api/chapters.ts` / `steps.ts` / `store/procedureEditor.ts`）⇒ 必须覆盖它们，逐个 hook 不可靠，故选汇聚点方案。

### 关键设计点（trade-off，记入 commit 理由，见 memory `trade-off-auto-decide-with-log`）

- **汇聚点 hook vs 逐路径 hook：** 选汇聚点。代价是把「建新 node」耦合进「旧 numbering」这一语义上略奇怪的位置——用**显眼注释**标明是 B2a-B3 临时脚手架、B4 随 `numbering_service` 删除来缓解；换来一处改动全覆盖、不漏 mutator。
- **硬删 vs 软删重建：** 硬删（`db.delete`）。避免每次结构写入都软删积累死行；因无入边外键，硬删安全。
- **统一到 `rebuild_from_legacy`，删 B1 的 `flatten_tree`：** 避免「导入走 flatten、其余走 rebuild」两条会漂移的建 node 路径（B2b PDF 一旦两路不一致就出 bug）。导入经汇聚点同样产出等价 node（review/编号/结构一致，见 Task 3 验证）。
- **局部 import：** hook 处用函数内 `from app.services import node_sync`，规避 `numbering_service`（被早期广泛 import）潜在的 import 期循环（`node_sync` 不 import `numbering_service`，本无环，局部 import 为双保险）。

---

## 文件结构

| 文件 | 职责 | 动作 |
|---|---|---|
| `backend/app/services/node_sync.py` | `rebuild_from_legacy(db, procedure_id)`：旧树 → 全量重建 ProcedureNode | 创建 |
| `backend/app/services/numbering_service.py` | `recompute` 末尾挂一处 rebuild hook | 修改（加 2 行） |
| `backend/app/services/import_service.py` | 删 B1 的 `_write_procedure_nodes` + 调用 + 相关 import | 修改（删法） |
| `backend/app/services/node_import.py` | B1 的 `flatten_tree`（被 rebuild 取代） | **删除** |
| `backend/tests/unit/services/test_node_sync.py` | `rebuild_from_legacy` 单测 | 创建 |
| `backend/tests/integration/test_node_sync_dualwrite.py` | 汇聚点 hook 跨路径集成测试 | 创建 |
| `backend/tests/unit/services/test_node_import.py` | B1 的 flatten 单测（随 node_import 删） | **删除** |
| `backend/tests/integration/test_node_import_dualwrite.py` | B1 导入双写集成测试 | **保留**（经 hook 仍须全绿） |

---

## Task 1: `node_sync.rebuild_from_legacy`（旧树 → 全量重建 node）

**Files:**
- Create: `backend/app/services/node_sync.py`
- Test: `backend/tests/unit/services/test_node_sync.py`

- [ ] **Step 1: 写失败测试**

Create `backend/tests/unit/services/test_node_sync.py`:

> 注：`from tests.conftest import Factory` 与现有 service 层单测的 Factory 引入方式一致；若你发现现有测试用别的写法（如直接不标注类型），改成与现有一致即可。

```python
"""node_sync.rebuild_from_legacy 单测（Plan B2a 双写补全）。

用 factory 直接造旧 chapter/step 树，调 rebuild_from_legacy，再用 node_service.get_nodes
断言派生出的统一 ProcedureNode 结构与旧树一致。
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.services import node_service, node_sync
from tests.conftest import Factory


def _proc(factory: Factory) -> str:
    folder = factory.folder()
    return factory.procedure(folder_id=folder.id).id


def test_rebuild_chapters_and_content(factory: Factory, db: Session) -> None:
    pid = _proc(factory)
    c1 = factory.chapter(pid, title="目的", parent_id=None, sort_order=0)
    factory.step(pid, chapter_id=c1.id, content="<p>本程序规定...</p>", kind="content", sort_order=0)
    c2 = factory.chapter(pid, title="职责", parent_id=None, sort_order=1)
    c21 = factory.chapter(pid, title="质量部", parent_id=c2.id, sort_order=0)
    factory.step(pid, chapter_id=c21.id, content="<p>归口管理</p>", kind="content", sort_order=0)

    node_sync.rebuild_from_legacy(db, pid)

    nodes = node_service.get_nodes(db, pid)
    assert [(n["heading_level"], n["body"], n["code"]) for n in nodes] == [
        (1, "<p>目的</p>", "1"),
        (None, "<p>本程序规定...</p>", ""),
        (1, "<p>职责</p>", "2"),
        (2, "<p>质量部</p>", "2.1"),
        (None, "<p>归口管理</p>", ""),
    ]
    assert nodes[0]["parent_id"] is None
    assert nodes[2]["parent_id"] is None
    assert nodes[1]["parent_id"] == nodes[0]["id"]
    assert nodes[3]["parent_id"] == nodes[2]["id"]
    assert nodes[4]["parent_id"] == nodes[3]["id"]
    assert [n["sort_order"] for n in nodes] == sorted(n["sort_order"] for n in nodes)


def test_rebuild_step_node_keeps_form(factory: Factory, db: Session) -> None:
    pid = _proc(factory)
    c1 = factory.chapter(pid, title="执行", sort_order=0)
    factory.step(
        pid, chapter_id=c1.id, content="<p>填表</p>", kind="step",
        input_schema={"type": "COMMON"}, sort_order=0,
    )

    node_sync.rebuild_from_legacy(db, pid)

    leaf = node_service.get_nodes(db, pid)[1]
    assert leaf["kind"] == "step"
    assert leaf["heading_level"] is None
    assert leaf["body"] == "<p>填表</p>"
    assert leaf["input_schema"] == {"type": "COMMON"}


def test_rebuild_preserves_review_clamps_layer_marks(factory: Factory, db: Session) -> None:
    pid = _proc(factory)
    factory.chapter(pid, title="存疑", sort_order=0, mark_status="review")
    factory.chapter(pid, title="层级标记残留", sort_order=1, mark_status="step")

    node_sync.rebuild_from_legacy(db, pid)

    nodes = node_service.get_nodes(db, pid)
    assert nodes[0]["mark_status"] == "review"
    assert nodes[1]["mark_status"] == "unmarked"


def test_rebuild_empty_title_body_empty(factory: Factory, db: Session) -> None:
    pid = _proc(factory)
    factory.chapter(pid, title="   ", sort_order=0)
    node_sync.rebuild_from_legacy(db, pid)
    assert node_service.get_nodes(db, pid)[0]["body"] == ""


def test_rebuild_skip_numbering_carried(factory: Factory, db: Session) -> None:
    pid = _proc(factory)
    factory.chapter(pid, title="不编号章", sort_order=0, skip_numbering=True)
    node_sync.rebuild_from_legacy(db, pid)
    n = node_service.get_nodes(db, pid)[0]
    assert n["skip_numbering"] is True
    assert n["code"] == ""


def test_rebuild_wipes_stale_nodes(factory: Factory, db: Session) -> None:
    pid = _proc(factory)
    factory.node(pid, body="<p>陈旧</p>", heading_level=1, sort_order=999)  # 游离旧 node
    factory.chapter(pid, title="真章", sort_order=0)
    node_sync.rebuild_from_legacy(db, pid)
    assert [n["body"] for n in node_service.get_nodes(db, pid)] == ["<p>真章</p>"]
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && .venv/bin/python -m pytest tests/unit/services/test_node_sync.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.node_sync'`

- [ ] **Step 3: 实现**

Create `backend/app/services/node_sync.py`:

```python
"""旧 chapter/step 树 → 统一 ProcedureNode 行的全量重建（Plan B2a 双写补全）。

B1 只在导入路径双写 ProcedureNode；编辑器保存、章节/步骤颗粒度增删改/转换、版本 fork
都只写旧 chapter/step。本模块的 rebuild_from_legacy 从某程序当前 active 的旧树前序展开、
**整程序硬删重建** ProcedureNode 行，使 node 始终与旧树一致。因无任何外键指向 node id
（签核/附件/版本均挂 procedure 级，见 B2 调查），全量重建安全。挂在
numbering_service.recompute 末尾这一“所有结构写入唯一汇聚点”，无需逐个 hook 各 mutator。
属 expand 阶段脚手架，B4 删旧表时一并删除。

统一节点模型见 docs/superpowers/specs/2026-05-28-unified-node-model-design.md §2/§7。
"""

from __future__ import annotations

import html

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.chapter import ProcedureChapter
from app.models.node import ProcedureNode
from app.models.step import ProcedureStep
from app.services import node_numbering

_SORT_GAP = 1000


def _chapter_body(title: str) -> str:
    """heading 的 body = 标题首段（spec §2.3）；空标题 → 空 body（占位章节）。"""
    title = title.strip()
    return f"<p>{html.escape(title)}</p>" if title else ""


def _clamp_mark_status(value: str) -> str:
    """node mark_status 只有 unmarked | review；旧 step/content 等层级标记态夹紧为 unmarked，
    review（Word 智能解析持久态）保留。"""
    return "review" if value == "review" else "unmarked"


def rebuild_from_legacy(db: Session, procedure_id: str) -> None:
    """从旧 chapter/step 树全量重建该程序的 ProcedureNode 行。

    硬删现有 node 行 → 前序展开旧树（Q25 保证同父下子章节与叶子项互斥，无交错歧义）
    → 按文档序 gap 赋 sort_order 插入 → node_numbering 重算 code。只 flush 不 commit。
    """
    # 1. 硬删现有 node（无外键指向 node id，安全；避免软删累积死行）
    for n in db.execute(
        select(ProcedureNode).where(ProcedureNode.procedure_id == procedure_id)
    ).scalars():
        db.delete(n)

    # 2. 读 active 旧树并按 parent 分组
    chapters = list(
        db.execute(
            select(ProcedureChapter).where(
                ProcedureChapter.procedure_id == procedure_id,
                ProcedureChapter.is_active.is_(True),
            )
        ).scalars()
    )
    steps = list(
        db.execute(
            select(ProcedureStep).where(
                ProcedureStep.procedure_id == procedure_id,
                ProcedureStep.is_active.is_(True),
            )
        ).scalars()
    )
    chapters_by_parent: dict[str | None, list[ProcedureChapter]] = {}
    for ch in chapters:
        chapters_by_parent.setdefault(ch.parent_id, []).append(ch)
    steps_by_chapter: dict[str | None, list[ProcedureStep]] = {}
    for st in steps:
        steps_by_chapter.setdefault(st.chapter_id, []).append(st)

    # 3. 前序展开，全局 gap 序
    seq = 0

    def _next_sort() -> int:
        nonlocal seq
        seq += 1
        return seq * _SORT_GAP

    def walk(parent_chapter_id: str | None, level: int) -> None:
        for ch in sorted(
            chapters_by_parent.get(parent_chapter_id, []), key=lambda c: (c.sort_order, c.id)
        ):
            db.add(
                ProcedureNode(
                    procedure_id=procedure_id,
                    sort_order=_next_sort(),
                    heading_level=level,
                    kind="node",
                    body=_chapter_body(ch.title),
                    skip_numbering=ch.skip_numbering,
                    mark_status=_clamp_mark_status(ch.mark_status),
                )
            )
            walk(ch.id, level + 1)
        for st in sorted(
            steps_by_chapter.get(parent_chapter_id, []), key=lambda s: (s.sort_order, s.id)
        ):
            is_step = st.kind == "step"
            db.add(
                ProcedureNode(
                    procedure_id=procedure_id,
                    sort_order=_next_sort(),
                    heading_level=None,
                    kind="step" if is_step else "node",
                    body=st.content,
                    input_schema=st.input_schema if is_step else {},
                    attachment_marks=st.attachment_marks if is_step else [],
                    skip_numbering=st.skip_numbering,
                    mark_status="unmarked",
                )
            )

    walk(None, 1)
    db.flush()
    node_numbering.recompute(db, procedure_id)
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && .venv/bin/python -m pytest tests/unit/services/test_node_sync.py -v`
Expected: PASS（6 个）

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/node_sync.py backend/tests/unit/services/test_node_sync.py
git commit -m "feat(node_sync): rebuild_from_legacy — legacy chapter/step tree -> ProcedureNode rows"
```

---

## Task 2: 在 `numbering_service.recompute` 末尾挂 rebuild hook + 跨路径集成测试

**Files:**
- Modify: `backend/app/services/numbering_service.py`
- Test: `backend/tests/integration/test_node_sync_dualwrite.py`

- [ ] **Step 1: 写失败测试**

Create `backend/tests/integration/test_node_sync_dualwrite.py`:

> 注：`/copy` 端点请求体字段名（`target_folder_id` / `name`）请对照 `backend/app/routers/procedures.py` 第 374 行附近的 copy 端点入参 schema 确认；若不同，按真实字段名改本测试的 json。

```python
"""numbering_service.recompute → node 全量重建的汇聚点 hook 集成测试（Plan B2a）。

证明所有结构写入收尾的 numbering_service.recompute 会把旧树镜像成 ProcedureNode：
直接 recompute、HTTP 颗粒度改动（toggle-skip-numbering）、复制（_clone_tree）。
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.services import node_service, numbering_service
from tests.conftest import Factory

FOLDER = "/api/v1/folders"
IMPORT = "/api/v1/procedures/import"


def test_recompute_rebuilds_nodes(factory: Factory, db: Session) -> None:
    folder = factory.folder()
    pid = factory.procedure(folder_id=folder.id).id
    factory.chapter(pid, title="目的", sort_order=0)  # 只造旧树，未造 node
    assert node_service.get_nodes(db, pid) == []

    numbering_service.recompute(db, pid)  # 结构写入唯一汇聚点

    nodes = node_service.get_nodes(db, pid)
    assert [(n["heading_level"], n["body"], n["code"]) for n in nodes] == [(1, "<p>目的</p>", "1")]


def test_recompute_resyncs_after_legacy_change(factory: Factory, db: Session) -> None:
    folder = factory.folder()
    pid = factory.procedure(folder_id=folder.id).id
    ch = factory.chapter(pid, title="旧标题", sort_order=0)
    numbering_service.recompute(db, pid)
    assert node_service.get_nodes(db, pid)[0]["body"] == "<p>旧标题</p>"

    ch.title = "新标题"
    db.flush()
    numbering_service.recompute(db, pid)
    assert node_service.get_nodes(db, pid)[0]["body"] == "<p>新标题</p>"


def _leaf(client: TestClient) -> str:
    return client.post(FOLDER, json={"name": "B2a夹", "prefix": "B2A"}).json()["id"]


def test_granular_toggle_resyncs_nodes(client: TestClient) -> None:
    leaf = _leaf(client)
    chapters = [{"title": "目的", "content_type": "chapter", "children": [
        {"content_type": "content", "rich_content": "<p>x</p>"}]}]
    pid = client.post(
        IMPORT, json={"name": "P", "folder_id": leaf, "chapters": chapters}
    ).json()["id"]
    chap_id = client.get(f"/api/v1/procedures/{pid}").json()["chapters"][0]["id"]
    assert client.get(f"/api/v1/procedures/{pid}/nodes").json()[0]["code"] == "1"

    r = client.post(f"/api/v1/chapters/{chap_id}/toggle-skip-numbering")
    assert r.status_code == 200, r.text

    head = client.get(f"/api/v1/procedures/{pid}/nodes").json()[0]
    assert head["skip_numbering"] is True
    assert head["code"] == ""  # 颗粒度改动经 recompute hook 同步到 node


def test_copy_clones_nodes(client: TestClient) -> None:
    leaf = _leaf(client)
    chapters = [{"title": "目的", "content_type": "chapter", "children": [
        {"content_type": "content", "rich_content": "<p>x</p>"}]}]
    src = client.post(
        IMPORT, json={"name": "源", "folder_id": leaf, "chapters": chapters}
    ).json()["id"]

    r = client.post(
        f"/api/v1/procedures/{src}/copy", json={"target_folder_id": leaf, "name": "副本"}
    )
    assert r.status_code == 201, r.text
    new_id = r.json()["id"]

    nodes = client.get(f"/api/v1/procedures/{new_id}/nodes").json()
    assert [(n["heading_level"], n["body"], n["code"]) for n in nodes] == [
        (1, "<p>目的</p>", "1"),
        (None, "<p>x</p>", ""),
    ]
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && .venv/bin/python -m pytest tests/integration/test_node_sync_dualwrite.py -v`
Expected: FAIL — hook 未挂，`recompute` 不建 node，`get_nodes` 仍 `[]` / 颗粒度改动不反映到 node（`AssertionError`，非 404/500）。

- [ ] **Step 3: 实现**

In `backend/app/services/numbering_service.py`, locate the end of `recompute(db, procedure_id)` (its final `db.flush()`). Insert the rebuild hook **after** that `db.flush()`, so the tail reads:

```python
    db.flush()
    # Plan B2a：所有结构写入都经本 recompute 汇聚；在此把旧 chapter/step 树全量镜像成统一
    # ProcedureNode 行，使下游可改读 node（B2b PDF）。临时脚手架，B4 随旧表+本服务一并删。
    from app.services import node_sync  # 局部 import：避免 numbering_service 被广泛 import 时成环
    node_sync.rebuild_from_legacy(db, procedure_id)
```

（`node_sync` 调的是 `node_numbering.recompute`，非本 `numbering_service.recompute`，无递归。）

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && .venv/bin/python -m pytest tests/integration/test_node_sync_dualwrite.py -v`
Expected: PASS（4 个）

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/numbering_service.py backend/tests/integration/test_node_sync_dualwrite.py
git commit -m "feat(numbering): rebuild ProcedureNode at recompute choke point (Plan B2a dual-write completion)"
```

---

## Task 3: 删 B1 冗余的导入专用双写（统一到 rebuild 路径）

B1 的 `import_service._write_procedure_nodes`（走 `node_import.flatten_tree`）已被 Task 2 的汇聚点取代：导入收尾必调 `numbering_service.recompute(db, proc.id)` → `rebuild_from_legacy` 从刚落库的旧树重建等价 node。两条建 node 路径并存会漂移，删冗余的一条。

**Files:**
- Modify: `backend/app/services/import_service.py`
- Delete: `backend/app/services/node_import.py`
- Delete: `backend/tests/unit/services/test_node_import.py`

- [ ] **Step 1: 先确认 B1 集成测试此刻已由 hook 满足（不动它）**

Run: `cd backend && .venv/bin/python -m pytest tests/integration/test_node_import_dualwrite.py -v`
Expected: PASS（2 个）——此时 `_write_procedure_nodes`（B1）与 hook（B2a）双双在跑，node 最终态由 hook 的 rebuild 落定，断言（heading_level/body/code/parent/升序 sort_order/旧 chapters 仍在 + review/skip 携带）仍成立。**这一步是删除前的安全网：证明删掉 B1 那条不改变结果。**

- [ ] **Step 2: 删除 import_service 里的 B1 双写**

In `backend/app/services/import_service.py`:

1. 删掉 `import_procedure` 里 B1 加的两行（注释 + 调用）：

```python
    # Plan B1 双写：同一棵（已归一化）导入树并行落成统一 ProcedureNode 行。
    _write_procedure_nodes(db, proc, chapters)
```

（删后，`_create_node` 循环之后紧接原有的 `editor_service._validate_and_recompute_levels(db, proc.id)`。）

2. 删掉整个 `_write_procedure_nodes` 函数定义（B1 加在 `_create_node` 之后、`_promote_temp_urls` 之前的那段）。

3. 从顶部 `from app.services import (...)` 块里删掉 B1 加的 `node_import` 与 `node_service` 两个名字（其余成员保持不变；确认这两个名字在本文件再无其它使用——它们是 B1 专为 `_write_procedure_nodes` 引入的）。

- [ ] **Step 3: 删除 node_import 模块与其单测**

```bash
git rm backend/app/services/node_import.py backend/tests/unit/services/test_node_import.py
```

（`grep -rn "node_import" backend/app backend/tests` 确认全仓再无引用。`test_node_import_dualwrite.py` 不删——它测的是导入端到端双写结果，由 hook 继续满足。）

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && .venv/bin/python -m pytest tests/integration/test_node_import_dualwrite.py tests/integration/test_node_sync_dualwrite.py tests/integration/test_word_import.py -v`
Expected: PASS（导入双写 2 + 汇聚点 4 + 旧 Word 导入 18，均绿）。

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor(import): drop B1 import-only dual-write; unify on node_sync rebuild path (Plan B2a)"
```

---

## Task 4: 全量回归 + mypy

**Files:** 无新增

- [ ] **Step 1: 跑全部后端测试**

Run: `cd backend && .venv/bin/python -m pytest -q`
Expected: 绿。算术基线：main 现为 **658 passed + 1 先存失败**（`test_editor.py::test_create_chapter_and_nested_get`，与本计划无关）。本计划净变动：+ Task1 6 个 node_sync 单测 + Task2 4 个汇聚点集成测 − Task3 删 7 个 node_import flatten 单测 = **净 +3** ⇒ **约 661 passed + 1 先存失败**。

⚠️ **可能的额外红**：汇聚点 hook 让**每条**旧结构写入路径都重建 node，若有**先存测试**断言「某旧程序的 `GET /nodes` 为空」或在 rebuild 中暴露边界 bug，会新红。逐条判断：
- 若纯粹因为「node 现在对旧程序也存在/会重算」而红（B2a 的预期行为），**最小改**该断言（出 B2a 范围的旧测试不要大改）。
- 若是 `rebuild_from_legacy` 真 bug（如某 fork/编辑路径下旧树形态触发异常），**修 node_sync**，别改测试掩盖。
用 superpowers:systematic-debugging 定位任何非上述两类的红。

- [ ] **Step 2: 类型检查**

Run: `cd backend && .venv/bin/python -m mypy app/services/node_sync.py app/services/numbering_service.py app/services/import_service.py 2>&1 | tail -20`
Expected: 无 **新增** error。已知先存 error `app/services/_invariants.py:31`（`comparison-overlap`，main 上即有，随 follow-import 出现）与本计划无关——逐条确认非本计划新增即可。

- [ ] **Step 3: Commit（若有修正）**

```bash
git add -A
git commit -m "chore: type/regression fixes for Plan B2a"
```

---

## 完成标准（B2a）

1. `node_sync.rebuild_from_legacy` 从旧树派生出与 chapter/step 一致的 ProcedureNode：heading_level=嵌套深度、content/step→None、body（章节=`<p>标题</p>`、正文/步骤=content 原文）、编号、派生父子、升序 sort_order 全部正确；`review` 保留、旧层级标记态夹紧为 `unmarked`、`skip_numbering` 携带、`kind='step'` 的表单 `input_schema`/`attachment_marks` 保留。
2. 经 `numbering_service.recompute` 汇聚点，**导入 / 编辑器保存 / 颗粒度章节步骤改动 / 版本 fork（copy/upgrade/rollback/restore）** 都使该程序 node 与旧树同步——集成测试覆盖导入、颗粒度 toggle、copy 三类。
3. B1 的 `_write_procedure_nodes`/`node_import.py`/`test_node_import.py` 已删，**唯一**建 node 路径是 `rebuild_from_legacy`；`test_node_import_dualwrite.py` 不动且全绿。
4. 旧 chapter/step 写法、所有旧导入/编辑/版本测试全绿（双写并存，下游仍读旧表）。
5. parser / `ParsedNode` / `ImportNodeIn` schema / 前端 / `_validate_and_recompute_levels`（旧树校验逻辑）零改动。

## 交接给 B2b 的事实

- **现在所有程序**（不止导入的）都有与旧树一致的 `ProcedureNode` 行，且任何结构写入后即时同步。B2b 可放心把 PDF 读取切到 node。
- **B2b 待办（B2 调查 + B2a 设计已确认）：**
  1. `services/pdf/context.py:load_render_data` 改从 `ProcedureNode`（`node_service.get_nodes` / `node_tree.build_tree` + `node.code`）组装 `ChapterData/StepData` 快照；下游 `sections.py` 渲染不变。
  2. **heading title 从 body 派生**：node 把章节标题存为 `body=<p>标题</p>`，PDF 需反解出标题文本（spec §2.3）；正文/step 沿用 `pdf-content-no-title`（无编号无标题内联）。
  3. sign-off / attachment / version-read / numbering 在 B2b **无需改动**（调查确认 no-op；numbering 读 `node.code`，已由 B2a 维护）。
  4. **编辑器/`GET /procedures/{id}` 详情读取不在 B2b**：当前前端编辑器消费 chapter/step；详情读切到 node 随 B3 前端改造一起做。
  5. 既有 dev.db 里 B2a 之前创建、且之后未再被结构写入的程序，其 node 可能尚未生成（无生产数据 + seed 不产内容，影响可忽略；B4 重建 dev.db 时彻底清零）。若 B2b 要对任意历史程序出 PDF，可加一次性 `rebuild_from_legacy` backfill。
```

