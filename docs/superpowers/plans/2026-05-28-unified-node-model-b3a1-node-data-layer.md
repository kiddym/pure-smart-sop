# 统一节点模型 B3a-1 — 前端节点数据层（api + store）实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立 B3 节点编辑器的**数据层**——node API 客户端 + 统一 `Node` 类型 + `nodeEditor` Pinia store（即时·乐观·颗粒度写 + 撤销），全部 vitest 单测覆盖，**不含任何 UI、不接线到现有编辑器**。纯增量、app 不变。

**Architecture:** 服务端权威：store 持服务端返回的扁平 node list（已带派生 `parent_id`/`depth`/`code`），渲染时只做展开折叠。结构编辑（层级/kind/skip/批量/review 确认）走 `PATCH :batch`（返回全量新 list 且清 review），内容编辑（body/表单）走 `PATCH /nodes/{id}`（If-Match 乐观锁，返回单节点），增删/重排走 `POST/DELETE/reorder` 后重新 `GET`。撤销 = 逆操作栈。客户端**不重算编号/派生**（B2 已让后端权威）。

**Tech Stack:** Vue 3、Pinia（Options API）、axios（`src/api/http.ts`，响应 `.data`、`If-Match` 头传 revision、拦截器 toast `detail.message`）、TypeScript、vitest（`vi.mock('@/api/...')` + `setActivePinia(createPinia())`）。前端测试 `cd frontend && npx vitest run <file>`；类型检查 `cd frontend && npx vue-tsc --noEmit`（或 package.json 的 type-check 脚本）。

**Spec:** `docs/superpowers/specs/2026-05-28-unified-node-model-b3-frontend-design.md`（B3a 数据层）+ 母 spec §4（node API）/§3（转换语义）。B3a-1 是 B3a 的第 1 部分（数据层）；第 2 部分 B3a-2 建 NodeTreePanel/NodeDetailPanel 并经 flag 接线。

**后端契约（已核对 `routers/nodes.py` + `schemas/node_v2.py`，实现时以真实代码为准）：**
- `GET /api/v1/procedures/{pid}/nodes` → `NodeOut[]`（扁平，按 sort_order，含派生 `parent_id/depth/code`）。
- `PATCH /api/v1/nodes/{id}`（`If-Match: <revision>` 头）→ `NodeOut`（单节点）。body=`NodePatchIn`：`{heading_level?, set_heading_level:bool, kind?, body?, input_schema?, attachment_marks?, skip_numbering?}`。**改 heading_level 必须带 `set_heading_level:true`**（null 既是合法值又是默认值）。**不支持 mark_status**。
- `POST /api/v1/procedures/{pid}/nodes` → `NodeOut`(201)。body=`NodeCreateIn`：`{body?, heading_level?, kind?, input_schema?, attachment_marks?, skip_numbering?, sort_order?}`。
- `DELETE /api/v1/nodes/{id}` → 204。
- `PATCH /api/v1/procedures/{pid}/nodes:batch` → `NodeOut[]`（**全量**）。body=`NodeBatchIn`：`{updates: {[id]: {heading_level?, set_heading_level:bool, kind?, input_schema?, skip_numbering?}}}`。**副作用：列表里每个 node 若 `mark_status==='review'` 清回 `unmarked`（空 change 也清）**；不支持 body/attachment_marks。无 If-Match。
- `POST /api/v1/procedures/{pid}/nodes/reorder` → 204。body=`{ordered_ids: string[]}`（须为该程序全部 active 节点的一个排列）。

---

## 范围说明

**做（B3a-1）：** `src/types/node.ts` 加 `Node`/输入类型；`src/api/nodes.ts` 客户端；`src/utils/nodeTree.ts`（标题派生 + 展开折叠）；`src/store/nodeEditor.ts` store（load + 结构编辑 + 内容编辑 + 撤销）；vitest 单测。

**不做：** 任何 Vue 组件、路由/flag、接线到 `ProcedureEditorView`（→ B3a-2）。删旧编辑器/layerMark/markMode（→ B3b）。β 键盘 / δ markdown（B3 之后）。后端零改动。

### 关键设计点（trade-off，commit 写理由）
- **结构编辑一律走 `:batch`（即使单节点）**：换来「返回全量权威 list（派生值正确）+ 自动清 review」，省去客户端重算派生 + 单独 re-GET。`PATCH /nodes/{id}` 只用于 body/表单（非结构、不动派生、需 revision 乐观锁）。
- **服务端权威、不做客户端派生**：B2 已让后端 `get_nodes` 产 `parent_id/depth/code`。store 只持 list + 展开态；增删/重排后 re-GET。比旧 1078 行 store 简单得多。
- **撤销 = 逆操作**（§6.1）：每个已提交结构/内容操作记一条逆操作；`undo()` 执行逆操作（不再入 undo 栈，入 redo 栈）。删除的撤销 = 重建（新 id，内容/位置还原）——记入备注。
- **review 确认** = `:batch` 传该节点空 change（后端清 review）。

---

## 文件结构

| 文件 | 职责 | 动作 |
|---|---|---|
| `src/types/node.ts` | 加统一 `Node` + `NodePatch`/`NodeCreate`/`NodeBatchUpdates` 输入类型 | 修改（追加） |
| `src/api/nodes.ts` | node API 客户端（list/patch/create/delete/reorder/batch） | 创建 |
| `src/utils/nodeTree.ts` | `nodeTitle(body)` 标题派生 + `visibleRows(...)` 展开折叠 + `hasChildren` | 创建 |
| `src/store/nodeEditor.ts` | nodeEditor Pinia store | 创建 |
| `tests/unit/api/nodes.spec.ts` | 客户端单测（mock http） | 创建 |
| `tests/unit/utils/nodeTree.spec.ts` | 标题派生 + 折叠单测 | 创建 |
| `tests/unit/store/nodeEditor.spec.ts` | store 单测（mock api/nodes） | 创建 |

