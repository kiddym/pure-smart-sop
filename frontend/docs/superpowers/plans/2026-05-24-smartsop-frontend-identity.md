# SmartSOP 前端「身份整合」实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把已有的暖色身份（赤陶 + 鼠尾草绿 + 米色）打通到全应用，消除与 Element Plus 蓝灰默认的双轨冲突，并补上字体性格与轻量动效。

**Architecture:** 以 `tokens.css` 为权威单一来源覆盖 Element 的 `--el-color-primary*` 变量（tokens.css 在 Element CSS 之后加载，覆盖自动级联到所有引用这些变量的组件）；`main.css` 负责 body 暖化、全局标题字与动效工具类；自托管 Fraunces 西文显示字（带系统衬线降级）；逐文件清除硬编码蓝。

**Tech Stack:** Vue 3 + Element Plus 2.7 + Tailwind 3 + Vite 5 + TypeScript（vue-tsc）

---

## 执行须知（重要）

- **当前目录不是 git 仓库**，因此本计划用 **Checkpoint（验证关卡）** 代替 `git commit`。若执行期间已 `git init`，可在每个 Checkpoint 处提交。
- **这是纯样式/设计改动**，没有自然的单元测试。每个 Task 的验证关卡用 **`npm run build`（vue-tsc + vite）+ `grep` 收口 + 目视走查** 作为回归门，这就是本类改动的正确验证方式，不强行编造单测。
- 工作目录均相对 `SmartSOP/frontend/`。
- 赤陶梯度（全计划统一使用，勿改）：

  | 变量 | 值 |
  |---|---|
  | `--el-color-primary` | `#d97757` |
  | `--el-color-primary-light-3` | `#e4a089` |
  | `--el-color-primary-light-5` | `#ecbbab` |
  | `--el-color-primary-light-7` | `#f4d6cd` |
  | `--el-color-primary-light-8` | `#f7e4dd` |
  | `--el-color-primary-light-9` | `#fbf1ee` |
  | `--el-color-primary-dark-2` | `#ae5f46` |

---

## Task 1: tokens.css 升格为权威单一来源（Element 梯度 + 字体变量）

**Files:**
- Modify: `src/assets/styles/tokens.css`

- [ ] **Step 1: 用以下完整内容替换 `src/assets/styles/tokens.css`**

```css
/* 设计令牌单一来源（权威见 docs/design-system.md）。
   新增配色请先回填 design-system.md，禁止散落 hex。 */
:root {
  /* 状态色（暖盘） */
  --st-draft: #a89a86;
  --st-published: #88b07a;
  --st-archived: #6b635a;
  --st-deprecated: #d9685e;

  /* 壳色 / 强调 */
  --accent: #d97757;
  --bg-surface: #f5f3ef;
  --bg-elevated: #eceae5;
  --text-primary: #1a1714;

  /* 字体 */
  --font-display: 'Fraunces', Georgia, 'Times New Roman', serif;

  /* Element Plus 主题色覆盖（赤陶梯度，单一来源）
     tokens.css 在 element-plus/dist/index.css 之后加载，故此覆盖生效，
     并级联到所有引用 var(--el-color-primary*) 的组件。 */
  --el-color-primary: #d97757;
  --el-color-primary-light-3: #e4a089;
  --el-color-primary-light-5: #ecbbab;
  --el-color-primary-light-7: #f4d6cd;
  --el-color-primary-light-8: #f7e4dd;
  --el-color-primary-light-9: #fbf1ee;
  --el-color-primary-dark-2: #ae5f46;
}
```

- [ ] **Step 2: 验证构建通过**

Run: `npm run build`
Expected: 成功（无 vue-tsc / vite 报错）。

- [ ] **Step 3: Checkpoint**

确认 tokens.css 含 7 个 `--el-color-primary*` 行与 `--font-display`。

---

## Task 2: tailwind.config.js — primary 暖化 + 显示字体族

