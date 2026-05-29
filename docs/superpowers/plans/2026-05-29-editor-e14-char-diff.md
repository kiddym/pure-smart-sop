# E14 — Char-Level Text Highlighting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** In `VersionCompareDialog` modified rows, show a char-level diff (red-strike deletions / green insertions) of the plain text, toggleable against E10's rendered side-by-side.

**Architecture:** Pure `charDiff.ts` (prefix/suffix trim + char-LCS, size-guarded) + a `charMode` toggle in `VersionCompareDialog`. Spec: `docs/superpowers/specs/2026-05-29-editor-e14-char-diff-design.md`.

**Tech Stack:** Vue 3, vitest + jsdom, vue-tsc. No new dependency.

---

## File Structure

- **Create** `frontend/src/components/version/charDiff.ts` — `htmlToText`, `charDiff`.
- **Create** `frontend/tests/unit/charDiff.spec.ts` — pure tests.
- **Modify** `frontend/src/components/version/VersionCompareDialog.vue` — `charMode` toggle + char-diff render.
- **Modify** `frontend/tests/unit/VersionCompareDialog.spec.ts` — a char-diff render test.

No backend change.

---

## Task 1: Pure `charDiff.ts`

**Files:**
- Create: `frontend/src/components/version/charDiff.ts`
- Test: `frontend/tests/unit/charDiff.spec.ts`

- [ ] **Step 1: Write the failing tests — CREATE `frontend/tests/unit/charDiff.spec.ts`**

```ts
import { describe, it, expect } from 'vitest'
import { htmlToText, charDiff } from '@/components/version/charDiff'

describe('htmlToText', () => {
  it('strips tags + unescapes entities; empty → ""', () => {
    expect(htmlToText('<p>目的</p><p>其余</p>')).toBe('目的其余')
    expect(htmlToText('<p>A &amp; B</p>')).toBe('A & B')
    expect(htmlToText('')).toBe('')
  })
})

describe('charDiff', () => {
  it('identical → one equal seg; empty → []', () => {
    expect(charDiff('abc', 'abc')).toEqual([{ type: 'equal', text: 'abc' }])
    expect(charDiff('', '')).toEqual([])
  })
  it('pure insertion (prefix + ins + suffix)', () => {
    expect(charDiff('公司股东', '公司创始股东')).toEqual([
      { type: 'equal', text: '公司' },
      { type: 'ins', text: '创始' },
      { type: 'equal', text: '股东' },
    ])
  })
  it('pure deletion', () => {
    expect(charDiff('公司创始股东', '公司股东')).toEqual([
      { type: 'equal', text: '公司' },
      { type: 'del', text: '创始' },
      { type: 'equal', text: '股东' },
    ])
  })
  it('replacement (del + ins, runs merged)', () => {
    expect(charDiff('公司所有股东', '公司创始股东')).toEqual([
      { type: 'equal', text: '公司' },
      { type: 'del', text: '所有' },
      { type: 'ins', text: '创始' },
      { type: 'equal', text: '股东' },
    ])
  })
  it('empty a → all ins; empty b → all del', () => {
    expect(charDiff('', 'abc')).toEqual([{ type: 'ins', text: 'abc' }])
    expect(charDiff('abc', '')).toEqual([{ type: 'del', text: 'abc' }])
  })
  it('size guard: huge fully-different middles degrade to [del, ins]', () => {
    const a = 'a'.repeat(1001)
    const b = 'b'.repeat(1001)
    expect(charDiff(a, b)).toEqual([
      { type: 'del', text: a },
      { type: 'ins', text: b },
    ])
  })
})
```

- [ ] **Step 2: Run to verify FAIL**

Run: `cd frontend && npm test -- tests/unit/charDiff.spec.ts` → FAIL (module missing).

- [ ] **Step 3: Implement — CREATE `frontend/src/components/version/charDiff.ts`**