---

## Task 1: 统一 `Node` 类型 + `api/nodes.ts` 客户端

**Files:**
- Modify: `src/types/node.ts`
- Create: `src/api/nodes.ts`
- Test: `tests/unit/api/nodes.spec.ts`

- [ ] **Step 1: 写失败测试**

Create `tests/unit/api/nodes.spec.ts`:

```typescript
import { describe, expect, it, vi, beforeEach } from 'vitest'

vi.mock('@/api/http', () => ({
  http: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}))

import { http } from '@/api/http'
import {
  listNodes,
  patchNode,
  createNode,
  deleteNode,
  batchUpdateNodes,
  reorderNodes,
} from '@/api/nodes'

const mocked = http as unknown as {
  get: ReturnType<typeof vi.fn>
  post: ReturnType<typeof vi.fn>
  patch: ReturnType<typeof vi.fn>
  delete: ReturnType<typeof vi.fn>
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('api/nodes', () => {
  it('listNodes GETs the procedure nodes and unwraps data', async () => {
    mocked.get.mockResolvedValue({ data: [{ id: 'n1' }] })
    const out = await listNodes('p1')
    expect(mocked.get).toHaveBeenCalledWith('/procedures/p1/nodes')
    expect(out).toEqual([{ id: 'n1' }])
  })

  it('patchNode PATCHes /nodes/{id} with If-Match revision', async () => {
    mocked.patch.mockResolvedValue({ data: { id: 'n1' } })
    await patchNode('n1', { body: '<p>x</p>' }, 3)
    expect(mocked.patch).toHaveBeenCalledWith(
      '/nodes/n1',
      { body: '<p>x</p>' },
      { headers: { 'If-Match': '3' } },
    )
  })

  it('createNode POSTs to /procedures/{id}/nodes', async () => {
    mocked.post.mockResolvedValue({ data: { id: 'new' } })
    const out = await createNode('p1', { heading_level: 1, body: '<p>A</p>' })
    expect(mocked.post).toHaveBeenCalledWith('/procedures/p1/nodes', {
      heading_level: 1,
      body: '<p>A</p>',
    })
    expect(out).toEqual({ id: 'new' })
  })

  it('deleteNode DELETEs /nodes/{id}', async () => {
    mocked.delete.mockResolvedValue({})
    await deleteNode('n1')
    expect(mocked.delete).toHaveBeenCalledWith('/nodes/n1')
  })

  it('batchUpdateNodes PATCHes the :batch endpoint and returns the full list', async () => {
    mocked.patch.mockResolvedValue({ data: [{ id: 'n1' }, { id: 'n2' }] })
    const out = await batchUpdateNodes('p1', { n1: { set_heading_level: true, heading_level: 2 } })
    expect(mocked.patch).toHaveBeenCalledWith('/procedures/p1/nodes:batch', {
      updates: { n1: { set_heading_level: true, heading_level: 2 } },
    })
    expect(out).toHaveLength(2)
  })

  it('reorderNodes POSTs ordered_ids', async () => {
    mocked.post.mockResolvedValue({})
    await reorderNodes('p1', ['n2', 'n1'])
    expect(mocked.post).toHaveBeenCalledWith('/procedures/p1/nodes/reorder', {
      ordered_ids: ['n2', 'n1'],
    })
  })
})
```

- [ ] **Step 2: 运行确认失败**

Run: `cd frontend && npx vitest run tests/unit/api/nodes.spec.ts`
Expected: FAIL — `@/api/nodes` 不存在 / 函数未定义。

- [ ] **Step 3: 实现**

In `src/types/node.ts`, append the unified node types (after the existing exports; reuse the existing `MarkStatus`/`InputSchema`/`AttachmentMark`):

```typescript
// ---- 统一节点模型（B3）：单 ProcedureNode 取代 chapter/content/step 三分 ----
// 对齐后端 NodeOut（app/schemas/node_v2.py）。parent_id/depth/code 为服务端派生。
export interface Node {
  id: string
  procedure_id: string
  sort_order: number
  heading_level: number | null // null=正文；1..N=章节层级
  kind: 'node' | 'step' // 'node'=无表单（章节/正文）；'step'=带表单
  body: string // rich HTML；heading 标题=body 第一个块级元素文本
  code: string // 服务端编号
  skip_numbering: boolean
  input_schema: InputSchema | Record<string, never>
  attachment_marks: AttachmentMark[]
  mark_status: MarkStatus // 统一模型只用 'unmarked' | 'review'
  revision: number // 乐观锁（仅 PATCH /nodes/{id} 用）
  parent_id: string | null // 派生
  depth: number // 派生
}

// PATCH /nodes/{id} body（NodePatchIn）。改 heading_level 必须带 set_heading_level:true。
export interface NodePatch {
  heading_level?: number | null
  set_heading_level?: boolean
  kind?: 'node' | 'step'
  body?: string
  input_schema?: InputSchema
  attachment_marks?: AttachmentMark[]
  skip_numbering?: boolean
}

// POST /procedures/{id}/nodes body（NodeCreateIn）。
export interface NodeCreate {
  body?: string
  heading_level?: number | null
  kind?: 'node' | 'step'
  input_schema?: InputSchema
  attachment_marks?: AttachmentMark[]
  skip_numbering?: boolean
  sort_order?: number | null
}

// :batch 单项（NodeBatchItem，不含 body/attachment_marks）。
export interface NodeBatchItem {
  heading_level?: number | null
  set_heading_level?: boolean
  kind?: 'node' | 'step'
  input_schema?: InputSchema
  skip_numbering?: boolean
}

// :batch updates 映射：nodeId → 变更。
export type NodeBatchUpdates = Record<string, NodeBatchItem>
```

Create `src/api/nodes.ts`:

```typescript
import { http } from './http'
import type { Node, NodeBatchUpdates, NodeCreate, NodePatch } from '@/types/node'

// 统一节点 API 客户端（spec §4）。结构编辑走 batch（返回全量 + 清 review）；
// 内容编辑走 patch（If-Match 乐观锁，返回单节点）；增删/重排后调用方 re-GET。

export const listNodes = async (procedureId: string): Promise<Node[]> =>
  (await http.get<Node[]>(`/procedures/${procedureId}/nodes`)).data

export const patchNode = async (
  nodeId: string,
  patch: NodePatch,
  revision: number,
): Promise<Node> =>
  (
    await http.patch<Node>(`/nodes/${nodeId}`, patch, {
      headers: { 'If-Match': String(revision) },
    })
  ).data

export const createNode = async (procedureId: string, payload: NodeCreate): Promise<Node> =>
  (await http.post<Node>(`/procedures/${procedureId}/nodes`, payload)).data

export const deleteNode = async (nodeId: string): Promise<void> => {
  await http.delete(`/nodes/${nodeId}`)
}

export const batchUpdateNodes = async (
  procedureId: string,
  updates: NodeBatchUpdates,
): Promise<Node[]> =>
  (await http.patch<Node[]>(`/procedures/${procedureId}/nodes:batch`, { updates })).data

export const reorderNodes = async (
  procedureId: string,
  orderedIds: string[],
): Promise<void> => {
  await http.post(`/procedures/${procedureId}/nodes/reorder`, { ordered_ids: orderedIds })
}
```

- [ ] **Step 4: 运行确认通过**

Run: `cd frontend && npx vitest run tests/unit/api/nodes.spec.ts`
Expected: PASS（6）。

- [ ] **Step 5: Commit**

```bash
git add src/types/node.ts src/api/nodes.ts tests/unit/api/nodes.spec.ts
git commit -m "feat(fe/nodes): unified Node type + node API client (B3a-1)"
```

---

## Task 2: `utils/nodeTree.ts`（标题派生 + 展开折叠）

**Files:**
- Create: `src/utils/nodeTree.ts`
- Test: `tests/unit/utils/nodeTree.spec.ts`

- [ ] **Step 1: 写失败测试**

Create `tests/unit/utils/nodeTree.spec.ts`:

```typescript
import { describe, expect, it } from 'vitest'
import { nodeTitle, hasChildren, visibleRows } from '@/utils/nodeTree'
import type { Node } from '@/types/node'

function n(over: Partial<Node>): Node {
  return {
    id: 'x', procedure_id: 'p', sort_order: 0, heading_level: null, kind: 'node',
    body: '', code: '', skip_numbering: false, input_schema: {}, attachment_marks: [],
    mark_status: 'unmarked', revision: 1, parent_id: null, depth: 0, ...over,
  }
}

describe('nodeTitle', () => {
  it('takes the first block element text', () => {
    expect(nodeTitle(n({ body: '<p>目的</p><p>其余</p>' }))).toBe('目的')
  })
  it('unescapes entities and strips nested tags', () => {
    expect(nodeTitle(n({ body: '<p>A &amp; <b>B</b></p>' }))).toBe('A & B')
  })
  it('empty body falls back', () => {
    expect(nodeTitle(n({ body: '', heading_level: 1 }))).toBe('未命名章节')
    expect(nodeTitle(n({ body: '   ' }))).toBe('未命名章节')
  })
})

describe('hasChildren', () => {
  it('true when some node has this id as parent_id', () => {
    const nodes = [n({ id: 'a', heading_level: 1 }), n({ id: 'b', parent_id: 'a' })]
    expect(hasChildren(nodes, 'a')).toBe(true)
    expect(hasChildren(nodes, 'b')).toBe(false)
  })
})

describe('visibleRows', () => {
  const nodes = [
    n({ id: 'a', heading_level: 1, depth: 0, parent_id: null, body: '<p>A</p>' }),
    n({ id: 'b', heading_level: 2, depth: 1, parent_id: 'a', body: '<p>B</p>' }),
    n({ id: 'c', depth: 2, parent_id: 'b', body: '<p>c</p>' }),
  ]
  it('collapsing a node hides its descendants', () => {
    const rows = visibleRows(nodes, { a: true, b: false }, { search: '', reviewOnly: false })
    expect(rows.map((r) => r.id)).toEqual(['a', 'b']) // c hidden under collapsed b
  })
  it('all expanded shows everything', () => {
    const rows = visibleRows(nodes, { a: true, b: true }, { search: '', reviewOnly: false })
    expect(rows.map((r) => r.id)).toEqual(['a', 'b', 'c'])
  })
  it('reviewOnly filters to review nodes', () => {
    const rv = [n({ id: 'a', body: '<p>A</p>', mark_status: 'review' }), n({ id: 'b', body: '<p>B</p>' })]
    const rows = visibleRows(rv, {}, { search: '', reviewOnly: true })
    expect(rows.map((r) => r.id)).toEqual(['a'])
  })
  it('search matches title text', () => {
    const rows = visibleRows(nodes, { a: true, b: true }, { search: 'B', reviewOnly: false })
    expect(rows.map((r) => r.id)).toEqual(['b'])
  })
  it('row carries derived title + hasChildren + expanded', () => {
    const rows = visibleRows(nodes, { a: true, b: true }, { search: '', reviewOnly: false })
    expect(rows[0]).toMatchObject({ id: 'a', title: 'A', hasChildren: true, expanded: true })
  })
})
```

- [ ] **Step 2: 运行确认失败**

Run: `cd frontend && npx vitest run tests/unit/utils/nodeTree.spec.ts`
Expected: FAIL — `@/utils/nodeTree` 不存在。

- [ ] **Step 3: 实现**

Create `src/utils/nodeTree.ts`:

```typescript
import type { Node } from '@/types/node'

const FALLBACK = '未命名章节'

/** 标题 = body 第一个块级元素的纯文本（spec §2.3）；空 → 占位。用浏览器 DOMParser 解析。 */
export function nodeTitle(node: Node): string {
  const body = node.body
  if (!body || !body.trim()) return FALLBACK
  const doc = new DOMParser().parseFromString(body, 'text/html')
  const first = doc.body.firstElementChild
  const text = (first ? first.textContent : doc.body.textContent) ?? ''
  const trimmed = text.trim()
  return trimmed || FALLBACK
}

/** 该节点是否有派生子（有任何节点 parent_id === id）。 */
export function hasChildren(nodes: Node[], id: string): boolean {
  return nodes.some((x) => x.parent_id === id)
}

export interface TreeRow {
  node: Node
  title: string
  hasChildren: boolean
  expanded: boolean
}

export interface RowFilter {
  search: string
  reviewOnly: boolean
}

/** 渲染行：按展开态折叠（折叠的 heading 子树整体隐藏）+ review/search 过滤。
 * nodes 假定已按 sort_order 升序（服务端保证）。展开态缺省视为展开。 */
export function visibleRows(
  nodes: Node[],
  expanded: Record<string, boolean>,
  filter: RowFilter,
): TreeRow[] {
  const byId = new Map(nodes.map((x) => [x.id, x]))
  const isExpanded = (id: string): boolean => expanded[id] !== false

  // 某节点是否被某个折叠的祖先隐藏（沿 parent_id 链上溯）。
  const hiddenByCollapse = (node: Node): boolean => {
    let pid = node.parent_id
    while (pid) {
      if (!isExpanded(pid)) return true
      pid = byId.get(pid)?.parent_id ?? null
    }
    return false
  }

  const q = filter.search.trim().toLowerCase()
  const rows: TreeRow[] = []
  for (const node of nodes) {
    if (filter.reviewOnly && node.mark_status !== 'review') continue
    const title = nodeTitle(node)
    if (q && !title.toLowerCase().includes(q)) continue
    // search/reviewOnly 激活时不做折叠（展开匹配项可见）；否则按展开态折叠。
    if (!q && !filter.reviewOnly && hiddenByCollapse(node)) continue
    rows.push({ node, title, hasChildren: hasChildren(nodes, node.id), expanded: isExpanded(node.id) })
  }
  return rows
}
```

- [ ] **Step 4: 运行确认通过**

Run: `cd frontend && npx vitest run tests/unit/utils/nodeTree.spec.ts`
Expected: PASS（jsdom 提供 `DOMParser`；vitest 默认 jsdom 环境——若该测试文件未启用 jsdom，在文件顶部加 `// @vitest-environment jsdom`）。

- [ ] **Step 5: Commit**

```bash
git add src/utils/nodeTree.ts tests/unit/utils/nodeTree.spec.ts
git commit -m "feat(fe/nodeTree): node title derivation + expand-folding visibleRows (B3a-1)"
```

---

## Task 3: `nodeEditor` store — load + 渲染派生 + 选择/展开/过滤

**Files:**
- Create: `src/store/nodeEditor.ts`
- Test: `tests/unit/store/nodeEditor.spec.ts`

- [ ] **Step 1: 写失败测试**

Create `tests/unit/store/nodeEditor.spec.ts`:

```typescript
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

const { listSpy, patchSpy, createSpy, deleteSpy, batchSpy, reorderSpy } = vi.hoisted(() => ({
  listSpy: vi.fn(), patchSpy: vi.fn(), createSpy: vi.fn(),
  deleteSpy: vi.fn(), batchSpy: vi.fn(), reorderSpy: vi.fn(),
}))
vi.mock('@/api/nodes', () => ({
  listNodes: listSpy, patchNode: patchSpy, createNode: createSpy,
  deleteNode: deleteSpy, batchUpdateNodes: batchSpy, reorderNodes: reorderSpy,
}))

import { useNodeEditorStore } from '@/store/nodeEditor'
import type { Node } from '@/types/node'

function n(over: Partial<Node>): Node {
  return {
    id: 'x', procedure_id: 'p1', sort_order: 0, heading_level: null, kind: 'node',
    body: '', code: '', skip_numbering: false, input_schema: {}, attachment_marks: [],
    mark_status: 'unmarked', revision: 1, parent_id: null, depth: 0, ...over,
  }
}

beforeEach(() => {
  vi.clearAllMocks()
  setActivePinia(createPinia())
})

describe('nodeEditor store — load + derive', () => {
  it('load fetches nodes and selects the first row', async () => {
    listSpy.mockResolvedValue([
      n({ id: 'a', heading_level: 1, body: '<p>目的</p>' }),
      n({ id: 'b', parent_id: 'a', sort_order: 1000, depth: 1, body: '<p>正文</p>' }),
    ])
    const store = useNodeEditorStore()
    await store.load('p1')
    expect(listSpy).toHaveBeenCalledWith('p1')
    expect(store.nodes).toHaveLength(2)
    expect(store.selectedId).toBe('a')
    expect(store.rows.map((r) => r.title)).toEqual(['目的', '正文'])
  })

  it('toggleExpand collapses a node and hides descendants in rows', async () => {
    listSpy.mockResolvedValue([
      n({ id: 'a', heading_level: 1, body: '<p>A</p>' }),
      n({ id: 'b', parent_id: 'a', sort_order: 1000, depth: 1, body: '<p>b</p>' }),
    ])
    const store = useNodeEditorStore()
    await store.load('p1')
    store.toggleExpand('a')
    expect(store.rows.map((r) => r.node.id)).toEqual(['a'])
  })

  it('reviewCount + reviewOnly filter', async () => {
    listSpy.mockResolvedValue([
      n({ id: 'a', heading_level: 1, body: '<p>A</p>', mark_status: 'review' }),
      n({ id: 'b', sort_order: 1000, body: '<p>b</p>' }),
    ])
    const store = useNodeEditorStore()
    await store.load('p1')
    expect(store.reviewCount).toBe(1)
    store.reviewOnly = true
    expect(store.rows.map((r) => r.node.id)).toEqual(['a'])
  })

  it('load sets loadError on failure', async () => {
    listSpy.mockRejectedValue(new Error('boom'))
    const store = useNodeEditorStore()
    await store.load('p1')
    expect(store.loadError).toBe(true)
    expect(store.nodes).toEqual([])
  })
})
```

