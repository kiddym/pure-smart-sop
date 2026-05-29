# Editor E3 — Tab/Shift+Tab Indent-Outdent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax. (Design approved in conversation; captured here — no separate spec doc.)

**Goal:** When a tree row has keyboard focus, `Tab` indents the node one level deeper and `Shift+Tab` one level shallower, walking 正文↔L1↔L2↔L3 (clamped). Frontend-only.

**Architecture (approved decisions):**
- **Tree-focused activation:** rows get `tabindex="-1"` (click-focusable, NOT in the page Tab order — Tab elsewhere keeps normal focus-nav; clicking a row focuses+selects it). On a focused row, `Tab`/`Shift+Tab` → emit `indent('in'|'out')` + `preventDefault`, but **only when the row div itself is the focus target** (`e.target === e.currentTarget`) so the inner checkbox/chip are unaffected.
- **Level scale** `[正文(null), L1, L2, L3]`: `in` = +1 step (clamp L3), `out` = −1 step (clamp 正文). 正文→L1 promotes a content node to a heading; L1→正文 demotes a heading to a content leaf (kind unchanged).
- **Step nodes:** the panel skips indent when `kind==='step'` (a step can't be a heading); also skips no-op clamps. Silent (no Tab-spam toast).
- Uses the existing `store.setLevel(id, newLevel)` (undoable via E1). `/view` (readonly) rows get no `tabindex` and don't indent.
- **Accepted limitation:** a focused row hijacks Tab to indent, so you can't Tab *out* of it via keyboard (click elsewhere to move focus). Arrow-key row nav is out of scope.

**Tech Stack:** Vue 3 `<script setup>`, Pinia, Element Plus, vitest + @vue/test-utils. From `frontend/`: `npx vitest run <path>`, `npx vue-tsc --noEmit`, `npm test`.

**Conventions:** commits end with the `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>` trailer (omitted below); `git add` explicit paths only.

---

## Task 1: `indentLevel` helper (`utils/nodeTree.ts`)

**Files:** Modify `frontend/src/utils/nodeTree.ts`; Test `frontend/tests/unit/utils/nodeTree.spec.ts`

- [ ] **Step 1: Write the failing test.** Append to `frontend/tests/unit/utils/nodeTree.spec.ts`:
```ts
import { indentLevel } from '@/utils/nodeTree'

describe('indentLevel', () => {
  it('in: 正文→L1→L2→L3, clamped at L3', () => {
    expect(indentLevel(null, 'in')).toBe(1)
    expect(indentLevel(1, 'in')).toBe(2)
    expect(indentLevel(2, 'in')).toBe(3)
    expect(indentLevel(3, 'in')).toBe(3)
  })
  it('out: L3→L2→L1→正文, clamped at 正文', () => {
    expect(indentLevel(3, 'out')).toBe(2)
    expect(indentLevel(2, 'out')).toBe(1)
    expect(indentLevel(1, 'out')).toBe(null)
    expect(indentLevel(null, 'out')).toBe(null)
  })
})
```
(If `indentLevel` is already in the file's existing `import { ... } from '@/utils/nodeTree'`, just add the name there instead of a new import line.)

- [ ] **Step 2: Run; verify fail.**
Run: `cd frontend && npx vitest run tests/unit/utils/nodeTree.spec.ts`
Expected: FAIL — `indentLevel` undefined.

- [ ] **Step 3: Implement.** Append to `frontend/src/utils/nodeTree.ts`:
```ts
const LEVEL_SCALE: (number | null)[] = [null, 1, 2, 3]

/** 缩进/反缩进一步：在 [正文, L1, L2, L3] 标尺上移动并夹紧。
 * 'in' = 更深（→L3），'out' = 更浅（→正文）。未知层级（如旧 L>3）按最深处理。 */
export function indentLevel(current: number | null, dir: 'in' | 'out'): number | null {
  let idx = LEVEL_SCALE.indexOf(current)
  if (idx < 0) idx = current === null ? 0 : LEVEL_SCALE.length - 1
  const next = dir === 'in' ? Math.min(idx + 1, LEVEL_SCALE.length - 1) : Math.max(idx - 1, 0)
  return LEVEL_SCALE[next]
}
```

- [ ] **Step 4: Run; verify pass.**
Run: `cd frontend && npx vitest run tests/unit/utils/nodeTree.spec.ts` → PASS.
Run: `cd frontend && npx vue-tsc --noEmit` → exit 0.

- [ ] **Step 5: Commit.**
```bash
git add frontend/src/utils/nodeTree.ts frontend/tests/unit/utils/nodeTree.spec.ts
git commit -m "feat(fe): indentLevel helper — walk 正文/L1/L2/L3 scale, clamped (E3)"
```

---

## Task 2: Row keydown + panel handler

**Files:** Modify `frontend/src/components/editor/NodeTreeRow.vue`, `frontend/src/components/editor/NodeTreePanel.vue`; Test `frontend/tests/unit/NodeTreeRow.spec.ts`, `frontend/tests/unit/NodeTreePanel.spec.ts`

- [ ] **Step 1: Write the failing tests.**

(a) Append to `frontend/tests/unit/NodeTreeRow.spec.ts`:
```ts
  it('Tab on the row emits indent "in"; Shift+Tab emits "out"', async () => {
    const w = mountRow(treeRow({ heading_level: 1 }))
    await w.find('.ntr').trigger('keydown', { key: 'Tab' })
    expect(w.emitted('indent')?.[0]).toEqual(['in'])
    await w.find('.ntr').trigger('keydown', { key: 'Tab', shiftKey: true })
    expect(w.emitted('indent')?.[1]).toEqual(['out'])
  })
  it('Tab from an inner control (checkbox) does not emit indent', async () => {
    const w = mountRow(treeRow({ heading_level: 1 }))
    await w.find('.ntr-check').trigger('keydown', { key: 'Tab' })
    expect(w.emitted('indent')).toBeFalsy()
  })
  it('readonly row: not focusable, no indent', async () => {
    const w = mountRow(treeRow({ heading_level: 1 }), { readonly: true })
    expect(w.find('.ntr').attributes('tabindex')).toBeUndefined()
    await w.find('.ntr').trigger('keydown', { key: 'Tab' })
    expect(w.emitted('indent')).toBeFalsy()
  })
  it('non-readonly row is click-focusable (tabindex -1)', () => {
    const w = mountRow(treeRow({ heading_level: 1 }))
    expect(w.find('.ntr').attributes('tabindex')).toBe('-1')
  })
```

(b) Append to `frontend/tests/unit/NodeTreePanel.spec.ts`:
```ts
  it('indent "in" on a content node promotes it to L1', () => {
    const { w, store } = setup([n({ id: 'a', heading_level: null, kind: 'node', body: '<p>A</p>' })])
    const setLevel = vi.spyOn(store, 'setLevel').mockResolvedValue()
    w.findComponent({ name: 'NodeTreeRow' }).vm.$emit('indent', 'in')
    expect(setLevel).toHaveBeenCalledWith('a', 1)
  })
  it('indent "in" on an L3 heading is a no-op (clamped)', () => {
    const { w, store } = setup([n({ id: 'a', heading_level: 3, kind: 'node', body: '<p>A</p>' })])
    const setLevel = vi.spyOn(store, 'setLevel').mockResolvedValue()
    w.findComponent({ name: 'NodeTreeRow' }).vm.$emit('indent', 'in')
    expect(setLevel).not.toHaveBeenCalled()
  })
  it('indent on a step node is skipped', () => {
    const { w, store } = setup([n({ id: 'a', heading_level: null, kind: 'step', body: '<p>S</p>' })])
    const setLevel = vi.spyOn(store, 'setLevel').mockResolvedValue()
    w.findComponent({ name: 'NodeTreeRow' }).vm.$emit('indent', 'in')
    expect(setLevel).not.toHaveBeenCalled()
  })
  it('indent "out" on an L1 heading demotes to 正文 (null)', () => {
    const { w, store } = setup([n({ id: 'a', heading_level: 1, kind: 'node', body: '<p>A</p>' })])
    const setLevel = vi.spyOn(store, 'setLevel').mockResolvedValue()
    w.findComponent({ name: 'NodeTreeRow' }).vm.$emit('indent', 'out')
    expect(setLevel).toHaveBeenCalledWith('a', null)
  })
```

- [ ] **Step 2: Run; verify fail.**
Run: `cd frontend && npx vitest run tests/unit/NodeTreeRow.spec.ts tests/unit/NodeTreePanel.spec.ts`
Expected: FAIL — no `indent` emit / `tabindex` / panel handler.

- [ ] **Step 3: Implement `NodeTreeRow.vue`.**
- Add to `defineEmits` (after the existing `(e: 'check', shift: boolean): void` line): `(e: 'indent', dir: 'in' | 'out'): void`.
- Add the handler in `<script setup>` (next to `onCheck`):
```ts
function onKeydown(ev: KeyboardEvent): void {
  if (props.readonly || ev.key !== 'Tab') return
  if (ev.target !== ev.currentTarget) return // 仅行本身聚焦（非内部 checkbox/chip）才缩进
  ev.preventDefault()
  emit('indent', ev.shiftKey ? 'out' : 'in')
}
```
- On the root `<div class="ntr" ...>`, add two bindings: `:tabindex="readonly ? undefined : -1"` and `@keydown="onKeydown"`.

- [ ] **Step 4: Implement `NodeTreePanel.vue`.**
- Add `indentLevel` to the value import from `@/utils/nodeTree` (the line that imports `subtreeIds, checkStates`): `import { subtreeIds, checkStates, indentLevel } from '@/utils/nodeTree'`.
- Add the handler (near `onCheck`):
```ts
function onIndent(id: string, dir: 'in' | 'out'): void {
  const node = store.nodeMap.get(id)
  if (!node || node.kind === 'step') return // 步骤不缩进（不能成章节）
  const next = indentLevel(node.heading_level, dir)
  if (next !== node.heading_level) void store.setLevel(id, next)
}
```
- On the `<NodeTreeRow ...>` in the template, add: `@indent="(dir: 'in' | 'out') => onIndent(row.node.id, dir)"`.

- [ ] **Step 5: Run; verify pass + type-check.**
Run: `cd frontend && npx vitest run tests/unit/NodeTreeRow.spec.ts tests/unit/NodeTreePanel.spec.ts` → PASS.
Run: `cd frontend && npx vue-tsc --noEmit` → exit 0.

- [ ] **Step 6: Commit.**
```bash
git add frontend/src/components/editor/NodeTreeRow.vue frontend/src/components/editor/NodeTreePanel.vue frontend/tests/unit/NodeTreeRow.spec.ts frontend/tests/unit/NodeTreePanel.spec.ts
git commit -m "feat(fe/editor): Tab/Shift+Tab indent-outdent on focused tree rows (E3)"
```

---

## Task 3: Verify + browser smoke + finish

- [ ] **Step 1: Full suite + type-check.**
Run: `cd frontend && npx vue-tsc --noEmit` → exit 0; `npm test` → all green (prior count + new tests, 0 failures).

- [ ] **Step 2: Browser smoke** (per `.claude/skills/running-smartsop-dev`). Launch backend + frontend, open a DRAFT procedure `/edit` (e.g. `356e353c-f3ea-49e1-8e97-674dbefb0e48`). With chrome-devtools MCP:
  - Click a **content** row (e.g. "为了凝聚…") to focus+select it, then dispatch a `Tab` keydown on that focused row → it becomes a heading (its level chip shows L1; confirm via `GET /nodes` the node's `heading_level` went `null → 1`). `Shift+Tab` → back to `null` (正文).
  - On an **L1 heading**, `Tab` → L2, `Tab` again → L3, `Tab` again → stays L3 (clamp). `Ctrl+Z` (E1) reverts one step.
  - Click a **step** node, `Tab` → no change (skipped), no error.
  - Confirm Tab pressed while focus is in the **body editor** does NOT indent (inserts in the editor) — focus-guard intact.
  - Zero console errors (the pre-existing asset 404 is unrelated).

- [ ] **Step 3: Finish the branch.** Use superpowers:finishing-a-development-branch (merge `--no-ff` to main).

---

## Self-Review Notes
- **`e.target === e.currentTarget`** restricts indent to the row div's own focus, so Tab on the inner checkbox/chip is left alone (tested).
- **`tabindex="-1"`** keeps rows out of the page Tab order (no traversal pollution); click focuses them; only the focused row's Tab is hijacked.
- **Step skip + no-op clamp** are both in `onIndent` (panel), so a step Tab and an L3 `Tab` issue no `setLevel` (tested).
- Promotion 正文→L1 on a **content** node (kind `node`) is invariant-safe (heading + kind node); the step case is excluded — so `setLevel` never produces a step+heading conflict.
- All level changes go through `store.setLevel` → recorded for **undo** (E1).