```ts
export interface DiffSeg {
  type: 'equal' | 'del' | 'ins'
  text: string
}

/** Visible text of a body HTML (for diffing). textContent concatenates — block breaks collapse. */
export function htmlToText(html: string): string {
  if (!html) return ''
  return new DOMParser().parseFromString(html, 'text/html').body.textContent ?? ''
}

const GUARD = 1_000_000

/** Char-level diff: common prefix/suffix trim, then char-LCS on the differing middle.
 *  Size guard: a huge fully-different middle degrades to one del + one ins (no O(n·m) blowup). */
export function charDiff(a: string, b: string): DiffSeg[] {
  if (a === b) return a ? [{ type: 'equal', text: a }] : []
  const minLen = Math.min(a.length, b.length)
  let p = 0
  while (p < minLen && a[p] === b[p]) p++
  let s = 0
  while (s < a.length - p && s < b.length - p && a[a.length - 1 - s] === b[b.length - 1 - s]) s++
  const aMid = a.slice(p, a.length - s)
  const bMid = b.slice(p, b.length - s)
  const segs: DiffSeg[] = []
  if (p > 0) segs.push({ type: 'equal', text: a.slice(0, p) })
  if (aMid && bMid && aMid.length * bMid.length > GUARD) {
    segs.push({ type: 'del', text: aMid })
    segs.push({ type: 'ins', text: bMid })
  } else {
    segs.push(...lcsMiddle(aMid, bMid))
  }
  if (s > 0) segs.push({ type: 'equal', text: a.slice(a.length - s) })
  return merge(segs)
}

function lcsMiddle(a: string, b: string): DiffSeg[] {
  if (!a) return b ? [{ type: 'ins', text: b }] : []
  if (!b) return [{ type: 'del', text: a }]
  const n = a.length
  const m = b.length
  const dp: number[][] = Array.from({ length: n + 1 }, () => new Array<number>(m + 1).fill(0))
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      dp[i][j] = a[i] === b[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1])
    }
  }
  const out: DiffSeg[] = []
  let i = 0
  let j = 0
  while (i < n && j < m) {
    if (a[i] === b[j]) {
      out.push({ type: 'equal', text: a[i] })
      i++
      j++
    } else if (dp[i + 1][j] >= dp[i][j + 1]) {
      out.push({ type: 'del', text: a[i] })
      i++
    } else {
      out.push({ type: 'ins', text: b[j] })
      j++
    }
  }
  while (i < n) {
    out.push({ type: 'del', text: a[i] })
    i++
  }
  while (j < m) {
    out.push({ type: 'ins', text: b[j] })
    j++
  }
  return out
}

/** Coalesce adjacent same-type segments; drop empties. */
function merge(segs: DiffSeg[]): DiffSeg[] {
  const out: DiffSeg[] = []
  for (const seg of segs) {
    if (!seg.text) continue
    const last = out[out.length - 1]
    if (last && last.type === seg.type) last.text += seg.text
    else out.push({ ...seg })
  }
  return out
}
```

- [ ] **Step 4: Run to verify PASS**

Run: `cd frontend && npm test -- tests/unit/charDiff.spec.ts` → expect all pass. If a case fails, fix the function (NOT the test) — the expected outputs are authoritative.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/version/charDiff.ts frontend/tests/unit/charDiff.spec.ts
git commit -m "feat(version): pure char-level diff (htmlToText + charDiff, LCS + prefix/suffix trim) (E14 Task 1)"
```

---

## Task 2: char-diff toggle + render in `VersionCompareDialog`

**Files:**
- Modify: `frontend/src/components/version/VersionCompareDialog.vue`
- Test: `frontend/tests/unit/VersionCompareDialog.spec.ts`

- [ ] **Step 1: Write the failing test — append to `frontend/tests/unit/VersionCompareDialog.spec.ts`**

Add inside the `describe('VersionCompareDialog', …)` block (reuses `n`, `mountDialog`):
```ts
  it('modified row shows a char-level diff (charMode default on)', async () => {
    await mountDialog(
      [n({ id: 'o1', code: '1', body: '<p>本程序适用于公司所有股东</p>' })],
      [n({ id: 'n1', code: '1', body: '<p>本程序适用于公司创始股东</p>' })],
    )
    // expand the single (modified) row — the dialog teleports to document.body
    const line = document.body.querySelector('.vc-line') as HTMLElement
    line.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    await flushPromises()
    expect(document.body.querySelector('.vc-del')?.textContent).toContain('所有')
    expect(document.body.querySelector('.vc-ins')?.textContent).toContain('创始')
    expect(document.body.querySelector('.vc-html')).toBeNull() // rendered side-by-side hidden in charMode
  })