- [ ] **Step 2: 运行确认失败**

Run: `cd frontend && npx vitest run tests/unit/store/nodeEditor.spec.ts`
Expected: FAIL — `@/store/nodeEditor` 不存在。

- [ ] **Step 3: 实现**

Create `src/store/nodeEditor.ts` (this task implements load + derive + selection/expand/filter; Tasks 4–5 add edit/undo actions to the SAME store — they will extend this file):

```typescript
import { defineStore } from 'pinia'
import * as api from '@/api/nodes'
import type { Node } from '@/types/node'
import { visibleRows, type TreeRow } from '@/utils/nodeTree'

interface State {
  procedureId: string | null
  nodes: Node[]
  selectedId: string | null
  expanded: Record<string, boolean>
  search: string
  reviewOnly: boolean
  selection: Set<string> // γ 多选（Task 4/5 用）
  loading: boolean
  loadError: boolean
  // 撤销（Task 5）
  undoStack: InverseOp[]
  redoStack: InverseOp[]
}

// 逆操作（Task 5 填充实现；此处先声明类型，store 形状稳定）。
export type InverseOp = () => Promise<void>

export const useNodeEditorStore = defineStore('nodeEditor', {
  state: (): State => ({
    procedureId: null,
    nodes: [],
    selectedId: null,
    expanded: {},
    search: '',
    reviewOnly: false,
    selection: new Set<string>(),
    loading: false,
    loadError: false,
    undoStack: [],
    redoStack: [],
  }),

  getters: {
    rows(state): TreeRow[] {
      return visibleRows(state.nodes, state.expanded, {
        search: state.search,
        reviewOnly: state.reviewOnly,
      })
    },
    nodeMap(state): Map<string, Node> {
      return new Map(state.nodes.map((x) => [x.id, x]))
    },
    reviewCount(state): number {
      return state.nodes.filter((x) => x.mark_status === 'review').length
    },
    selectedNode(state): Node | null {
      return state.selectedId ? this.nodeMap.get(state.selectedId) ?? null : null
    },
  },

  actions: {
    async load(procedureId: string): Promise<void> {
      this.loading = true
      this.loadError = false
      try {
        this.procedureId = procedureId
        this.nodes = await api.listNodes(procedureId)
        this.expanded = {}
        this.selection = new Set()
        this.undoStack = []
        this.redoStack = []
        this.selectedId = this.nodes[0]?.id ?? null
      } catch {
        this.loadError = true
        this.nodes = []
        this.selectedId = null
      } finally {
        this.loading = false
      }
    },

    select(id: string | null): void {
      this.selectedId = id
    },

    toggleExpand(id: string): void {
      // 缺省视为展开，故首次 toggle = 折叠。
      this.expanded[id] = this.expanded[id] === false
    },
  },
})
```

- [ ] **Step 4: 运行确认通过**

Run: `cd frontend && npx vitest run tests/unit/store/nodeEditor.spec.ts`
Expected: PASS（4）。

- [ ] **Step 5: Commit**

```bash
git add src/store/nodeEditor.ts tests/unit/store/nodeEditor.spec.ts
git commit -m "feat(fe/nodeEditor): store load + derived rows + selection/expand/filter (B3a-1)"
```

---

## Task 4: `nodeEditor` store — 结构编辑（:batch / create / delete / reorder）

**Files:**
- Modify: `src/store/nodeEditor.ts`
- Test: `tests/unit/store/nodeEditor.spec.ts`（追加）

- [ ] **Step 1: 写失败测试**

Append to `tests/unit/store/nodeEditor.spec.ts`:

```typescript
describe('nodeEditor store — structural edits', () => {
  it('setLevel routes through :batch and replaces nodes with the full list', async () => {
    listSpy.mockResolvedValue([n({ id: 'a', heading_level: null, body: '<p>x</p>' })])
    batchSpy.mockResolvedValue([n({ id: 'a', heading_level: 2, body: '<p>x</p>', code: '1' })])
    const store = useNodeEditorStore()
    await store.load('p1')
    await store.setLevel('a', 2)
    expect(batchSpy).toHaveBeenCalledWith('p1', { a: { set_heading_level: true, heading_level: 2 } })
    expect(store.nodeMap.get('a')?.heading_level).toBe(2)
  })

  it('setLevel to null (降为正文) sends set_heading_level true + null', async () => {
    listSpy.mockResolvedValue([n({ id: 'a', heading_level: 2, body: '<p>x</p>' })])
    batchSpy.mockResolvedValue([n({ id: 'a', heading_level: null, body: '<p>x</p>' })])
    const store = useNodeEditorStore()
    await store.load('p1')
    await store.setLevel('a', null)
    expect(batchSpy).toHaveBeenCalledWith('p1', { a: { set_heading_level: true, heading_level: null } })
  })

  it('batchSetLevel applies one level to many (γ path)', async () => {
    listSpy.mockResolvedValue([n({ id: 'a', body: '<p>a</p>' }), n({ id: 'b', sort_order: 1000, body: '<p>b</p>' })])
    batchSpy.mockResolvedValue([n({ id: 'a', heading_level: 3 }), n({ id: 'b', heading_level: 3, sort_order: 1000 })])
    const store = useNodeEditorStore()
    await store.load('p1')
    await store.batchSetLevel(['a', 'b'], 3)
    expect(batchSpy).toHaveBeenCalledWith('p1', {
      a: { set_heading_level: true, heading_level: 3 },
      b: { set_heading_level: true, heading_level: 3 },
    })
  })

  it('confirmReview sends an empty :batch change (backend clears review)', async () => {
    listSpy.mockResolvedValue([n({ id: 'a', body: '<p>a</p>', mark_status: 'review' })])
    batchSpy.mockResolvedValue([n({ id: 'a', body: '<p>a</p>', mark_status: 'unmarked' })])
    const store = useNodeEditorStore()
    await store.load('p1')
    await store.confirmReview('a')
    expect(batchSpy).toHaveBeenCalledWith('p1', { a: {} })
    expect(store.nodeMap.get('a')?.mark_status).toBe('unmarked')
  })

  it('createNode then re-GETs the full list', async () => {
    listSpy.mockResolvedValueOnce([n({ id: 'a', heading_level: 1, body: '<p>a</p>' })])
    createSpy.mockResolvedValue(n({ id: 'new', body: '' }))
    listSpy.mockResolvedValueOnce([
      n({ id: 'a', heading_level: 1, body: '<p>a</p>' }),
      n({ id: 'new', sort_order: 1000, body: '' }),
    ])
    const store = useNodeEditorStore()
    await store.load('p1')
    await store.createNode({ heading_level: null })
    expect(createSpy).toHaveBeenCalledWith('p1', { heading_level: null })
    expect(store.nodes.map((x) => x.id)).toEqual(['a', 'new'])
  })

  it('deleteNode then re-GETs', async () => {
    listSpy.mockResolvedValueOnce([n({ id: 'a', body: '<p>a</p>' }), n({ id: 'b', sort_order: 1000 })])
    deleteSpy.mockResolvedValue(undefined)
    listSpy.mockResolvedValueOnce([n({ id: 'a', body: '<p>a</p>' })])
    const store = useNodeEditorStore()
    await store.load('p1')
    await store.removeNode('b')
    expect(deleteSpy).toHaveBeenCalledWith('b')
    expect(store.nodes.map((x) => x.id)).toEqual(['a'])
  })

  it('reorder then re-GETs', async () => {
    listSpy.mockResolvedValueOnce([n({ id: 'a' }), n({ id: 'b', sort_order: 1000 })])
    reorderSpy.mockResolvedValue(undefined)
    listSpy.mockResolvedValueOnce([n({ id: 'b' }), n({ id: 'a', sort_order: 1000 })])
    const store = useNodeEditorStore()
    await store.load('p1')
    await store.reorder(['b', 'a'])
    expect(reorderSpy).toHaveBeenCalledWith('p1', ['b', 'a'])
    expect(store.nodes.map((x) => x.id)).toEqual(['b', 'a'])
  })
})
```

- [ ] **Step 2: 运行确认失败**

Run: `cd frontend && npx vitest run tests/unit/store/nodeEditor.spec.ts`
Expected: FAIL — `setLevel`/`batchSetLevel`/`confirmReview`/`createNode`/`removeNode`/`reorder` 未定义。

- [ ] **Step 3: 实现**

Add these actions to the `actions` block in `src/store/nodeEditor.ts` (after `toggleExpand`). Add a private helper `_refetch` and a `_batch` that records undo (undo wiring lands in Task 5 — here `_pushUndo` is a no-op placeholder method added now so signatures are stable):

```typescript
    async _refetch(): Promise<void> {
      if (!this.procedureId) return
      this.nodes = await api.listNodes(this.procedureId)
    },

    // 占位：Task 5 实现逆操作入栈；此处先空实现，保持调用点稳定。
    _pushUndo(_inverse: InverseOp): void {
      void _inverse
    },

    async setLevel(id: string, level: number | null): Promise<void> {
      if (!this.procedureId) return
      const prev = this.nodeMap.get(id)?.heading_level ?? null
      this.nodes = await api.batchUpdateNodes(this.procedureId, {
        [id]: { set_heading_level: true, heading_level: level },
      })
      this._pushUndo(() => this.setLevel(id, prev))
    },

    async setKind(id: string, kind: 'node' | 'step'): Promise<void> {
      if (!this.procedureId) return
      const prev = this.nodeMap.get(id)?.kind ?? 'node'
      this.nodes = await api.batchUpdateNodes(this.procedureId, { [id]: { kind } })
      this._pushUndo(() => this.setKind(id, prev))
    },

    async toggleSkip(id: string): Promise<void> {
      if (!this.procedureId) return
      const prev = this.nodeMap.get(id)?.skip_numbering ?? false
      this.nodes = await api.batchUpdateNodes(this.procedureId, { [id]: { skip_numbering: !prev } })
      this._pushUndo(() => this.toggleSkip(id))
    },

    async batchSetLevel(ids: string[], level: number | null): Promise<void> {
      if (!this.procedureId || ids.length === 0) return
      const prev = new Map(ids.map((i) => [i, this.nodeMap.get(i)?.heading_level ?? null]))
      const updates: Record<string, { set_heading_level: true; heading_level: number | null }> = {}
      for (const i of ids) updates[i] = { set_heading_level: true, heading_level: level }
      this.nodes = await api.batchUpdateNodes(this.procedureId, updates)
      this._pushUndo(async () => {
        for (const [i, lv] of prev) await this.setLevel(i, lv)
      })
    },

    async confirmReview(id: string): Promise<void> {
      if (!this.procedureId) return
      // 空 change → 后端清该节点 review（routers/nodes.py :batch 无条件清 review）。
      this.nodes = await api.batchUpdateNodes(this.procedureId, { [id]: {} })
      // 确认动作不入撤销栈（清 review 不可逆且无害）。
    },

    async createNode(payload: import('@/types/node').NodeCreate): Promise<void> {
      if (!this.procedureId) return
      const created = await api.createNode(this.procedureId, payload)
      await this._refetch()
      this.selectedId = created.id
      this._pushUndo(() => this.removeNode(created.id))
    },

    async removeNode(id: string): Promise<void> {
      if (!this.procedureId) return
      const gone = this.nodeMap.get(id)
      await api.deleteNode(id)
      await this._refetch()
      if (this.selectedId === id) this.selectedId = this.nodes[0]?.id ?? null
      // 删除的撤销 = 重建（新 id，内容/层级/skip 还原；位置近似为末尾）。
      if (gone) {
        this._pushUndo(() =>
          this.createNode({
            body: gone.body,
            heading_level: gone.heading_level,
            kind: gone.kind,
            input_schema: gone.input_schema as import('@/types/node').InputSchema,
            attachment_marks: gone.attachment_marks,
            skip_numbering: gone.skip_numbering,
          }),
        )
      }
    },

    async reorder(orderedIds: string[]): Promise<void> {
      if (!this.procedureId) return
      const prevOrder = this.nodes.map((x) => x.id)
      await api.reorderNodes(this.procedureId, orderedIds)
      await this._refetch()
      this._pushUndo(() => this.reorder(prevOrder))
    },
```