**Files:**
- Modify: `tailwind.config.js`

- [ ] **Step 1: 修改 `colors.primary`（第 9–14 行附近）**

将：
```js
        primary: {
          DEFAULT: '#409eff',
          dark: '#337ecc',
        },
```
改为：
```js
        primary: {
          DEFAULT: '#d97757',
          dark: '#ae5f46',
        },
```

- [ ] **Step 2: 在 `fontFamily` 中新增 `display` 族**

将：
```js
      fontFamily: {
        sans: [
          'PingFang SC',
          'Microsoft YaHei',
          'Helvetica Neue',
          'Arial',
          'sans-serif',
        ],
      },
```
改为：
```js
      fontFamily: {
        sans: [
          'PingFang SC',
          'Microsoft YaHei',
          'Helvetica Neue',
          'Arial',
          'sans-serif',
        ],
        display: ['Fraunces', 'Georgia', 'Times New Roman', 'serif'],
      },
```

- [ ] **Step 3: 验证构建通过**

Run: `npm run build`
Expected: 成功。

- [ ] **Step 4: Checkpoint**

确认 `grep -n "409eff\|337ecc" tailwind.config.js` 无输出。

---

## Task 3: main.css — body 暖化 + 全局标题字 + 动效工具类

**Files:**
- Modify: `src/assets/styles/main.css`

- [ ] **Step 1: 用以下完整内容替换 `src/assets/styles/main.css`**

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

html,
body,
#app {
  height: 100%;
  margin: 0;
  font-family: 'PingFang SC', 'Microsoft YaHei', 'Helvetica Neue', Arial, sans-serif;
  color: var(--text-primary);
  background: var(--bg-surface);
}

/* 标题/品牌使用显示字（西文有性格，中文回退系统字） */
h1,
h2,
h3,
.app-brand {
  font-family: var(--font-display);
}