```

- [ ] **Step 2: Run to verify FAIL**

Run: `cd frontend && npm test -- tests/unit/VersionCompareDialog.spec.ts` → the new test FAILS (no `.vc-del`/`.vc-ins`; `.vc-html` still present). Existing 3 tests still pass.

- [ ] **Step 3: Script — import + charMode + charSegs**

In `VersionCompareDialog.vue` `<script setup>`:
- Change the `./versionDiff` import to also bring in nothing new; add a new import line:
  ```ts
  import { charDiff, htmlToText } from './charDiff'
  ```
- After `const onlyChanges = ref(true)` (line ~19-20), add:
  ```ts
  const charMode = ref(true)
  ```
- Add a method (near `toggle`):
  ```ts
  function charSegs(r: DiffRow) {
    return charDiff(htmlToText(r.old?.body ?? ''), htmlToText(r.new?.body ?? ''))
  }
  ```

- [ ] **Step 4: Template — toolbar toggle + modified-row branch**

(a) Add the toggle right after the `只看变更` switch (line 76):
```html
        <el-switch v-model="onlyChanges" active-text="只看变更" />
        <el-switch v-model="charMode" active-text="字符差异" />
```
(b) Replace the modified-row `<template v-if="r.status === 'modified'"> … </template>` (lines 90-101) with:
```html
          <template v-if="r.status === 'modified'">
            <div v-if="charMode" class="vc-chardiff">
              <span
                v-for="(seg, k) in charSegs(r)"
                :key="k"
                :class="seg.type === 'del' ? 'vc-del' : seg.type === 'ins' ? 'vc-ins' : ''"
              >{{ seg.text }}</span>
            </div>
            <template v-else>
              <div class="vc-col">
                <div class="vc-coltag">旧 v{{ oldVersion }}</div>
                <!-- eslint-disable-next-line vue/no-v-html -->
                <div class="vc-html" v-html="r.old?.body"></div>
              </div>
              <div class="vc-col">
                <div class="vc-coltag">新 v{{ newVersion }}</div>
                <!-- eslint-disable-next-line vue/no-v-html -->
                <div class="vc-html" v-html="r.new?.body"></div>
              </div>
            </template>
          </template>
```
(`added`/`removed` branches below are unchanged.)

- [ ] **Step 5: CSS** (in `<style scoped>`, near `.vc-html`)

```css
.vc-chardiff {
  flex: 1;
  min-width: 0;
  padding: 8px;
  background: #fff;
  border: 1px solid var(--el-border-color-lighter, #ebeef5);
  border-radius: 4px;
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.6;
}
.vc-del {
  background: #fde2e2;
  color: #c0392b;
  text-decoration: line-through;
}
.vc-ins {
  background: #e3f9e5;
  color: #2e7d32;
}
```

- [ ] **Step 6: Run the dialog suite — green**

Run: `cd frontend && npm test -- tests/unit/VersionCompareDialog.spec.ts` → expect all pass (3 existing + the new char-diff test).

- [ ] **Step 7: Type check + full suite**

Run: `cd frontend && npm run typecheck` → vue-tsc no errors.
Run: `cd frontend && npm test` → 0 failures.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/version/VersionCompareDialog.vue frontend/tests/unit/VersionCompareDialog.spec.ts
git commit -m "feat(version): char-diff toggle + render in VersionCompareDialog (E14 Task 2)"
```

---

## Orchestrator browser smoke (NOT a subagent task — after Task 2, before merge)

Reuse the E10-style staging: a group with ≥2 versions where a node body differs between v1 and the current (the dev DB has the `a5b865ed` 2-version group; edit a node's body in the v2 draft via the API so a `modified` row appears with a real text change). Open the v2 detail page → 「对比当前」 on the v1 row → the modified row (expanded) shows char-level red-strike/green highlights; the 「字符差异」 toggle switches to E10's rendered 旧 | 新. If staging is impractical, note it — `charDiff` is unit-tested and the dialog render is unit-tested.

---

## Self-Review

**Spec coverage:**
- Pure `htmlToText` + `charDiff` (prefix/suffix trim, char-LCS, merge, size guard) → Task 1. ✓
- `charMode` toggle (default on) + `charSegs` + modified-row branch (char-diff vs E10 side-by-side) + CSS → Task 2. ✓
- `added`/`removed` rows unchanged; toggle switches all modified rows → Task 2 Step 4. ✓
- Accepted caveat (block breaks collapse) is inherent to `htmlToText`; no task fights it. ✓
- Non-goals (word/token diff, HTML-aware, added/removed char-diff, dep, persist) → untouched. ✓

**Placeholder scan:** none — full code for the module, the script, the template, the CSS, and both test files.

**Type consistency:** `DiffSeg`/`charDiff`/`htmlToText` defined Task 1, imported Task 2. `charSegs(r: DiffRow)` returns `DiffSeg[]`; the template's `seg.type`/`seg.text` match. `charMode` is a `ref<boolean>`. `DiffRow`/`r.old`/`r.new` already exist (E10).