注：结构编辑全程把 `this.nodes` 替换为服务端权威结果（`:batch` 返回全量；create/delete/reorder 后 `_refetch`），无需客户端重算派生/编号。错误（如网络）由 `http` 拦截器 toast；本层不吞异常（调用方/视图可 catch，B3a-2 处理）。

- [ ] **Step 4: 运行确认通过**

Run: `cd frontend && npx vitest run tests/unit/store/nodeEditor.spec.ts`
Expected: PASS（Task 3 的 4 + 本任务 7 = 11）。

- [ ] **Step 5: Commit**

```bash
git add src/store/nodeEditor.ts tests/unit/store/nodeEditor.spec.ts
git commit -m "feat(fe/nodeEditor): structural edits via :batch + create/delete/reorder (B3a-1)"
```

---

## Task 5: `nodeEditor` store — 内容编辑（PATCH body/表单）+ 撤销/重做

**Files:**
- Modify: `src/store/nodeEditor.ts`
- Test: `tests/unit/store/nodeEditor.spec.ts`（追加）

- [ ] **Step 1: 写失败测试**

Append to `tests/unit/store/nodeEditor.spec.ts`:

```typescript
describe('nodeEditor store — content edits + undo', () => {
  it('updateBody PATCHes with the node revision and updates that node only', async () => {
    listSpy.mockResolvedValue([n({ id: 'a', body: '<p>old</p>', revision: 4 })])
    patchSpy.mockResolvedValue(n({ id: 'a', body: '<p>new</p>', revision: 5 }))
    const store = useNodeEditorStore()
    await store.load('p1')
    await store.updateBody('a', '<p>new</p>')
    expect(patchSpy).toHaveBeenCalledWith('a', { body: '<p>new</p>' }, 4)
    expect(store.nodeMap.get('a')?.body).toBe('<p>new</p>')
    expect(store.nodeMap.get('a')?.revision).toBe(5)
  })

  it('updateForm PATCHes input_schema + attachment_marks', async () => {
    listSpy.mockResolvedValue([n({ id: 'a', kind: 'step', revision: 2 })])
    patchSpy.mockResolvedValue(n({ id: 'a', kind: 'step', revision: 3, input_schema: { type: 'NOTE' } }))
    const store = useNodeEditorStore()
    await store.load('p1')
    await store.updateForm('a', { type: 'NOTE' }, [])
    expect(patchSpy).toHaveBeenCalledWith('a', { input_schema: { type: 'NOTE' }, attachment_marks: [] }, 2)
  })

  it('undo of setLevel issues the inverse :batch', async () => {
    listSpy.mockResolvedValue([n({ id: 'a', heading_level: null, body: '<p>x</p>' })])
    batchSpy.mockResolvedValueOnce([n({ id: 'a', heading_level: 2, body: '<p>x</p>' })]) // do
    batchSpy.mockResolvedValueOnce([n({ id: 'a', heading_level: null, body: '<p>x</p>' })]) // undo
    const store = useNodeEditorStore()
    await store.load('p1')
    await store.setLevel('a', 2)
    expect(store.canUndo).toBe(true)
    await store.undo()
    expect(batchSpy).toHaveBeenLastCalledWith('p1', { a: { set_heading_level: true, heading_level: null } })
    expect(store.nodeMap.get('a')?.heading_level).toBe(null)
    expect(store.canUndo).toBe(false)
  })

  it('undo of updateBody restores the previous body', async () => {
    listSpy.mockResolvedValue([n({ id: 'a', body: '<p>old</p>', revision: 1 })])
    patchSpy.mockResolvedValueOnce(n({ id: 'a', body: '<p>new</p>', revision: 2 })) // do
    patchSpy.mockResolvedValueOnce(n({ id: 'a', body: '<p>old</p>', revision: 3 })) // undo
    const store = useNodeEditorStore()
    await store.load('p1')
    await store.updateBody('a', '<p>new</p>')
    await store.undo()
    expect(patchSpy).toHaveBeenLastCalledWith('a', { body: '<p>old</p>' }, 2)
    expect(store.nodeMap.get('a')?.body).toBe('<p>old</p>')
  })
})
```

- [ ] **Step 2: 运行确认失败**

Run: `cd frontend && npx vitest run tests/unit/store/nodeEditor.spec.ts`
Expected: FAIL — `updateBody`/`updateForm`/`undo`/`canUndo` 未定义（且 `_pushUndo` 仍是占位 → undo 测试失败）。

- [ ] **Step 3: 实现**

(a) Add the content-edit actions to the `actions` block of `src/store/nodeEditor.ts`:

```typescript
    async updateBody(id: string, body: string): Promise<void> {
      const node = this.nodeMap.get(id)
      if (!node) return
      const prevBody = node.body
      const updated = await api.patchNode(id, { body }, node.revision)
      this._replaceNode(updated)
      this._pushUndo(() => this.updateBody(id, prevBody))
    },

    async updateForm(
      id: string,
      inputSchema: import('@/types/node').InputSchema,
      attachmentMarks: import('@/types/node').AttachmentMark[],
    ): Promise<void> {
      const node = this.nodeMap.get(id)
      if (!node) return
      const prevSchema = node.input_schema as import('@/types/node').InputSchema
      const prevMarks = node.attachment_marks
      const updated = await api.patchNode(
        id,
        { input_schema: inputSchema, attachment_marks: attachmentMarks },
        node.revision,
      )
      this._replaceNode(updated)
      this._pushUndo(() => this.updateForm(id, prevSchema, prevMarks))
    },

    _replaceNode(updated: Node): void {
      const i = this.nodes.findIndex((x) => x.id === updated.id)
      if (i >= 0) this.nodes[i] = updated
    },
```

(b) Replace the Task-4 placeholder `_pushUndo` with the real implementation, and add `undo`/`redo` actions + `canUndo`/`canRedo` getters. The placeholder was:

```typescript
    _pushUndo(_inverse: InverseOp): void {
      void _inverse
    },
```

Replace it with:

```typescript
    _pushUndo(inverse: InverseOp): void {
      this.undoStack.push(inverse)
      if (this.undoStack.length > 100) this.undoStack.shift()
    },

    async undo(): Promise<void> {
      const inverse = this.undoStack.pop()
      if (!inverse) return
      this._suppressUndo = true
      try {
        await inverse()
      } finally {
        this._suppressUndo = false
      }
    },
```

And gate `_pushUndo` so that operations performed *during* an undo don't themselves get recorded — add a transient flag to state and guard:

In `State` add `_suppressUndo: boolean` (and init `false` in `state()`); then make `_pushUndo` early-return when suppressed:

```typescript
    _pushUndo(inverse: InverseOp): void {
      if (this._suppressUndo) return
      this.undoStack.push(inverse)
      if (this.undoStack.length > 100) this.undoStack.shift()
    },
```

Add getters:

```typescript
    canUndo(state): boolean {
      return state.undoStack.length > 0
    },
```

（说明：B3a-1 实现「线性撤销」——`undo()` 执行逆操作并出栈；逆操作本身经 `_suppressUndo` 不再入栈。`redo` 留到 B3a-2 与键盘/按钮一起接（YAGNI：本数据层先保证 undo 正确）。`redoStack` 字段保留备用。）

- [ ] **Step 4: 运行确认通过**

Run: `cd frontend && npx vitest run tests/unit/store/nodeEditor.spec.ts`
Expected: PASS（11 + 4 = 15）。

- [ ] **Step 5: Commit**

```bash
git add src/store/nodeEditor.ts tests/unit/store/nodeEditor.spec.ts
git commit -m "feat(fe/nodeEditor): content edits (PATCH body/form) + inverse-op undo (B3a-1)"
```

---

## Task 6: 全量前端回归 + 类型检查

**Files:** 无新增

- [ ] **Step 1: 跑全部前端测试**

Run: `cd frontend && npx vitest run`
Expected: 既有 spec 全绿（B3a-1 未动任何现有文件，纯增量）+ 新增 3 个 spec 文件（api/nodes 6 + utils/nodeTree ~9 + store/nodeEditor 15）全绿。记录新增/总数。

- [ ] **Step 2: 类型检查**

Run: `cd frontend && npx vue-tsc --noEmit`（若 `package.json` 有 `type-check`/`build` 脚本，用 `npm run type-check`）
Expected: 无 **新增** 类型错误（B3a-1 新文件类型干净；若仓库本就有先存 tsc error，逐条确认非新增）。

- [ ] **Step 3: Commit（若有修正）**

```bash
git add -A
git commit -m "chore(fe): type/regression fixes for B3a-1"
```

---

## 完成标准（B3a-1）

1. `src/api/nodes.ts` 覆盖 §4 六个端点，`.data` 解包、`PATCH` 带 `If-Match` revision、`:batch` 用 `set_heading_level` 标志。
2. `nodeEditor` store：`load` 取扁平 list；`rows` 按展开态折叠 + review/search 过滤、标题由 body 首块派生；结构编辑（setLevel/setKind/toggleSkip/batchSetLevel/confirmReview）走 `:batch` 并以全量结果替换 `nodes`；create/delete/reorder 后 re-GET；内容编辑（updateBody/updateForm）走 `PATCH`(revision) 单节点替换；`undo` 执行逆操作。
3. 全部经 vitest 单测（mock api/http），≥30 个断言级用例。
4. **零** UI / 路由 / flag / 现有文件改动——纯增量，app 行为不变，现有 spec 全绿。

## 交接给 B3a-2 的事实
- store 暴露：`load(pid)`、`rows`/`nodeMap`/`selectedNode`/`reviewCount`、`select`/`toggleExpand`、`setLevel`/`setKind`/`toggleSkip`/`batchSetLevel`/`confirmReview`/`createNode`/`removeNode`/`reorder`、`updateBody`/`updateForm`、`undo`/`canUndo`、`selection`(Set，待 B3a-2 接 batchMark)、`search`/`reviewOnly`。
- B3a-2 建 `NodeTreePanel`（行 = `store.rows[i]`，chip 调 `setLevel`/`setKind`，checkbox 经 `batchMark` 维护 `store.selection`，浮动条调 `batchSetLevel`，review 徽章读 `node.mark_status`、确认调 `confirmReview`，拖拽调 `reorder`）+ `NodeDetailPanel`（body 经 `RichTextEditor` 调 `updateBody`，step 表单调 `updateForm`），经 `?editor=node` flag 挂到 `ProcedureEditorView`，旧编辑器默认。
- redo + β 键盘（`Cmd+1..4`/`Tab`/`Cmd+Z`）+ δ markdown 留到后续；`redoStack` 字段已预留。
- 删除的撤销会产生新 id（已在 `removeNode` 备注）；如需保 id 稳定，B4 可加软恢复端点。