/* ---- 动效（克制，可访问） ---- */
/* 路由切换淡入淡出，配合 <Transition name="fade"> */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.16s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* 一次性入场（用于首屏 stagger） */
@keyframes u-fade-in {
  from {
    opacity: 0;
    transform: translateY(6px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
.u-fade-in {
  animation: u-fade-in 0.28s ease both;
}

@media (prefers-reduced-motion: reduce) {
  .fade-enter-active,
  .fade-leave-active,
  .u-fade-in {
    transition: none !important;
    animation: none !important;
  }
}
```

- [ ] **Step 2: 验证构建通过**

Run: `npm run build`
Expected: 成功。

- [ ] **Step 3: Checkpoint**

确认 main.css 含 `--text-primary`、`--bg-surface`、`--font-display`、`.fade-enter-active`、`.u-fade-in`、`prefers-reduced-motion`。

---

## Task 4: 自托管 Fraunces 显示字（带降级）

**Files:**
- Create: `src/assets/fonts/` 目录
- Create: `src/assets/fonts/fraunces.css`
- Create: `src/assets/fonts/Fraunces-SemiBold.woff2`（下载；失败则降级）
- Modify: `src/main.ts`

- [ ] **Step 1: 建目录并尝试下载 Fraunces（拉丁子集，SemiBold/600）**

Run:
```bash
mkdir -p src/assets/fonts
curl -fsSL "https://fonts.gstatic.com/s/fraunces/v31/6NUh8FyLNQOQZAnv9bYEvDiIdE9Ea92uemAk_WBq8U.woff2" -o src/assets/fonts/Fraunces-SemiBold.woff2 && echo DOWNLOAD_OK || echo DOWNLOAD_FAILED
```
Expected: 打印 `DOWNLOAD_OK` 且文件大小 > 5KB（`ls -l src/assets/fonts/Fraunces-SemiBold.woff2`）。

> **降级分支：** 若打印 `DOWNLOAD_FAILED` 或文件 < 5KB（网络/代理受限）：删除该 woff2 文件，**跳过 Step 2 与 Step 3 的 main.ts 导入**，直接到 Step 4。此时 `--font-display` 中的 `Georgia, 'Times New Roman', serif` 系统衬线栈生效，标题仍获得「衬线 vs 无衬线正文」的层级区分——改动不阻塞。在 Checkpoint 中记录"字体降级到系统衬线"。

- [ ] **Step 2: 创建 `src/assets/fonts/fraunces.css`（仅下载成功时）**

```css
@font-face {
  font-family: 'Fraunces';
  font-style: normal;
  font-weight: 600;
  font-display: swap;
  src: url('./Fraunces-SemiBold.woff2') format('woff2');
}
```

- [ ] **Step 3: 在 `src/main.ts` 引入字体（仅下载成功时）**

在 `import './assets/styles/tokens.css'` 之前一行插入：
```ts
import './assets/fonts/fraunces.css'
```
使 `src/main.ts` 顶部 import 段为：
```ts
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import './assets/fonts/fraunces.css'
import './assets/styles/tokens.css'
import './assets/styles/main.css'
```

- [ ] **Step 4: 验证构建通过**

Run: `npm run build`
Expected: 成功（若走降级分支，未引入 fraunces.css 也应成功）。

- [ ] **Step 5: Checkpoint**

记录：字体是「自托管成功」还是「降级到系统衬线」。

---

## Task 5: AppLayout.vue — 品牌字 + 路由切换淡入

**Files:**
- Modify: `src/layouts/AppLayout.vue`

> 品牌字已由 Task 3 的全局 `.app-brand` 规则覆盖，本任务只加路由过渡。

- [ ] **Step 1: 给 `<RouterView>` 包裹淡入过渡**

将 `<template>` 中的：
```html
    <el-main class="app-main">
      <RouterView />
    </el-main>
```
改为：
```html
    <el-main class="app-main">
      <RouterView v-slot="{ Component }">
        <Transition name="fade" mode="out-in">
          <component :is="Component" />
        </Transition>
      </RouterView>
    </el-main>
```

- [ ] **Step 2: 验证构建通过**

Run: `npm run build`
Expected: 成功。

- [ ] **Step 3: Checkpoint**

确认 AppLayout.vue 含 `<Transition name="fade" mode="out-in">`。

---

## Task 6: 清除硬编码蓝（12 文件，grep 收口为 0）

**Files（全部 Modify）:**
- `src/components/import-v2/ContentDetailCard.vue`
- `src/components/import-v2/ChapterDetailCard.vue`
- `src/components/import-v2/WordPreviewPanel.vue`
- `src/components/import-v2/ImportTreeRow.vue`
- `src/components/import/ImportFormStep.vue`
- `src/components/import/ImportTreeNode.vue`
- `src/components/import/ModeStep.vue`
- `src/components/import/UploadStep.vue`
- `src/components/import/BlockMarkingStep.vue`
- `src/components/editor/TreeRow.vue`
- `src/components/editor/StepDetailPanel.vue`
- `src/components/version/VersionListPanel.vue`

**替换规则（两遍 sed，顺序不可颠倒）：**
- 第一遍把已有 `var(X, #蓝)` 的 fallback 暖化（匹配 `, #hex)` 形式）。
- 第二遍把剩余裸蓝包进 Element 变量。
- 颠倒顺序会产生 `var(--el-color-primary, var(--el-color-primary, ...))` 嵌套错误。

- [ ] **Step 1: 第一遍 —— 暖化 var() fallback**

Run:
```bash
LC_ALL=C find src -name '*.vue' -exec sed -i '' \
  -e 's/, #409eff)/, #d97757)/g' \
  -e 's/, #ecf5ff)/, #fbf1ee)/g' \
  -e 's/, #d9ecff)/, #f7e4dd)/g' {} +
```

- [ ] **Step 2: 第二遍 —— 裸蓝包进 Element 变量**

Run:
```bash
LC_ALL=C find src -name '*.vue' -exec sed -i '' \
  -e 's/#409eff/var(--el-color-primary, #d97757)/g' \
  -e 's/#ecf5ff/var(--el-color-primary-light-9, #fbf1ee)/g' \
  -e 's/#d9ecff/var(--el-color-primary-light-8, #f7e4dd)/g' {} +
```

- [ ] **Step 3: grep 收口（必须为 0）**

Run:
```bash
grep -rn "#409eff\|#337ecc\|#ecf5ff\|#d9ecff" src --include="*.vue" --include="*.css" | wc -l
```
Expected: `0`

- [ ] **Step 4: 验证构建通过**

Run: `npm run build`
Expected: 成功。

- [ ] **Step 5: Checkpoint**

抽查 `src/components/import/BlockMarkingStep.vue` 与 `src/components/editor/TreeRow.vue`，确认蓝已全部变成 `var(--el-color-primary*, #暖hex)`。

---

## Task 7: 主列表首屏 stagger 入场

**Files:**
- Modify: `src/views/procedures/ProcedureLibraryView.vue`

- [ ] **Step 1: 在 `<style scoped>` 末尾追加 stagger 规则**

在 `.pager { ... }` 之后追加：
```css
.library > * {
  animation: u-fade-in 0.28s ease both;
}
.library > *:nth-child(1) {
  animation-delay: 0.02s;
}
.library > *:nth-child(2) {
  animation-delay: 0.06s;
}
.library > *:nth-child(3) {
  animation-delay: 0.1s;
}
.library > *:nth-child(4) {
  animation-delay: 0.14s;
}
@media (prefers-reduced-motion: reduce) {
  .library > * {
    animation: none;
  }
}
```

> `@keyframes u-fade-in` 由 Task 3 的全局 main.css 定义，scoped 样式可引用全局 keyframes。

- [ ] **Step 2: 验证构建通过**

Run: `npm run build`
Expected: 成功。

- [ ] **Step 3: Checkpoint**

确认 ProcedureLibraryView.vue 含 `.library > *` 与 `nth-child` 延迟。

---

## Task 8: 创建 docs/design-system.md（修复治理悬空引用）

**Files:**
- Create: `docs/design-system.md`

- [ ] **Step 1: 写入以下内容到 `docs/design-system.md`**

```markdown
# SmartSOP 前端设计系统（单一来源）

> 权威配色/字体/动效以本文档为准。新增配色必须先回填本文档，禁止在组件里散落 hex。
> 令牌实现见 `src/assets/styles/tokens.css`。

## §1 身份概述

暖色身份：以赤陶（terracotta）为强调、鼠尾草绿表"已发布"、米色为壳层背景，
传达"文档/程序/合规"的克制、可信气质。刻意避开默认后台模板的蓝灰。

## §2 色彩

### 2.1 壳色与强调
| Token | 值 | 用途 |
|---|---|---|
| `--accent` | `#d97757` | 强调（赤陶） |
| `--bg-surface` | `#f5f3ef` | 壳层背景（米） |
| `--bg-elevated` | `#eceae5` | 抬升面 |
| `--text-primary` | `#1a1714` | 主文字（暖近黑） |

### 2.2 Element Plus 主题色映射（赤陶梯度）
在 tokens.css 的 `:root` 覆盖，自动级联全组件：

| 变量 | 值 |
|---|---|
| `--el-color-primary` | `#d97757` |
| `--el-color-primary-light-3` | `#e4a089` |
| `--el-color-primary-light-5` | `#ecbbab` |
| `--el-color-primary-light-7` | `#f4d6cd` |
| `--el-color-primary-light-8` | `#f7e4dd` |
| `--el-color-primary-light-9` | `#fbf1ee` |
| `--el-color-primary-dark-2` | `#ae5f46` |

> success / warning / danger 暂保留 Element 默认（已被 PublishChecklistDialog
> 等使用），如需暖化后续单列。

### 2.3 状态色语义
| Token | 值 | 语义 | 视觉 |
|---|---|---|---|
| `--st-draft` | `#a89a86` | 草稿 | 空心暖灰点 |
| `--st-published` | `#88b07a` | 已发布 | 实心鼠尾草绿 |
| `--st-archived` | `#6b635a` | 已归档 | 暗实心 |
| `--st-deprecated` | `#d9685e` | 废弃 | 警示红 |

## §3 字体

- 标题/品牌：`--font-display` = `'Fraunces', Georgia, 'Times New Roman', serif`
  （西文显示衬线；自托管 woff2，拉丁子集；拉取失败降级系统衬线）。
- 正文：系统字栈 `PingFang SC, Microsoft YaHei, Helvetica Neue, Arial, sans-serif`。
- 应用：全局 `h1/h2/h3/.app-brand` 用显示字；正文中文保持系统字。

## §4 动效

- 原则：克制、一次性入场、尊重 `prefers-reduced-motion`。
- 路由切换：`<Transition name="fade">`，160ms 淡入淡出。
- 首屏：`.u-fade-in` keyframe，280ms，仅入场一次。
- 对话框：沿用 Element 自带 fade+zoom。

## §5 治理

- 禁止在 `.vue`/`.css` 中写裸 hex 配色；一律走 `var(--*)`。
- 新增配色 → 先回填本文档 §2 → 再在 tokens.css 落地。
- CI/复查：`grep -rn "#409eff\|#337ecc\|#ecf5ff\|#d9ecff" src` 应为 0。
```

- [ ] **Step 2: 确认 tokens.css 的"权威见 docs/design-system.md"引用现已有效**

Run: `ls -l docs/design-system.md`
Expected: 文件存在。

- [ ] **Step 3: Checkpoint**

确认 design-system.md 含 §1–§5。

---

## Task 9: 最终验证（构建 + lint + grep + 目视走查）

**Files:** 无（仅验证）

- [ ] **Step 1: 构建**

Run: `npm run build`
Expected: 成功。

- [ ] **Step 2: Lint 0 警告**

Run: `npm run lint`
Expected: 通过，0 警告。

- [ ] **Step 3: 蓝色收口为 0**

Run: `grep -rn "#409eff\|#337ecc\|#ecf5ff\|#d9ecff" src --include="*.vue" --include="*.css" | wc -l`
Expected: `0`

- [ ] **Step 4: 启动并目视走查**

Run: `npm run dev`（前端 5173），逐页确认：
- 主列表：按钮/链接为赤陶、无残留蓝、首屏有轻入场。
- 编辑器（TreeRow 拖拽高亮）：高亮为暖色。
- 导入向导（ModeStep/UploadStep/BlockMarkingStep）：选中态、链接为暖色。
- 品牌字「Smart SOP」与页面标题为显示字（或系统衬线降级）。
- 系统设置开启"减少动态效果"后，入场/过渡关闭。
- 截图留档。

- [ ] **Step 5: 完成**

用 superpowers:verification-before-completion 核对：build 通过、lint 0、grep=0、目视无残留蓝——证据齐全方可宣称完成。

---

## Self-Review

- **Spec 覆盖：** §3.1 Element 覆盖→T1；§3.2 双轨收敛（tailwind/body/清蓝/tokens 权威）→T1,T2,T3,T6；§3.3 字体→T2,T3,T4；§3.4 动效→T3,T5,T7；§3.5 治理文档→T8；§5 验证→T9。全部有对应任务。
- **占位符扫描：** 无 TBD/TODO；所有代码块为完整内容。
- **类型/命名一致：** `--el-color-primary*`、`--font-display`、`u-fade-in`、`fade`(Transition) 在各任务间一致。
- **范围修正：** spec 估"6–8 个含蓝组件"，实测为 **12 个**，T6 已按实精确列出。
