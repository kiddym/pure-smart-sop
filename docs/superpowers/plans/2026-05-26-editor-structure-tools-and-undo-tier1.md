# Editor Structure-Tools Grouping & Undo Tier 1 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Co-locate 标记模式 with 层级标定 in the left panel, and make `deleteNode` + `moveCrossParent` snapshot-undoable by deferring them to the batch save (Tier 1 of the undo-boundary fix).

**Architecture:** Both changes are frontend-only. The undo Tier 1 work extends the existing snapshot machinery (`Snapshot` + `snapshot()`/`restore()`) with two deletion-id sets, rewrites two store actions from "ensureSaved → backend call → reload" to "pushUndo → local mutation," and wires `buildPayload` to send the deletion-id sets the API already accepts. The grouping change is pure UI relocation: the 标记模式 button moves from `EditorTopBar.vue` into a new 结构工具 row in `ChapterTreePanel.vue` alongside 层级标定.

**Tech Stack:** Vue 3 + Pinia + Element Plus, Vitest (`@vue/test-utils`, jsdom), TypeScript.

**Spec:** `docs/superpowers/specs/2026-05-26-editor-structure-tools-and-undo-boundary-design.md` (commit `6f22c9c`).

---

## File Map

**Modified:**
- `frontend/src/store/procedureEditor.ts` — extend `Snapshot` + `EditorDraftState` + state; rewrite `deleteNode` and `moveCrossParent`; update `snapshot`/`restore`/`isDirty`/`resetEditState`/`exportDraft`/`importDraft`/`buildPayload`.
- `frontend/src/components/editor/EditorTopBar.vue` — remove the 标记模式 button; tighten the undo button tooltip.
- `frontend/src/components/editor/ChapterTreePanel.vue` — add a 结构工具 row containing `[标记模式] [层级标定]`; fold the existing `.layer-entry` into it.
- `frontend/tests/unit/procedureEditorStore.spec.ts` — new test blocks for the deletion-set snapshot, `isDirty`, draft round-trip, `deleteNode` deferred behavior, `moveCrossParent` local behavior, `buildPayload` deletion payload + reset on save.
- `frontend/tests/unit/EditorTopBar.spec.ts` — assert 标记模式 button absent; assert undo tooltip text.
- `frontend/tests/unit/ChapterTreePanel.spec.ts` — assert 结构工具 row renders both buttons; clicking them toggles store modes mutually exclusively.

**Created:** none.

**Order rationale:** Phase A (store + tests) is the load-bearing change and is fully independent. Phase B (UI relocation) is small and safe to do last so any unexpected interaction with `markMode` shows up first against a clean store.

---

## Phase A — Tier 1 Undo Boundary (store)

### Task 1: Extend `Snapshot` + state with deletion-id sets

**Files:**
- Modify: `frontend/src/store/procedureEditor.ts:53-71` (Snapshot + EditorDraftState)
- Modify: `frontend/src/store/procedureEditor.ts:138-175` (State interface + state initializer)
- Modify: `frontend/src/store/procedureEditor.ts:369-376` (resetEditState)
- Modify: `frontend/src/store/procedureEditor.ts:423-442` (snapshot/restore)
- Modify: `frontend/src/store/procedureEditor.ts:370-376` cluster around `load()` clearing undo
- Test: `frontend/tests/unit/procedureEditorStore.spec.ts`

- [ ] **Step 1: Write the failing test**

Append a new `describe` block at the end of `frontend/tests/unit/procedureEditorStore.spec.ts`:

```ts
describe('snapshot / restore 包含删除集合', () => {
  it('snapshot 拷贝 deletedChapterIds / deletedStepIds；restore 恢复', () => {
    const s = seed()
    s.deletedChapterIds = new Set(['x', 'y'])
    s.deletedStepIds = new Set(['s'])
    const snap = s.snapshot()
    s.deletedChapterIds = new Set()
    s.deletedStepIds = new Set()
    s.restore(snap)
    expect([...s.deletedChapterIds].sort()).toEqual(['x', 'y'])
    expect([...s.deletedStepIds]).toEqual(['s'])
  })

  it('resetEditState 清空删除集合', () => {
    const s = seed()
    s.deletedChapterIds = new Set(['x'])
    s.deletedStepIds = new Set(['s'])
    s.resetEditState()
    expect(s.deletedChapterIds.size).toBe(0)
    expect(s.deletedStepIds.size).toBe(0)
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run tests/unit/procedureEditorStore.spec.ts -t '删除集合'`
Expected: FAIL — properties `deletedChapterIds` / `deletedStepIds` don't exist on the store.

- [ ] **Step 3: Extend the `Snapshot` interface**

In `frontend/src/store/procedureEditor.ts`, replace the `Snapshot` interface (lines 53–59):

```ts
interface Snapshot {
  chapters: EditorChapter[]
  steps: EditorStep[]
  dirtyChapters: string[]
  dirtySteps: string[]
  deletedChapterIds: string[]
  deletedStepIds: string[]
  metaDirty: boolean
}
```

- [ ] **Step 4: Extend the `EditorDraftState` interface**

In `frontend/src/store/procedureEditor.ts`, replace `EditorDraftState` (lines 62–71):

```ts
export interface EditorDraftState {
  procedure: ProcedureMeta | null
  chapters: EditorChapter[]
  steps: EditorStep[]
  selectedId: string | null
  expanded: Record<string, boolean>
  dirtyChapters: string[]
  dirtySteps: string[]
  deletedChapterIds: string[]
  deletedStepIds: string[]
  metaDirty: boolean
}
```

