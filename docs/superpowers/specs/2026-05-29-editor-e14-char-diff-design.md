# E14 — Char-Level Text Highlighting in the Version Diff Viewer — Design

**Date:** 2026-05-29
**Track:** Post-migration editor track. Follow-up to E10 (version diff/compare viewer).
**Status:** Design approved; ready for implementation plan.

## Goal

In `VersionCompareDialog`'s `modified` rows, highlight exactly which characters changed between the old and new node body — deletions (red strikethrough) + insertions (green). A toolbar toggle 「字符差异」 (default on) switches all modified rows between this char-diff and E10's rendered old | new side-by-side.

## Background (E10, present today)

`VersionCompareDialog.vue`: a `modified` row, when expanded, renders `<template v-if="r.status === 'modified'">` → two `.vc-col` columns with `旧 v{n}` / `新 v{n}` showing `r.old.body` / `r.new.body` via `v-html` (lines 90-101). Toolbar (`#header`) has a `<el-switch v-model="onlyChanges" active-text="只看变更">` (line 76). `added`/`removed` rows show the new/old body (no counterpart to diff). Node bodies are HTML; content is mostly Chinese (no word boundaries). No diff library installed; `nodeTitle` already uses `DOMParser` for html→text.

## Components & changes

### 1. Pure `charDiff.ts` — `frontend/src/components/version/charDiff.ts`

```ts
export interface DiffSeg { type: 'equal' | 'del' | 'ins'; text: string }

/** Visible text of a body HTML (for diffing). textContent concatenates — block breaks collapse. */
export function htmlToText(html: string): string {
  if (!html) return ''
  return new DOMParser().parseFromString(html, 'text/html').body.textContent ?? ''
}

/** Char-level diff: common prefix/suffix trim, then char-LCS on the differing middle.
 *  Size guard: if the middle is huge, degrade to "whole middle replaced" (no O(n·m) blowup). */
export function charDiff(a: string, b: string): DiffSeg[]
```
- `charDiff`: equal-prefix + equal-suffix as `equal` segs; the middle via a char-LCS DP (`del` for unmatched `a` chars, `ins` for unmatched `b`, `equal` for matched — same del-first tiebreak as E10's `diffVersions`); merge adjacent same-type segs. **Guard:** if `aMid.length * bMid.length > 1_000_000`, emit one `del`(aMid) + one `ins`(bMid) instead of the LCS. Identical inputs → a single `equal` (or `[]` when empty). Empty `a` → all `ins`; empty `b` → all `del`.
- Dependency-free; consistent with E10's LCS.

### 2. `VersionCompareDialog.vue`

- `const charMode = ref(true)`. Toolbar: add `<el-switch v-model="charMode" active-text="字符差异" />` right after the `只看变更` switch (line 76).
- Import `charDiff`, `htmlToText` (and the `DiffSeg` type). Add a method:
  ```ts
  function charSegs(r: DiffRow) {
    return charDiff(htmlToText(r.old?.body ?? ''), htmlToText(r.new?.body ?? ''))
  }
  ```
- Replace the modified-row body (lines 90-101) so it branches on `charMode`:
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
      <div class="vc-col"><div class="vc-coltag">旧 v{{ oldVersion }}</div><!-- eslint-disable-next-line vue/no-v-html --><div class="vc-html" v-html="r.old?.body"></div></div>
      <div class="vc-col"><div class="vc-coltag">新 v{{ newVersion }}</div><!-- eslint-disable-next-line vue/no-v-html --><div class="vc-html" v-html="r.new?.body"></div></div>
    </template>
  </template>
  ```
  (`added`/`removed` branches unchanged — char-diff needs both sides.)
- CSS: `.vc-chardiff { flex:1; min-width:0; padding:8px; background:#fff; border:1px solid var(--el-border-color-lighter,#ebeef5); border-radius:4px; white-space:pre-wrap; word-break:break-word; line-height:1.6 }`; `.vc-del { background:#fde2e2; color:#c0392b; text-decoration:line-through }`; `.vc-ins { background:#e3f9e5; color:#2e7d32 }`.

## Data flow

```
modified row expanded + charMode → charSegs(r) = charDiff(htmlToText(old.body), htmlToText(new.body))
  → render <span> per seg (equal plain / del red-strike / ins green)
charMode off → E10's 旧 v{n} | 新 v{n} rendered v-html side-by-side
```

## Error handling / edge cases

- Empty body on one side → all `ins` / all `del`. Identical text (body changed only in tags/whitespace stripped away) → a single `equal` (no highlights — acceptable).
- Very long, fully-different bodies → the size guard degrades to one `del` + one `ins` (whole middle replaced) — no O(n·m) blowup.
- `charSegs` is computed in the template only for expanded modified rows (small N) — recompute-on-render is fine.
- **Accepted caveat:** `htmlToText` collapses block/paragraph breaks (multi-paragraph bodies show as continuous text in the char-diff); the 「字符差异」 toggle → rendered side-by-side is the fallback when structure matters. HTML-aware structural diff is a non-goal.

## Testing

- **Unit `frontend/tests/unit/charDiff.spec.ts`** (flat under `tests/unit/`, matching `versionDiff.spec.ts`/`pdfChrome.spec.ts`): `htmlToText` (strips tags, entities, empty); `charDiff` — identical → one `equal`; insertion (`公司[]股东`→`公司{创始}股东`); deletion; replacement (prefix+suffix trim, `所有`→`创始`); empty `a` → all `ins`; empty `b` → all `del`; adjacent same-type merged into a run; the size-guard degrade (two ~1001-char all-different middles → `[del, ins]`).
- **`frontend/tests/unit/VersionCompareDialog.spec.ts`** (extend E10's): a modified row (old `本程序适用于公司所有股东`, new `…创始股东`), expanded, with `charMode` default on → `.vc-del` contains `所有`, `.vc-ins` contains `创始`, and no `.vc-html` (rendered side-by-side hidden in charMode). (Expand by dispatching a `click` on the row's `.vc-line` — the dialog teleports to `document.body`, as E10's tests already query.)
- **Browser smoke**: compare a version whose node body was edited → the modified row shows char-level red/green; the 「字符差异」 toggle switches to E10's rendered 旧 | 新.
- vue-tsc clean; full suite green.

## Non-goals (YAGNI)

Word-level/token diff (char-level fits CJK), HTML-aware structural diff (tags preserved across the change), char-diff for `added`/`removed` rows, a Myers / diff-match-patch dependency, persisting the toggle state.
