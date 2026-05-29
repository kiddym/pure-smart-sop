# E13 — PDF Preview Labeled Page Rail — Design

**Date:** 2026-05-29
**Track:** Post-migration editor track. Feature; the thumbnails/page-rail deferred from E12. Builds on E7 (page nav) + E12 (jump-to-page).
**Status:** Design approved; ready for implementation plan.

## Goal

Add a toggleable left **outline rail** to the PDF preview: one row per page = page № + the first heading on that page (封面 / 目录 / 修订记录 / chapter title), current page highlighted, click → jump. A navigable, glanceable minimap — more useful than E12's bare jump-to-page. Chosen over real scaled-clone thumbnails (the preview is in-browser HTML, so real thumbnails would double the document DOM for modest value).

## Background (E7/E12 machinery, present today)

`PdfPreviewDialog.vue` (fullscreen `el-dialog`): header `.pv-toolbar.no-print` (zoom + page-nav incl. the E12 editable page input); default slot is `<div ref="scrollEl" class="pv-scroll" @scroll="onScroll">` → `<div ref="docEl" class="pv-doc" :style="{ zoom }">` → a series of `<section class="page …">` (cover / TOC / revision / content pages / attachments). Available: `pageEls()` (`docEl.querySelectorAll('.page')`), `currentPage`/`pageCount` refs, `onScroll()` → `activePageIndex` keeps `currentPage` synced, `goPage(i)` (clamp + `scrollIntoView` + set `currentPage`). On model load (in the `watch(visible)` success branch, after `nextTick`): `zoom=1; currentPage=0; pageCount=pageEls().length`. Headings present per page: `.cover-title` (cover), `.sec-title` (`目录`/`修订记录`), `.chapter-title`/`.step-title` (content/attachments); `.ph-title` is the *running* header (repeated procedure name) — must be ignored.

## Components & changes

### 1. Pure `pageLabel` — `frontend/src/components/PdfPreview/pdfChrome.ts`

```ts
/** Outline label for a preview .page element: 封面 for the cover; else the first section
 *  heading (.sec-title / .chapter-title / .step-title) text; fallback `第 N 页`.
 *  Ignores the running page-header (.ph-title, the repeated procedure name). */
export function pageLabel(el: HTMLElement, index: number): string {
  if (el.classList.contains('cover')) return '封面'
  const h = el.querySelector('.sec-title, .chapter-title, .step-title')
  const text = h?.textContent?.trim() ?? ''
  return text || `第 ${index + 1} 页`
}
```

### 2. `PdfPreviewDialog.vue`

- **State:** `const railOpen = ref(true)` (default open, for discoverability); `const railEl = ref<HTMLElement | null>(null)`; `const railItems = ref<{ index: number; label: string }[]>([])`.
- **Build rail items** where `pageCount` is set (model-load `nextTick`): `railItems.value = pageEls().map((el, i) => ({ index: i, label: pageLabel(el, i) }))`.
- **Active follows scroll:** a row's `is-active` binds to `it.index === currentPage` (E7's `onScroll` keeps `currentPage` synced). Add `watch(currentPage, () => nextTick(() => railEl.value?.querySelector<HTMLElement>('.pv-rail-item.is-active')?.scrollIntoView({ block: 'nearest' })))` so the highlighted row stays visible in the rail.
- **Toolbar toggle:** a `☰ 目录` button in `.pv-actions` (before the zoom group) → `railOpen = !railOpen`.
- **Body restructure** — wrap the existing `.pv-scroll` in a flex `.pv-body` with the rail:
  ```html
  <div class="pv-body">
    <aside v-if="railOpen && model" ref="railEl" class="pv-rail no-print">
      <button
        v-for="it in railItems" :key="it.index"
        class="pv-rail-item" :class="{ 'is-active': it.index === currentPage }"
        @click="goPage(it.index)"
      >
        <span class="pv-rail-num">{{ it.index + 1 }}</span>
        <span class="pv-rail-label">{{ it.label }}</span>
      </button>
    </aside>
    <div ref="scrollEl" v-loading="loading" class="pv-scroll" @scroll="onScroll">
      <!-- unchanged .pv-doc … -->
    </div>
  </div>
  ```
- **CSS:** move `.pv-scroll { height: calc(100vh - 90px) }` to `.pv-body` (`display:flex; height:calc(100vh-90px)`); `.pv-scroll` → `flex:1; min-width:0` (keep `overflow:auto; background; padding`). `.pv-rail { width:200px; flex:none; overflow-y:auto; background:#3a3d42; padding:8px 0 }`; `.pv-rail-item { display:flex; gap:6px; width:100%; text-align:left; padding:4px 10px; background:none; border:none; color:#cfd3dc; cursor:pointer; font-size:12px }`; `.pv-rail-item:hover { background:rgba(255,255,255,0.08) }`; `.pv-rail-item.is-active { background:var(--el-color-primary,#d97757); color:#fff }`; `.pv-rail-num { flex:none; width:20px; text-align:right; opacity:.7 }`; `.pv-rail-label { flex:1; min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap }`. The rail is `.no-print`.

## Data flow

```
model load → nextTick → pageCount + railItems = pageEls().map(pageLabel)
scroll → onScroll → currentPage → rail row .is-active follows + scrolls into rail view
click rail row → goPage(index) → canvas scrolls + currentPage set → row highlights
☰ 目录 → railOpen toggles the aside
```

## Error handling / edge cases

- Rail renders only when `railOpen && model` (hidden during `v-loading` / before load).
- A page with no heading → `第 N 页` fallback. Cover → `封面`.
- `goPage` already clamps; clicking is always a valid index.
- Restructuring keeps `scrollEl` = `.pv-scroll`, so E7 zoom (on `.pv-doc`), scroll-sync, page-nav, and E12 jump-to-page are unaffected. The rail is `.no-print` so print/PDF download exclude it (the existing `@media print` already hides `.no-print`).
- Reopening the dialog rebuilds `railItems` (same model-load path).

## Testing

- **Unit `frontend/tests/unit/pdfChrome.spec.ts`**: `pageLabel` over constructed elements — `.page.cover` → `封面`; a page with `.sec-title` "目录" → "目录"; a page with `.chapter-title` "1.0 目的" → "1.0 目的"; a page with only `.ph-title` (running header) + no section heading → `第 N 页`; index used in the fallback.
- **Browser smoke**: open the preview → rail lists labeled pages (封面/目录/修订记录/章节…); click a row → canvas jumps + that row highlights; scrolling moves the highlight and scrolls the active row into the rail; `☰ 目录` hides/shows the rail; print preview shows no rail.
- vue-tsc clean; full suite green.

## Non-goals (YAGNI)

Scaled-clone / raster thumbnails (rejected — heavy), resizable rail, drag-to-reorder pages, a collapsible nested-outline tree, persisting the open/closed state.