- [ ] **Step 5: Add the two sets to the `State` type**

In `frontend/src/store/procedureEditor.ts`, in the `State` interface (lines 138–153), add right after `dirtySteps`:

```ts
  deletedChapterIds: Set<string>
  deletedStepIds: Set<string>
```

- [ ] **Step 6: Initialize the two sets in `state()`**

In `frontend/src/store/procedureEditor.ts`, in the `state: (): State => ({ ... })` initializer (lines 156–175), add right after `dirtySteps: new Set<string>(),`:

```ts
    deletedChapterIds: new Set<string>(),
    deletedStepIds: new Set<string>(),
```

- [ ] **Step 7: Extend `snapshot()` and `restore()`**

In `frontend/src/store/procedureEditor.ts`, replace `snapshot()` and `restore()` (lines 423–442):

```ts
    snapshot(): Snapshot {
      return {
        chapters: clone(this.chapters),
        steps: clone(this.steps),
        dirtyChapters: [...this.dirtyChapters],
        dirtySteps: [...this.dirtySteps],
        deletedChapterIds: [...this.deletedChapterIds],
        deletedStepIds: [...this.deletedStepIds],
        metaDirty: this.metaDirty,
      }
    },

    restore(snap: Snapshot): void {
      this.chapters = clone(snap.chapters)
      this.steps = clone(snap.steps)
      this.dirtyChapters = new Set(snap.dirtyChapters)
      this.dirtySteps = new Set(snap.dirtySteps)
      this.deletedChapterIds = new Set(snap.deletedChapterIds)
      this.deletedStepIds = new Set(snap.deletedStepIds)
      this.metaDirty = snap.metaDirty
      if (this.selectedId && !this.chapterMap.has(this.selectedId) && !this.stepMap.has(this.selectedId)) {
        this.selectedId = this.firstNodeId()
      }
    },
```

- [ ] **Step 8: Clear the sets in `resetEditState()`**

In `frontend/src/store/procedureEditor.ts`, replace `resetEditState()` (lines 369–376):

```ts
    resetEditState(): void {
      this.dirtyChapters = new Set()
      this.dirtySteps = new Set()
      this.deletedChapterIds = new Set()
      this.deletedStepIds = new Set()
      this.metaDirty = false
      this.undoStack = []
      this.redoStack = []
      this.lastUndoTag = null
    },
```

- [ ] **Step 9: Run test to verify it passes**

Run: `cd frontend && npx vitest run tests/unit/procedureEditorStore.spec.ts -t '删除集合'`
Expected: PASS, both `it` blocks green.

- [ ] **Step 10: Commit**

```bash
git add frontend/src/store/procedureEditor.ts frontend/tests/unit/procedureEditorStore.spec.ts
git commit -m "feat(editor): add deletedChapterIds/deletedStepIds to snapshot + state"
```

---

### Task 2: Extend `isDirty` to include pending deletions

**Files:**
- Modify: `frontend/src/store/procedureEditor.ts:182-184` (isDirty getter)
- Test: `frontend/tests/unit/procedureEditorStore.spec.ts`

- [ ] **Step 1: Write the failing test**

Append to the `describe('snapshot / restore 包含删除集合', ...)` block in the test file (or alongside it):

```ts
describe('isDirty 含待删除', () => {
  it('deletedChapterIds 非空时 isDirty 为 true', () => {
    const s = seed()
    expect(s.isDirty).toBe(false)
    s.deletedChapterIds = new Set(['x'])
    expect(s.isDirty).toBe(true)
  })

  it('deletedStepIds 非空时 isDirty 为 true', () => {
    const s = seed()
    s.deletedStepIds = new Set(['s'])
    expect(s.isDirty).toBe(true)
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run tests/unit/procedureEditorStore.spec.ts -t 'isDirty 含待删除'`
Expected: FAIL — `isDirty` returns `false` even with non-empty deletion sets.

- [ ] **Step 3: Extend the `isDirty` getter**

In `frontend/src/store/procedureEditor.ts`, replace `isDirty` (lines 182–184):

```ts
    isDirty(state): boolean {
      return (
        state.dirtyChapters.size > 0
        || state.dirtySteps.size > 0
        || state.deletedChapterIds.size > 0
        || state.deletedStepIds.size > 0
        || state.metaDirty
      )
    },
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run tests/unit/procedureEditorStore.spec.ts -t 'isDirty 含待删除'`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/store/procedureEditor.ts frontend/tests/unit/procedureEditorStore.spec.ts
git commit -m "feat(editor): isDirty includes pending deletions"
```

---

### Task 3: Round-trip deletion sets through `exportDraft` / `importDraft`

**Files:**
- Modify: `frontend/src/store/procedureEditor.ts:830-855` (exportDraft, importDraft)
- Test: `frontend/tests/unit/procedureEditorStore.spec.ts`

- [ ] **Step 1: Write the failing test**

Append a new `describe`:

```ts
describe('exportDraft / importDraft 含删除集合', () => {
  it('exportDraft 导出 deletedChapterIds / deletedStepIds', () => {
    const s = seed()
    s.deletedChapterIds = new Set(['x', 'y'])
    s.deletedStepIds = new Set(['s'])
    const draft = s.exportDraft()
    expect([...draft.deletedChapterIds].sort()).toEqual(['x', 'y'])
    expect(draft.deletedStepIds).toEqual(['s'])
  })

  it('importDraft 还原 deletedChapterIds / deletedStepIds', () => {
    const s = seed()
    const s2 = useProcedureEditorStore()
    s2.importDraft({
      procedure: meta(),
      chapters: [chap('a', null, 0)],
      steps: [],
      selectedId: null,
      expanded: {},
      dirtyChapters: [],
      dirtySteps: [],
      deletedChapterIds: ['x'],
      deletedStepIds: ['s'],
      metaDirty: false,
    })
    expect([...s2.deletedChapterIds]).toEqual(['x'])
    expect([...s2.deletedStepIds]).toEqual(['s'])
    // importDraft 历来清 undo 栈：保持原有契约
    expect(s2.undoStack).toEqual([])
    expect(s2.redoStack).toEqual([])
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run tests/unit/procedureEditorStore.spec.ts -t 'exportDraft / importDraft 含删除集合'`
Expected: FAIL — `exportDraft` return shape missing the new fields; `importDraft` payload type mismatch.

- [ ] **Step 3: Extend `exportDraft()`**

In `frontend/src/store/procedureEditor.ts`, replace `exportDraft()` (lines 830–841):

```ts
    exportDraft(): EditorDraftState {
      return {
        procedure: clone(this.procedure),
        chapters: clone(this.chapters),
        steps: clone(this.steps),
        selectedId: this.selectedId,
        expanded: { ...this.expanded },
        dirtyChapters: [...this.dirtyChapters],
        dirtySteps: [...this.dirtySteps],
        deletedChapterIds: [...this.deletedChapterIds],
        deletedStepIds: [...this.deletedStepIds],
        metaDirty: this.metaDirty,
      }
    },
```

- [ ] **Step 4: Extend `importDraft()`**

In `frontend/src/store/procedureEditor.ts`, replace `importDraft()` (lines 843–855):

```ts
    importDraft(d: EditorDraftState): void {
      if (d.procedure) this.procedure = clone(d.procedure)
      this.chapters = clone(d.chapters)
      this.steps = clone(d.steps)
      this.selectedId = d.selectedId
      this.expanded = { ...d.expanded }
      this.dirtyChapters = new Set(d.dirtyChapters)
      this.dirtySteps = new Set(d.dirtySteps)
      this.deletedChapterIds = new Set(d.deletedChapterIds)
      this.deletedStepIds = new Set(d.deletedStepIds)
      this.metaDirty = d.metaDirty
      this.undoStack = []
      this.redoStack = []
      this.lastUndoTag = null
    },
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd frontend && npx vitest run tests/unit/procedureEditorStore.spec.ts -t 'exportDraft / importDraft 含删除集合'`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/store/procedureEditor.ts frontend/tests/unit/procedureEditorStore.spec.ts
git commit -m "feat(editor): round-trip deletion sets through sessionStorage draft"
```

---

### Task 4: Rewrite `deleteNode` as deferred-local + undoable

**Files:**
- Modify: `frontend/src/store/procedureEditor.ts:667-679` (deleteNode)
- Test: `frontend/tests/unit/procedureEditorStore.spec.ts` (also extend mocks to spy deleteChapter / deleteStep)

- [ ] **Step 1: Hoist `deleteChapter` and `deleteStep` spies in the test file mock**

In `frontend/tests/unit/procedureEditorStore.spec.ts`, replace the `vi.hoisted` block (line 8) and the two relevant mocks (lines 9–17). Keep `markSpy` and `saveSpy` (already present); add `deleteChapterSpy` and `deleteStepSpy`:

```ts
const { markSpy, saveSpy, deleteChapterSpy, deleteStepSpy } = vi.hoisted(() => ({
  markSpy: vi.fn(),
  saveSpy: vi.fn(),
  deleteChapterSpy: vi.fn(),
  deleteStepSpy: vi.fn(),
}))
vi.mock('@/api/chapters', () => ({
  setChapterMarkStatus: markSpy,
  createChapter: vi.fn(),
  deleteChapter: deleteChapterSpy,
  moveChapter: vi.fn(),
  convertChapterToStep: vi.fn(),
  convertRootToStep: vi.fn(),
}))
vi.mock('@/api/steps', () => ({ deleteStep: deleteStepSpy, moveStep: vi.fn(), convertStepToChapter: vi.fn() }))
```

In the existing `beforeEach` (lines 107–111), add:

```ts
  deleteChapterSpy.mockReset().mockResolvedValue({})
  deleteStepSpy.mockReset().mockResolvedValue({})
```

- [ ] **Step 2: Write the failing test**

Append a new `describe`:

```ts
describe('deleteNode 本地化（Tier 1）', () => {
  it('删除已存章节：记录 id 到 deletedChapterIds，不发请求', async () => {
    const s = seed()
    await s.deleteNode('a')
    expect([...s.deletedChapterIds]).toEqual(['a'])
    expect(deleteChapterSpy).not.toHaveBeenCalled()
    expect(s.chapterMap.has('a')).toBe(false)
  })

  it('删除已存章节可撤销：undo 还原章节和删除集合', async () => {
    const s = seed()
    await s.deleteNode('a')
    s.undo()
    expect(s.chapterMap.has('a')).toBe(true)
    expect(s.deletedChapterIds.size).toBe(0)
  })

  it('删除临时章节：不进入 deletedChapterIds（后端无此节点）', async () => {
    const s = seed()
    const tmp = s.addChapterNode('a')
    await s.deleteNode(tmp)
    expect(s.deletedChapterIds.size).toBe(0)
    expect(s.chapterMap.has(tmp)).toBe(false)
    expect(deleteChapterSpy).not.toHaveBeenCalled()
  })

  it('删除子树：所有已存后代章节 + 已存子步骤都进入对应删除集合，临时子节点忽略', async () => {
    const s = seed()
    // 已存父 a；已存子 a1；a1 下临时孙 a1t；a 下已存步骤 stepX；a1 下临时步骤 stepT
    s.chapters = [chap('a', null, 0), chap('a1', 'a', 0)]
    const tmpGrandchild = s.addChapterNode('a1')   // 临时
    s.steps = [stp('stepX', 'a', 0), stp('stepT_real', 'a1', 0)]
    const tmpStep = s.addStepNode('a1')             // 临时
    await s.deleteNode('a')
    expect([...s.deletedChapterIds].sort()).toEqual(['a', 'a1'])
    expect([...s.deletedStepIds].sort()).toEqual(['stepT_real', 'stepX'])
    // 临时节点不进入删除集合
    expect(s.deletedChapterIds.has(tmpGrandchild)).toBe(false)
    expect(s.deletedStepIds.has(tmpStep)).toBe(false)
    // 本地完全移除
    expect(s.chapterMap.has('a')).toBe(false)
    expect(s.chapterMap.has('a1')).toBe(false)
    expect(s.stepMap.has('stepX')).toBe(false)
  })

  it('删除已存步骤：记录 id 到 deletedStepIds，不发请求', async () => {
    const s = seed()
    s.steps = [stp('s1', 'a', 0)]
    await s.deleteNode('s1')
    expect([...s.deletedStepIds]).toEqual(['s1'])
    expect(deleteStepSpy).not.toHaveBeenCalled()
    expect(s.stepMap.has('s1')).toBe(false)
  })
})
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd frontend && npx vitest run tests/unit/procedureEditorStore.spec.ts -t 'deleteNode 本地化'`
Expected: FAIL — current `deleteNode` calls `deleteChapterApi`/`deleteStepApi` (or for persisted nodes calls `ensureSaved` + backend); deletion sets stay empty.

- [ ] **Step 4: Rewrite `deleteNode` in the store**

In `frontend/src/store/procedureEditor.ts`, replace `deleteNode` (lines 667–679). Note: the existing top-comment about "立即后端转换 / 移动 / 标记" (line 681) belongs to `ensureSaved` and the still-immediate ops below — leave that comment unchanged. Remove the imports of `deleteChapterApi` / `deleteStepApi` from `@/api/chapters` and `@/api/steps` if and only if they are no longer used elsewhere in the file (verify with a quick grep before deleting any import):

```ts
    // 删除节点：纯本地，已存节点的真实 id（含子树中的已存后代 / 已存步骤）记入待删除集合，
    // 由下次 save 经 buildPayload 一并提交。可撤销。
    deleteNode(id: string): void {
      this.pushUndo()
      const ch = this.chapterMap.get(id)
      if (ch) {
        const subtreeChapterIds = this.collectSubtree(id)
        for (const cid of subtreeChapterIds) {
          if (!isTempId(cid)) this.deletedChapterIds.add(cid)
        }
        for (const st of this.steps) {
          if (st.chapter_id && subtreeChapterIds.has(st.chapter_id) && !isTempId(st.id)) {
            this.deletedStepIds.add(st.id)
          }
        }
      } else if (this.stepMap.has(id)) {
        if (!isTempId(id)) this.deletedStepIds.add(id)
      }
      this.removeNodeLocal(id)
    },
```

Note the signature change: `deleteNode` is no longer `async`. If any caller `await`s it, the await becomes a no-op — that's fine for callers but verify with grep that no caller chains `.then()` or expects the returned `Promise`:

```bash
cd frontend && grep -rn "deleteNode" src tests | grep -v "procedureEditor.ts"
```

If any caller chains `.then` or relies on the async signature, update it to call synchronously in the same task.

- [ ] **Step 5: Run test to verify it passes**

Run: `cd frontend && npx vitest run tests/unit/procedureEditorStore.spec.ts -t 'deleteNode 本地化'`
Expected: PASS, all 5 `it` blocks green.

- [ ] **Step 6: Run the full store test file to catch regressions**

Run: `cd frontend && npx vitest run tests/unit/procedureEditorStore.spec.ts`
Expected: All tests pass. If any existing test fails because it asserted `deleteChapterApi` was called or `await s.deleteNode(...)` semantics, update those tests to the new local model (they were testing the now-removed behavior).

- [ ] **Step 7: Commit**

```bash
git add frontend/src/store/procedureEditor.ts frontend/tests/unit/procedureEditorStore.spec.ts
git commit -m "feat(editor): deleteNode is now local + undoable; deletion deferred to save"
```

---

### Task 5: Rewrite `moveCrossParent` as local + undoable

**Files:**
- Modify: `frontend/src/store/procedureEditor.ts:715-725` (moveCrossParent)
- Test: `frontend/tests/unit/procedureEditorStore.spec.ts` (extend mocks)

- [ ] **Step 1: Hoist `moveChapter` / `moveStep` spies in the test file mock**

In `frontend/tests/unit/procedureEditorStore.spec.ts`, extend the `vi.hoisted` block from Task 4 with two more spies:

```ts
const { markSpy, saveSpy, deleteChapterSpy, deleteStepSpy, moveChapterSpy, moveStepSpy } = vi.hoisted(() => ({
  markSpy: vi.fn(),
  saveSpy: vi.fn(),
  deleteChapterSpy: vi.fn(),
  deleteStepSpy: vi.fn(),
  moveChapterSpy: vi.fn(),
  moveStepSpy: vi.fn(),
}))
```

Update the `@/api/chapters` and `@/api/steps` mocks accordingly:

```ts
vi.mock('@/api/chapters', () => ({
  setChapterMarkStatus: markSpy,
  createChapter: vi.fn(),
  deleteChapter: deleteChapterSpy,
  moveChapter: moveChapterSpy,
  convertChapterToStep: vi.fn(),
  convertRootToStep: vi.fn(),
}))
vi.mock('@/api/steps', () => ({ deleteStep: deleteStepSpy, moveStep: moveStepSpy, convertStepToChapter: vi.fn() }))
```

And add to `beforeEach`:

```ts
  moveChapterSpy.mockReset().mockResolvedValue({})
  moveStepSpy.mockReset().mockResolvedValue({})
```

- [ ] **Step 2: Write the failing test**

Append a new `describe`:

```ts
describe('moveCrossParent 本地化（Tier 1）', () => {
  it('章节跨父：parent_id 与两侧 sort_order 重排，置脏，不发请求', async () => {
    const s = seed()
    // 两个根：a（含 a1, a2）、b（含 b1）
    s.chapters = [
      chap('a', null, 0),
      chap('b', null, 1),
      chap('a1', 'a', 0),
      chap('a2', 'a', 1),
      chap('b1', 'b', 0),
    ]
    // 把 a1 移到 b 下，索引 0（变成 b 的首子）
    await s.moveCrossParent('a1', 'b', 0)
    expect(moveChapterSpy).not.toHaveBeenCalled()
    expect(s.chapterMap.get('a1')!.parent_id).toBe('b')
    // 新父组 (b 下) 应为 [a1, b1]，sort_order 0..1
    const bGroup = s.chapters.filter((c) => c.parent_id === 'b').sort((x, y) => x.sort_order - y.sort_order)
    expect(bGroup.map((c) => c.id)).toEqual(['a1', 'b1'])
    expect(bGroup.map((c) => c.sort_order)).toEqual([0, 1])
    // 原父组 (a 下) 应只剩 a2，sort_order 重排为 0
    const aGroup = s.chapters.filter((c) => c.parent_id === 'a').sort((x, y) => x.sort_order - y.sort_order)
    expect(aGroup.map((c) => c.id)).toEqual(['a2'])
    expect(aGroup.map((c) => c.sort_order)).toEqual([0])
    // 三个被触碰的章节都进入 dirty
    expect(s.dirtyChapters.has('a1')).toBe(true)
    expect(s.dirtyChapters.has('a2')).toBe(true)
    expect(s.dirtyChapters.has('b1')).toBe(true)
  })

  it('章节跨父可撤销', async () => {
    const s = seed()
    s.chapters = [
      chap('a', null, 0),
      chap('b', null, 1),
      chap('a1', 'a', 0),
    ]
    await s.moveCrossParent('a1', 'b', 0)
    s.undo()
    expect(s.chapterMap.get('a1')!.parent_id).toBe('a')
    expect(s.chapterMap.get('a1')!.sort_order).toBe(0)
  })

  it('步骤跨父：chapter_id 与两侧 sort_order 重排，置脏，不发请求', async () => {
    const s = seed()
    s.steps = [stp('s1', 'a', 0), stp('s2', 'a', 1), stp('s3', 'b', 0)]
    await s.moveCrossParent('s1', 'b', 1)
    expect(moveStepSpy).not.toHaveBeenCalled()
    expect(s.stepMap.get('s1')!.chapter_id).toBe('b')
    const bSteps = s.steps.filter((x) => x.chapter_id === 'b').sort((x, y) => x.sort_order - y.sort_order)
    expect(bSteps.map((x) => x.id)).toEqual(['s3', 's1'])
    expect(bSteps.map((x) => x.sort_order)).toEqual([0, 1])
    const aSteps = s.steps.filter((x) => x.chapter_id === 'a').sort((x, y) => x.sort_order - y.sort_order)
    expect(aSteps.map((x) => x.id)).toEqual(['s2'])
    expect(aSteps.map((x) => x.sort_order)).toEqual([0])
    expect(s.dirtySteps.has('s1')).toBe(true)
    expect(s.dirtySteps.has('s2')).toBe(true)
    expect(s.dirtySteps.has('s3')).toBe(true)
  })
})
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd frontend && npx vitest run tests/unit/procedureEditorStore.spec.ts -t 'moveCrossParent 本地化'`
Expected: FAIL — current `moveCrossParent` calls `moveChapterApi`/`moveStepApi` (via the mocked spies), so `moveChapterSpy`/`moveStepSpy` get called.

- [ ] **Step 4: Rewrite `moveCrossParent` in the store**

In `frontend/src/store/procedureEditor.ts`, replace `moveCrossParent` (lines 715–725). Note: keep the `ensureSaved` helper above (lines 683–685) — it's still used by `convertToStep` / `convertRootToStep` / `convertToChapter` / `cycleMark` / `applyAllMarks`. Only `deleteNode` and `moveCrossParent` move off it.

```ts
    // 跨父移动：本地写 parent_id (或 chapter_id) + 两侧组重排 sort_order，置脏，可撤销。
    // 客户端 DnD 层（utils/treeDnd.ts）已挡住环 / 三级深度 / Q25 同父类型互斥，store 不再二次校验。
    moveCrossParent(id: string, targetParentId: string | null, targetIndex: number): void {
      const ch = this.chapterMap.get(id)
      const st = ch ? null : this.stepMap.get(id)
      if (!ch && !st) return
      this.pushUndo()
      if (ch) {
        const oldParent = ch.parent_id
        ch.parent_id = targetParentId
        this.resequenceChapterGroup(oldParent)
        this.resequenceChapterGroupWithInsert(targetParentId, id, targetIndex)
      } else {
        const oldChapter = st!.chapter_id
        st!.chapter_id = targetParentId
        this.resequenceStepGroup(oldChapter)
        this.resequenceStepGroupWithInsert(targetParentId, id, targetIndex)
      }
    },

    // 把指定 parent_id 下的章节按当前顺序重写 sort_order = 0..n，全部置脏。
    resequenceChapterGroup(parentId: string | null): void {
      const group = this.chapters
        .filter((c) => c.parent_id === parentId)
        .sort((a, b) => (a.sort_order !== b.sort_order ? a.sort_order - b.sort_order : a.id < b.id ? -1 : 1))
      group.forEach((c, i) => {
        c.sort_order = i
        this.dirtyChapters.add(c.id)
      })
    },

    // 把指定 parent_id 下的章节排序后，将 movedId 插入到 targetIndex，重写 sort_order = 0..n，全部置脏。
    resequenceChapterGroupWithInsert(parentId: string | null, movedId: string, targetIndex: number): void {
      const cmp = (a: EditorChapter, b: EditorChapter): number =>
        a.sort_order !== b.sort_order ? a.sort_order - b.sort_order : a.id < b.id ? -1 : 1
      const others = this.chapters.filter((c) => c.parent_id === parentId && c.id !== movedId).sort(cmp)
      const moved = this.chapterMap.get(movedId)
      if (!moved) return
      const clamped = Math.max(0, Math.min(targetIndex, others.length))
      others.splice(clamped, 0, moved)
      others.forEach((c, i) => {
        c.sort_order = i
        this.dirtyChapters.add(c.id)
      })
    },

    resequenceStepGroup(chapterId: string | null): void {
      const group = this.steps
        .filter((s) => s.chapter_id === chapterId)
        .sort((a, b) => (a.sort_order !== b.sort_order ? a.sort_order - b.sort_order : a.id < b.id ? -1 : 1))
      group.forEach((st, i) => {
        st.sort_order = i
        this.dirtySteps.add(st.id)
      })
    },

    resequenceStepGroupWithInsert(chapterId: string | null, movedId: string, targetIndex: number): void {
      const cmp = (a: EditorStep, b: EditorStep): number =>
        a.sort_order !== b.sort_order ? a.sort_order - b.sort_order : a.id < b.id ? -1 : 1
      const others = this.steps.filter((s) => s.chapter_id === chapterId && s.id !== movedId).sort(cmp)
      const moved = this.stepMap.get(movedId)
      if (!moved) return
      const clamped = Math.max(0, Math.min(targetIndex, others.length))
      others.splice(clamped, 0, moved)
      others.forEach((st, i) => {
        st.sort_order = i
        this.dirtySteps.add(st.id)
      })
    },
```

Signature change: `moveCrossParent` is no longer `async`. Verify callers with:

```bash
cd frontend && grep -rn "moveCrossParent" src tests | grep -v "procedureEditor.ts"
```

The DnD caller in `ChapterTreePanel.vue:205-217` currently calls `store.moveCrossParent(...)` (possibly inside an `await` or `.then` after a confirm). The new sync signature still works inside an async context — `await store.moveCrossParent(...)` becomes `await undefined`, which is fine. If a caller relied on the returned `Promise`, change it to a plain call.

- [ ] **Step 5: Run test to verify it passes**

Run: `cd frontend && npx vitest run tests/unit/procedureEditorStore.spec.ts -t 'moveCrossParent 本地化'`
Expected: PASS, all 3 `it` blocks green.

- [ ] **Step 6: Run the full store test file**

Run: `cd frontend && npx vitest run tests/unit/procedureEditorStore.spec.ts`
Expected: All tests pass. Update any pre-existing test that asserted `moveChapter`/`moveStep` API calls (they're no longer made).

- [ ] **Step 7: Commit**

```bash
git add frontend/src/store/procedureEditor.ts frontend/tests/unit/procedureEditorStore.spec.ts
git commit -m "feat(editor): moveCrossParent is now local + undoable; sync on save"
```

---

### Task 6: Wire `buildPayload` to send deletion sets; verify they clear on save

**Files:**
- Modify: `frontend/src/store/procedureEditor.ts:905-906` (buildPayload return — populate deleted_*_ids)
- Test: `frontend/tests/unit/procedureEditorStore.spec.ts`

- [ ] **Step 1: Write the failing test**

Append a new `describe`:

```ts
describe('buildPayload + save 链路含删除集合', () => {
  it('buildPayload 输出 deleted_chapter_ids / deleted_step_ids', () => {
    const s = seed()
    s.deletedChapterIds = new Set(['x', 'y'])
    s.deletedStepIds = new Set(['s'])
    const payload = s.buildPayload()
    expect([...payload.deleted_chapter_ids].sort()).toEqual(['x', 'y'])
    expect(payload.deleted_step_ids).toEqual(['s'])
  })

  it('save 成功后删除集合清空', async () => {
    const s = seed()
    // 触发 isDirty 让 save 真正发起：先标一笔 dirty
    s.updateChapterFields('a', { title: '改名' })
    s.deletedChapterIds = new Set(['x'])
    s.deletedStepIds = new Set(['s'])
    saveSpy.mockResolvedValue({ ...meta(), revision: 4, id_map: {} })
    await s.save()
    expect(s.deletedChapterIds.size).toBe(0)
    expect(s.deletedStepIds.size).toBe(0)
    // 同时 payload 在 save 调用时确实带了删除 id
    const calledPayload = saveSpy.mock.calls[0][1]
    expect(calledPayload.deleted_chapter_ids).toEqual(['x'])
    expect(calledPayload.deleted_step_ids).toEqual(['s'])
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run tests/unit/procedureEditorStore.spec.ts -t 'buildPayload \+ save 链路'`
Expected: FAIL — `buildPayload` still hardcodes `deleted_chapter_ids: []` and `deleted_step_ids: []`.

- [ ] **Step 3: Update `buildPayload` to emit the deletion sets**

In `frontend/src/store/procedureEditor.ts`, in `buildPayload()` (lines 894–907), replace the two hardcoded empty arrays:

```ts
        deleted_chapter_ids: [...this.deletedChapterIds],
        deleted_step_ids: [...this.deletedStepIds],
```

(`resetEditState`, which already clears the dirty sets, will also clear the deletion sets thanks to Task 1 Step 8 — no further save-path change required.)

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run tests/unit/procedureEditorStore.spec.ts -t 'buildPayload \+ save 链路'`
Expected: PASS, both `it` blocks green.

- [ ] **Step 5: Run the full store test file**

Run: `cd frontend && npx vitest run tests/unit/procedureEditorStore.spec.ts`
Expected: All tests pass.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/store/procedureEditor.ts frontend/tests/unit/procedureEditorStore.spec.ts
git commit -m "feat(editor): buildPayload emits deleted_*_ids; resetEditState clears them on save"
```

---

### Task 7: Tighten the undo button tooltip

**Files:**
- Modify: `frontend/src/components/editor/EditorTopBar.vue:44` (undo button title)
- Test: `frontend/tests/unit/EditorTopBar.spec.ts`

- [ ] **Step 1: Write the failing test**

In `frontend/tests/unit/EditorTopBar.spec.ts`, after the existing `describe`, add:

```ts
describe('EditorTopBar · 撤销按钮 tooltip', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('title 标明范围限于大纲结构', () => {
    seedEditable()
    const w = mount(EditorTopBar, { global: { plugins: [ElementPlus] } })
    const undoBtn = w.findAll('button').find((b) => b.text() === '↶')
    expect(undoBtn).toBeTruthy()
    const title = undoBtn!.attributes('title') ?? ''
    expect(title).toContain('撤销')
    expect(title).toContain('Ctrl+Z')
    expect(title).toContain('大纲结构')
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run tests/unit/EditorTopBar.spec.ts -t '撤销按钮 tooltip'`
Expected: FAIL — current title is `"撤销 (Ctrl+Z)"`, missing `大纲结构`.

- [ ] **Step 3: Update the tooltip**

In `frontend/src/components/editor/EditorTopBar.vue`, replace line 44:

```html
        <el-button size="small" :disabled="!canUndo" title="撤销大纲结构 (Ctrl+Z) · 类型转换 / 标记应用 不在范围内" @click="store.undo()">↶</el-button>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run tests/unit/EditorTopBar.spec.ts -t '撤销按钮 tooltip'`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/editor/EditorTopBar.vue frontend/tests/unit/EditorTopBar.spec.ts
git commit -m "feat(editor): clarify undo button scope in tooltip"
```

---

## Phase B — Mode Grouping (UI)

### Task 8: Remove 标记模式 button from `EditorTopBar.vue`

**Files:**
- Modify: `frontend/src/components/editor/EditorTopBar.vue:47-53` (delete the 标记模式 button)
- Test: `frontend/tests/unit/EditorTopBar.spec.ts`

- [ ] **Step 1: Write the failing test**

Append to `frontend/tests/unit/EditorTopBar.spec.ts`:

```ts
describe('EditorTopBar · 标记模式按钮已移除', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('顶栏不再渲染「标记模式」按钮', () => {
    seedEditable()
    const w = mount(EditorTopBar, { global: { plugins: [ElementPlus] } })
    const btn = w.findAll('button').find((b) => b.text().includes('标记模式'))
    expect(btn).toBeFalsy()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run tests/unit/EditorTopBar.spec.ts -t '标记模式按钮已移除'`
Expected: FAIL — the button still exists.

- [ ] **Step 3: Delete the 标记模式 button from the template**

In `frontend/src/components/editor/EditorTopBar.vue`, delete the entire 标记模式 `<el-button>` block (lines 47–53):

```html
      <el-button
        size="small"
        :type="store.markMode ? 'primary' : 'default'"
        @click="store.toggleMarkMode()"
      >
        标记模式
      </el-button>
```

Leave everything else in the `.right` div as-is (PDF 预览 / 保存 / 发布 / ⋮).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run tests/unit/EditorTopBar.spec.ts`
Expected: All tests in this file pass (including the existing PDF 预览 test and the tooltip test from Task 7).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/editor/EditorTopBar.vue frontend/tests/unit/EditorTopBar.spec.ts
git commit -m "refactor(editor): remove 标记模式 button from top bar (moves to tree panel)"
```

---

### Task 9: Add 结构工具 row to `ChapterTreePanel.vue`

**Files:**
- Modify: `frontend/src/components/editor/ChapterTreePanel.vue:321-325` (replace `.layer-entry` with a `.structure-tools` row holding both buttons)
- Modify: `frontend/src/components/editor/ChapterTreePanel.vue:385-392` (extend the shared CSS selector list)
- Test: `frontend/tests/unit/ChapterTreePanel.spec.ts`

- [ ] **Step 1: Write the failing test**

Append to `frontend/tests/unit/ChapterTreePanel.spec.ts`:

```ts
describe('ChapterTreePanel · 结构工具行（标记模式 + 层级标定）', () => {
  it('渲染两枚互斥按钮：标记模式 + 层级标定', () => {
    setActivePinia(createPinia())
    const store = useProcedureEditorStore()
    store.procedure = meta()
    store.chapters = [chapter('c1', '总则', null, 0)]
    const w = mount(ChapterTreePanel, { global: { plugins: [ElementPlus] } })
    const tools = w.find('.structure-tools')
    expect(tools.exists()).toBe(true)
    expect(tools.text()).toContain('标记模式')
    expect(tools.text()).toContain('层级标定')
  })

  it('点击「标记模式」进入 markMode；再点「层级标定」自动退出 markMode 进入 layerMode', async () => {
    setActivePinia(createPinia())
    const store = useProcedureEditorStore()
    store.procedure = meta()
    store.chapters = [chapter('c1', '总则', null, 0)]
    const w = mount(ChapterTreePanel, { global: { plugins: [ElementPlus] } })
    const tools = w.find('.structure-tools')
    const markBtn = tools.findAll('button').find((b) => b.text().includes('标记模式'))!
    const layerBtn = tools.findAll('button').find((b) => b.text().includes('层级标定'))!
    await markBtn.trigger('click')
    expect(store.markMode).toBe(true)
    expect(store.layerMode).toBe(false)
    await layerBtn.trigger('click')
    expect(store.markMode).toBe(false)
    expect(store.layerMode).toBe(true)
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run tests/unit/ChapterTreePanel.spec.ts -t '结构工具行'`
Expected: FAIL — `.structure-tools` selector returns no node; 标记模式 isn't in the panel.

- [ ] **Step 3: Replace the `.layer-entry` block with a `.structure-tools` row**

In `frontend/src/components/editor/ChapterTreePanel.vue`, replace lines 321–325 (the `<div v-if="store.editable" class="layer-entry">…</div>` block) with:

```html
      <div v-if="store.editable" class="structure-tools">
        <span class="structure-tools-label">结构工具：</span>
        <el-button
          size="small"
          :type="store.markMode ? 'primary' : 'default'"
          @click="store.toggleMarkMode()"
        >
          {{ store.markMode ? '退出标记模式' : '标记模式' }}
        </el-button>
        <el-button
          size="small"
          :type="store.layerMode ? 'primary' : 'default'"
          @click="store.toggleLayerMode()"
        >
          {{ store.layerMode ? '退出层级标定' : '层级标定' }}
        </el-button>
      </div>
```

Then in the `<style scoped>` section, replace the existing shared selector (lines 385–392):

```css
.layer-entry,
.root-add,
.mark-bar {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
}
```

with:

```css
.structure-tools,
.root-add,
.mark-bar {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
}
.structure-tools-label {
  font-size: 12px;
  color: #909399;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run tests/unit/ChapterTreePanel.spec.ts -t '结构工具行'`
Expected: PASS, both `it` blocks green.

- [ ] **Step 5: Run the full ChapterTreePanel test file to catch regressions**

Run: `cd frontend && npx vitest run tests/unit/ChapterTreePanel.spec.ts`
Expected: All tests pass.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/editor/ChapterTreePanel.vue frontend/tests/unit/ChapterTreePanel.spec.ts
git commit -m "feat(editor): group 标记模式 + 层级标定 in left-panel 结构工具 row"
```

---

## Final Verification

- [ ] **Step 1: Run the full frontend test suite**

Run: `cd frontend && npm run test`
Expected: All tests pass.

- [ ] **Step 2: Run the type checker**

Run: `cd frontend && npx vue-tsc --noEmit`
Expected: No type errors. (If the project has a `typecheck` script, prefer that.)

- [ ] **Step 3: Manual smoke (optional, recommended)**

In the running app:
1. Open a procedure editor → confirm 标记模式 is no longer in the top bar and is in the left panel next to 层级标定.
2. Add a temp chapter, delete it, press Ctrl+Z → temp chapter returns; no network call fired.
3. Add a chapter, save, then delete it → click 保存 → confirm the request payload contains the deleted id in `deleted_chapter_ids` and the chapter is gone on reload.
4. Drag a chapter to a different parent → confirm no network call fires until 保存; Ctrl+Z reverses the move.
5. Hover the undo (↶) button → tooltip mentions 大纲结构 + Ctrl+Z + the excluded ops.

- [ ] **Step 4: Push branch**

Run: `git push -u origin feat/structure-tools-grouping-and-undo-tier1`

---

## Spec Self-Review (against `docs/superpowers/specs/2026-05-26-editor-structure-tools-and-undo-boundary-design.md`)

- Part 1 grouping: ✅ Task 8 (remove from EditorTopBar) + Task 9 (add 结构工具 row, fold `.layer-entry`, active-state styling via `:type="… ? 'primary' : 'default'"`).
- Snapshot extension with `deletedChapterIds`/`deletedStepIds`: ✅ Task 1.
- Store state addition + initializer: ✅ Task 1.
- `snapshot()` / `restore()` updates: ✅ Task 1.
- `resetEditState` clears deletion sets: ✅ Task 1 Step 8.
- `isDirty` extension: ✅ Task 2.
- `exportDraft` / `importDraft` round-trip: ✅ Task 3.
- `deleteNode` deferred-local + persisted descendants + temp-vs-real handling + undo restore: ✅ Task 4.
- `moveCrossParent` local with both groups resequenced + undo: ✅ Task 5.
- `buildPayload` emits deletion sets + sets clear after save: ✅ Task 6.
- Undo tooltip clarifies scope: ✅ Task 7.
- Non-goals (conversions, 标记应用, metadata, rich-text undo): respected — no tasks touch those paths.
