# UI 设计系统地基 实现计划（Design System Foundation）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 [docs/design-system.md](../design-system.md)（feature-clarifications §49 / Q313–Q319）的「暖炭黑 · Claude Code 本色」落成可运行的前端主题地基 + 基础组件。

**Architecture:** CSS 变量（`tokens.css`）单一来源 → Tailwind 与 Element Plus 共读；EP 启用暗模式 + `element-overrides.css` 把 `--el-*` 重映射到令牌；亮纸区用 `.paper` 容器局部切回浅色；交付一个 `/styleguide` 页可视化验证整套主题。

**Tech Stack:** Vue 3.4 + TypeScript（`<script setup>`）+ Element Plus 2.7 + Tailwind 3.4 + Vite 5 + Vitest（jsdom）+ @fontsource。

**Scope（本计划范围）：**
- ✅ 令牌 `tokens.css` + Tailwind 令牌化 + 字体（Inter / JetBrains Mono）
- ✅ Element Plus 暗模式 + `element-overrides.css` 变量重映射
- ✅ 亮纸孤岛 `.paper`
- ✅ 基础组件：状态指示 `StatusIndicator`、应用框架 `AppLayout`
- ✅ `/styleguide` 可视化验证页
- ❌ **不在本计划**：程序库列表页（§41）、编辑器、详情、审计、设置等页面级构建（各自独立计划，建立在本地基上）
- ❌ **推迟**：`wangeditor-overrides.css`（WangEditor 尚未安装，待编辑器构建时一并做）

**前置说明：**
- 所有命令在 `frontend/` 目录下执行。
- 提交步骤假设仓库已 git 初始化；若 `git status` 报「not a git repository」，先 `git init` 或跳过 commit 步骤。
- 现状已确认：`@/` → `src/`（vite + tsconfig 均配）；测试目录 `tests/unit/**/*.spec.ts`（vitest `globals:true` + jsdom）；EP 在 `src/main.ts` 全局注册；`preflight:false` 已设；无 sass（故 EP primary 阶梯用定稿硬值，不用 SCSS mix）。

---

### Task 1：安装字体依赖（Inter / JetBrains Mono）

**Files:**
- Modify: `frontend/package.json`（由 npm 自动写入 dependencies）

- [ ] **Step 1: 安装 @fontsource 字体包**

Run（在 `frontend/`）:
```bash
npm install @fontsource/inter@^5 @fontsource/jetbrains-mono@^5
```
Expected: `package.json` 的 `dependencies` 新增 `@fontsource/inter` 与 `@fontsource/jetbrains-mono`，`node_modules` 装好。

- [ ] **Step 2: 验证字体文件存在**

Run:
```bash
node -e "require.resolve('@fontsource/inter/400.css'); require.resolve('@fontsource/jetbrains-mono/400.css'); console.log('fonts ok')"
```
Expected: 输出 `fonts ok`（无报错）。

- [ ] **Step 3: Commit**

```bash
git add package.json package-lock.json
git commit -m "chore(ui): add Inter + JetBrains Mono webfonts"
```

---

### Task 2：创建令牌与 Element Plus 覆盖样式

两个纯样式文件，本任务只创建、不接线（Task 3 才生效），故无视觉副作用。

**Files:**
- Create: `frontend/src/assets/styles/tokens.css`
- Create: `frontend/src/assets/styles/element-overrides.css`

- [ ] **Step 1: 创建 `tokens.css`**

写入 `frontend/src/assets/styles/tokens.css`：
```css
/* 设计令牌单一来源。权威见 docs/design-system.md §2 / feature-clarifications §49。 */
:root {
  /* 暗壳 */
  --bg-base: #1a1714;
  --bg-surface: #211e1b;
  --bg-elevated: #2a2622;
  --bg-hover: #322d28;
  --border-subtle: #3a352f;
  --border-strong: #4a443c;
  --text-primary: #ece6dd;
  --text-secondary: #b3aa9e;
  --text-tertiary: #7a7269;

  /* 陶土橙强调（仅交互） */
  --accent: #d97757;
  --accent-hover: #e08a6e;
  --accent-active: #c56546;
  --accent-rgb: 217 119 87;

  /* 状态盘（修订 Q172） */
  --st-draft: #a89a86;
  --st-published: #88b07a;
  --st-archived: #6b635a;
  --st-deprecated: #d9685e;
}

/* 亮纸孤岛：编辑器画布 / PDF 预览。局部把变量切回浅色。 */
.paper {
  --paper-bg: #faf8f4;
  --paper-text: #2a2521;
  --paper-border: #e5dfd5;
  background: var(--paper-bg);
  color: var(--paper-text);
  --el-bg-color: var(--paper-bg);
  --el-text-color-primary: var(--paper-text);
  --el-border-color: var(--paper-border);
}
```

- [ ] **Step 2: 创建 `element-overrides.css`**

写入 `frontend/src/assets/styles/element-overrides.css`：
```css
/* Element Plus 暗模式变量重映射 → 设计令牌。集中覆盖（合规 frontend-coding-standards §8.1）。
   EP primary 阶梯暗模式用定稿硬值（无 sass）。 */
html.dark {
  --el-bg-color: var(--bg-base);
  --el-bg-color-page: var(--bg-base);
  --el-bg-color-overlay: var(--bg-elevated);
  --el-fill-color: var(--bg-hover);
  --el-fill-color-light: var(--bg-elevated);
  --el-fill-color-lighter: var(--bg-elevated);
  --el-fill-color-blank: var(--bg-base);

  --el-text-color-primary: var(--text-primary);
  --el-text-color-regular: var(--text-primary);
  --el-text-color-secondary: var(--text-secondary);
  --el-text-color-placeholder: var(--text-tertiary);
  --el-text-color-disabled: var(--text-tertiary);

  --el-border-color: var(--border-subtle);
  --el-border-color-light: var(--border-subtle);
  --el-border-color-lighter: var(--border-subtle);
  --el-border-color-extra-light: var(--border-subtle);
  --el-border-color-dark: var(--border-strong);
  --el-border-color-darker: var(--border-strong);

  --el-border-radius-base: 4px;
  --el-border-radius-small: 4px;

  /* primary → 陶土橙（暗模式向底色混的阶梯，定稿硬值） */
  --el-color-primary: var(--accent);
  --el-color-primary-light-3: #a85e45;
  --el-color-primary-light-5: #7a4634;
  --el-color-primary-light-7: #4d2e22;
  --el-color-primary-light-8: #3a241b;
  --el-color-primary-light-9: #261913;
  --el-color-primary-dark-2: #c56546;

  /* 语义色 → 状态盘 */
  --el-color-success: var(--st-published);
  --el-color-info: var(--st-draft);
  --el-color-danger: var(--st-deprecated);
  --el-color-warning: #d9a14e;
}
```

- [ ] **Step 3: 验证类型/构建未被破坏（纯 CSS，不应影响）**

Run:
```bash
npm run typecheck
```
Expected: PASS（0 error）。

- [ ] **Step 4: Commit**

```bash
git add src/assets/styles/tokens.css src/assets/styles/element-overrides.css
git commit -m "feat(ui): add design tokens + Element Plus dark overrides"
```

---

### Task 3：接线主题（启用暗模式 + 引入令牌/覆盖/字体）

把 Task 1/2 的产物接入启动链路，主题在本任务后「点亮」。CSS 源顺序 = EP 基 → EP 暗 → 令牌 → tailwind(main.css) → 覆盖（覆盖最后、同 `html.dark` 特异性下胜出）。

**Files:**
- Modify: `frontend/src/main.ts`
- Modify: `frontend/index.html`
- Modify: `frontend/src/assets/styles/main.css`

- [ ] **Step 1: 改 `main.ts` 的导入链**

把 `frontend/src/main.ts` 全文替换为：
```ts
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import 'element-plus/theme-chalk/dark/css-vars.css'
import '@fontsource/inter/400.css'
import '@fontsource/inter/500.css'
import '@fontsource/inter/600.css'
import '@fontsource/jetbrains-mono/400.css'
import '@fontsource/jetbrains-mono/500.css'
import './assets/styles/tokens.css'
import './assets/styles/main.css'
import './assets/styles/element-overrides.css'

import App from './App.vue'
import router from './router'

const app = createApp(App)

app.use(createPinia())
app.use(router)
app.use(ElementPlus)

app.mount('#app')
```

- [ ] **Step 2: 给 `<html>` 加 `dark` 类**

把 `frontend/index.html` 第 2 行 `<html lang="zh-CN">` 改为：
```html
<html lang="zh-CN" class="dark">
```

- [ ] **Step 3: 改 `main.css` 基样式为暗壳**

把 `frontend/src/assets/styles/main.css` 全文替换为：
```css
@tailwind base;
@tailwind components;
@tailwind utilities;

html,
body,
#app {
  height: 100%;
  margin: 0;
  font-family: 'Inter', 'PingFang SC', 'Microsoft YaHei', 'Helvetica Neue', Arial, sans-serif;
  color: var(--text-primary);
  background: var(--bg-base);
}
```

- [ ] **Step 4: 构建验证**

Run:
```bash
npm run build
```
Expected: 构建成功（vue-tsc 0 error + vite build 完成），无 `Cannot find module 'element-plus/theme-chalk/dark/css-vars.css'` 等报错。

- [ ] **Step 5: Commit**

```bash
git add src/main.ts index.html src/assets/styles/main.css
git commit -m "feat(ui): wire dark theme (EP dark mode + tokens + fonts)"
```

---

### Task 4：Tailwind 令牌化

让 Tailwind 工具类读同一份 CSS 变量；删除旧 `primary:#409eff`；加 mono 字体族。

**Files:**
- Modify: `frontend/tailwind.config.js`

- [ ] **Step 1: 替换 `tailwind.config.js`**

把 `frontend/tailwind.config.js` 全文替换为：
```js
/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        base: 'var(--bg-base)',
        surface: 'var(--bg-surface)',
        elevated: 'var(--bg-elevated)',
        hover: 'var(--bg-hover)',
        line: {
          subtle: 'var(--border-subtle)',
          strong: 'var(--border-strong)',
        },
        ink: {
          DEFAULT: 'var(--text-primary)',
          soft: 'var(--text-secondary)',
          faint: 'var(--text-tertiary)',
        },
        accent: {
          DEFAULT: 'var(--accent)',
          hover: 'var(--accent-hover)',
          active: 'var(--accent-active)',
        },
        st: {
          draft: 'var(--st-draft)',
          published: 'var(--st-published)',
          archived: 'var(--st-archived)',
          deprecated: 'var(--st-deprecated)',
        },
        paper: {
          DEFAULT: 'var(--paper-bg)',
          text: 'var(--paper-text)',
          border: 'var(--paper-border)',
        },
      },
      fontFamily: {
        sans: ['Inter', 'PingFang SC', 'Microsoft YaHei', 'Helvetica Neue', 'Arial', 'sans-serif'],
        mono: ['JetBrains Mono', 'Sarasa Mono SC', 'ui-monospace', 'SFMono-Regular', 'monospace'],
      },
    },
  },
  plugins: [],
  corePlugins: {
    // Element Plus 自带 preflight，避免冲突
    preflight: false,
  },
}
```

> 注：颜色 token 用 `var(--x)`，故不支持 `bg-accent/50` 这类透明度修饰；需透明度时用 `rgb(var(--accent-rgb)/.12)` 自定义类。边框色类名为 `border-line-subtle`（避免与 Tailwind `border` 前缀混淆）。

- [ ] **Step 2: 构建验证**

Run:
```bash
npm run build
```
Expected: 构建成功，无报错。

- [ ] **Step 3: Commit**

```bash
git add tailwind.config.js
git commit -m "feat(ui): tokenize Tailwind theme (colors + mono font)"
```

---

### Task 5：状态元数据模块（TDD）

状态 → 中文标签 / 令牌名 / 圆点填充，单一来源，供 `StatusIndicator` 与未来列表页复用。

**Files:**
- Test: `frontend/tests/unit/types/status.spec.ts`
- Create: `frontend/src/types/status.ts`

- [ ] **Step 1: 写失败测试**

写入 `frontend/tests/unit/types/status.spec.ts`：
```ts
import { describe, it, expect } from 'vitest'
import { STATUS_META } from '@/types/status'

describe('STATUS_META', () => {
  it('maps PUBLISHED to 已发布 / st-published / filled', () => {
    expect(STATUS_META.PUBLISHED).toEqual({ label: '已发布', token: 'st-published', filled: true })
  })

  it('maps DRAFT to 草稿 / st-draft / hollow', () => {
    expect(STATUS_META.DRAFT).toEqual({ label: '草稿', token: 'st-draft', filled: false })
  })

  it('maps ARCHIVED to 已归档 / st-archived / filled', () => {
    expect(STATUS_META.ARCHIVED).toEqual({ label: '已归档', token: 'st-archived', filled: true })
  })
})
```

- [ ] **Step 2: 运行测试确认失败**

Run:
```bash
npx vitest run tests/unit/types/status.spec.ts
```
Expected: FAIL，报 `Cannot find module '@/types/status'` 或解析错误。

- [ ] **Step 3: 写最小实现**

写入 `frontend/src/types/status.ts`：
```ts
export type ProcedureStatus = 'DRAFT' | 'PUBLISHED' | 'ARCHIVED'

export interface StatusMeta {
  /** 中文标签 */
  label: string
  /** 对应 tokens.css 的 CSS 变量名（不含 -- 前缀） */
  token: string
  /** true=实心圆点 ●，false=空心圆点 ○ */
  filled: boolean
}

export const STATUS_META: Record<ProcedureStatus, StatusMeta> = {
  DRAFT: { label: '草稿', token: 'st-draft', filled: false },
  PUBLISHED: { label: '已发布', token: 'st-published', filled: true },
  ARCHIVED: { label: '已归档', token: 'st-archived', filled: true },
}
```

- [ ] **Step 4: 运行测试确认通过**

Run:
```bash
npx vitest run tests/unit/types/status.spec.ts
```
Expected: PASS（3 passed）。

- [ ] **Step 5: Commit**

```bash
git add src/types/status.ts tests/unit/types/status.spec.ts
git commit -m "feat(ui): add ProcedureStatus meta (revised Q172 palette)"
```

---

### Task 6：状态指示组件 StatusIndicator（TDD）

圆点 + 等宽风格标签 + 可选「废止」描边 tag（§3.4 / Q317）。

**Files:**
- Test: `frontend/tests/unit/components/StatusIndicator.spec.ts`
- Create: `frontend/src/components/common/StatusIndicator.vue`

- [ ] **Step 1: 写失败测试**

写入 `frontend/tests/unit/components/StatusIndicator.spec.ts`：
```ts
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import StatusIndicator from '@/components/common/StatusIndicator.vue'

describe('StatusIndicator', () => {
  it('renders the published label with a filled dot colored by token', () => {
    const w = mount(StatusIndicator, { props: { status: 'PUBLISHED' } })
    expect(w.find('.status-label').text()).toBe('已发布')
    expect(w.find('.status-dot').classes()).toContain('status-dot--filled')
    expect(w.find('.status-dot').attributes('style')).toContain('var(--st-published)')
  })

  it('renders draft with a hollow dot', () => {
    const w = mount(StatusIndicator, { props: { status: 'DRAFT' } })
    expect(w.find('.status-label').text()).toBe('草稿')
    expect(w.find('.status-dot').classes()).toContain('status-dot--hollow')
  })

  it('appends a 废止 tag when deprecated', () => {
    const w = mount(StatusIndicator, { props: { status: 'ARCHIVED', deprecated: true } })
    expect(w.find('.status-deprecated').text()).toBe('废止')
  })

  it('omits the 废止 tag by default', () => {
    const w = mount(StatusIndicator, { props: { status: 'PUBLISHED' } })
    expect(w.find('.status-deprecated').exists()).toBe(false)
  })
})
```

- [ ] **Step 2: 运行测试确认失败**

Run:
```bash
npx vitest run tests/unit/components/StatusIndicator.spec.ts
```
Expected: FAIL，报 `Cannot find module '@/components/common/StatusIndicator.vue'`。

- [ ] **Step 3: 写最小实现**

写入 `frontend/src/components/common/StatusIndicator.vue`：
```vue
<script setup lang="ts">
import { computed } from 'vue'
import { STATUS_META, type ProcedureStatus } from '@/types/status'

interface Props {
  status: ProcedureStatus
  deprecated?: boolean
}

const props = withDefaults(defineProps<Props>(), { deprecated: false })

const meta = computed(() => STATUS_META[props.status])
const dotStyle = computed(() => ({ color: `var(--${meta.value.token})` }))
</script>

<template>
  <span class="status">
    <span
      class="status-dot"
      :class="meta.filled ? 'status-dot--filled' : 'status-dot--hollow'"
      :style="dotStyle"
    />
    <span class="status-label">{{ meta.label }}</span>
    <span v-if="deprecated" class="status-deprecated">废止</span>
  </span>
</template>

<style scoped>
.status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}
.status-dot--filled {
  background: currentColor;
}
.status-dot--hollow {
  border: 1.5px solid currentColor;
}
.status-label {
  font-size: 14px;
  color: var(--text-primary);
}
.status-deprecated {
  margin-left: 4px;
  padding: 0 6px;
  font-size: 12px;
  line-height: 18px;
  color: var(--st-deprecated);
  border: 1px solid var(--st-deprecated);
  border-radius: 4px;
}
</style>
```

- [ ] **Step 4: 运行测试确认通过**

Run:
```bash
npx vitest run tests/unit/components/StatusIndicator.spec.ts
```
Expected: PASS（4 passed）。

- [ ] **Step 5: Commit**

```bash
git add src/components/common/StatusIndicator.vue tests/unit/components/StatusIndicator.spec.ts
git commit -m "feat(ui): add StatusIndicator component"
```

---

### Task 7：应用框架布局 AppLayout（TDD）

顶栏（48px，含品牌 + search/actions 插槽）+ 左侧栏（240px，sidebar 插槽）+ 主区（默认插槽）。§3.1。

**Files:**
- Test: `frontend/tests/unit/layouts/AppLayout.spec.ts`
- Create: `frontend/src/layouts/AppLayout.vue`

- [ ] **Step 1: 写失败测试**

写入 `frontend/tests/unit/layouts/AppLayout.spec.ts`：
```ts
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import AppLayout from '@/layouts/AppLayout.vue'

describe('AppLayout', () => {
  it('renders the brand, sidebar slot and default slot', () => {
    const w = mount(AppLayout, {
      slots: {
        sidebar: '<nav class="t-side">SIDE</nav>',
        default: '<main class="t-main">MAIN</main>',
      },
    })
    expect(w.find('.app-brand').text()).toContain('Smart SOP')
    expect(w.find('.t-side').exists()).toBe(true)
    expect(w.find('.t-main').exists()).toBe(true)
  })

  it('renders the topbar search and actions slots', () => {
    const w = mount(AppLayout, {
      slots: {
        search: '<input class="t-search" />',
        actions: '<button class="t-act">A</button>',
      },
    })
    expect(w.find('.t-search').exists()).toBe(true)
    expect(w.find('.t-act').exists()).toBe(true)
  })
})
```

- [ ] **Step 2: 运行测试确认失败**

Run:
```bash
npx vitest run tests/unit/layouts/AppLayout.spec.ts
```
Expected: FAIL，报 `Cannot find module '@/layouts/AppLayout.vue'`。

- [ ] **Step 3: 写最小实现**

写入 `frontend/src/layouts/AppLayout.vue`：
```vue
<script setup lang="ts">
// 纯布局壳：插槽 search / actions / sidebar / 默认（主区）
</script>

<template>
  <div class="app-layout">
    <header class="app-topbar">
      <span class="app-brand">Smart SOP</span>
      <div class="app-topbar-search"><slot name="search" /></div>
      <div class="app-topbar-actions"><slot name="actions" /></div>
    </header>
    <div class="app-body">
      <aside class="app-sidebar"><slot name="sidebar" /></aside>
      <main class="app-main"><slot /></main>
    </div>
  </div>
</template>

<style scoped>
.app-layout {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg-base);
}
.app-topbar {
  display: flex;
  align-items: center;
  gap: 16px;
  height: 48px;
  padding: 0 16px;
  background: var(--bg-surface);
  border-bottom: 1px solid var(--border-subtle);
}
.app-brand {
  font-weight: 600;
  color: var(--text-primary);
}
.app-topbar-search {
  flex: 1;
}
.app-topbar-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}
.app-body {
  display: flex;
  flex: 1;
  min-height: 0;
}
.app-sidebar {
  width: 240px;
  flex-shrink: 0;
  background: var(--bg-surface);
  border-right: 1px solid var(--border-subtle);
  overflow-y: auto;
}
.app-main {
  flex: 1;
  min-width: 0;
  overflow-y: auto;
  background: var(--bg-base);
}
</style>
```

- [ ] **Step 4: 运行测试确认通过**

Run:
```bash
npx vitest run tests/unit/layouts/AppLayout.spec.ts
```
Expected: PASS（2 passed）。

- [ ] **Step 5: Commit**

```bash
git add src/layouts/AppLayout.vue tests/unit/layouts/AppLayout.spec.ts
git commit -m "feat(ui): add AppLayout shell"
```

---

### Task 8：Styleguide 验证页 + 路由

非生产用的可视化验证页，把主题 + 组件 + 关键 EP 控件 + 亮纸区放一起，供「跑起来肉眼验收」。

**Files:**
- Create: `frontend/src/views/styleguide/index.vue`
- Modify: `frontend/src/router/index.ts`

- [ ] **Step 1: 加路由**

把 `frontend/src/router/index.ts` 的 `routes` 数组替换为：
```ts
const routes: RouteRecordRaw[] = [
  {
    path: '/',
    redirect: '/procedures/library',
  },
  {
    path: '/styleguide',
    component: () => import('@/views/styleguide/index.vue'),
  },
  // Phase 2 起会按模块拆分到 router/modules/ 下
]
```

- [ ] **Step 2: 创建 styleguide 页**

写入 `frontend/src/views/styleguide/index.vue`：
```vue
<script setup lang="ts">
// 开发用主题验证页（非生产页面）。
import { ref } from 'vue'
import AppLayout from '@/layouts/AppLayout.vue'
import StatusIndicator from '@/components/common/StatusIndicator.vue'

const kw = ref('')
const rows = [
  { code: 'QC-0001', name: '装配作业规程', v: 'v3' },
  { code: 'QC-0002', name: '检验作业指导', v: 'v2' },
]
</script>

<template>
  <AppLayout>
    <template #search>
      <el-input v-model="kw" placeholder="搜索全库…" clearable class="max-w-sm" />
    </template>
    <template #actions>
      <el-button type="primary">＋ 新建程序</el-button>
    </template>
    <template #sidebar>
      <div class="p-3 text-ink-soft">
        <div class="px-2 py-1.5 text-xs">标准文件库</div>
        <div class="px-2 py-1.5 text-ink">▸ QC 质量</div>
        <div class="px-2 py-1.5 text-ink">▸ QA 保证</div>
      </div>
    </template>

    <div class="flex flex-col gap-6 p-6">
      <section>
        <h2 class="text-ink">状态指示</h2>
        <div class="mt-3 flex gap-6">
          <StatusIndicator status="DRAFT" />
          <StatusIndicator status="PUBLISHED" />
          <StatusIndicator status="ARCHIVED" />
          <StatusIndicator status="ARCHIVED" :deprecated="true" />
        </div>
      </section>

      <section>
        <h2 class="text-ink">按钮</h2>
        <div class="mt-3 flex gap-3">
          <el-button type="primary">主按钮</el-button>
          <el-button>次按钮</el-button>
          <el-button type="danger" plain>危险</el-button>
        </div>
      </section>

      <section>
        <h2 class="text-ink">表格（EP 暗化）</h2>
        <el-table :data="rows" class="mt-3">
          <el-table-column prop="code" label="编号" />
          <el-table-column prop="name" label="名称" />
          <el-table-column prop="v" label="版本" />
        </el-table>
      </section>

      <section class="flex gap-4">
        <div class="flex-1">
          <h2 class="text-ink">暗壳卡片</h2>
          <div class="mt-3 rounded-md border border-line-subtle bg-elevated p-4 text-ink">
            暗壳面板示例
          </div>
        </div>
        <div class="paper flex-1 rounded-md p-4">
          <h3>亮纸文档区</h3>
          <p>本规程规定了装配工序的检验要求……（这是将来打印成 PDF 的那张纸）</p>
        </div>
      </section>
    </div>
  </AppLayout>
</template>
```

- [ ] **Step 3: 类型/构建验证**

Run:
```bash
npm run typecheck && npm run build
```
Expected: 两者均 PASS（0 error）。

- [ ] **Step 4: Commit**

```bash
git add src/views/styleguide/index.vue src/router/index.ts
git commit -m "feat(ui): add /styleguide theme verification page"
```

---

### Task 9：整体验收（lint / typecheck / test / build + 肉眼）

**Files:** 无（仅运行 + 人工检查）

- [ ] **Step 1: 全套质量门禁**

Run（在 `frontend/`）:
```bash
npm run lint && npm run typecheck && npm run test && npm run build
```
Expected: 全部 PASS——`lint` 0 error、`typecheck` 0 error、`test` 全绿（status/StatusIndicator/AppLayout 共 9 用例）、`build` 成功。

- [ ] **Step 2: 起开发服务器**

Run:
```bash
npm run dev
```
然后浏览器打开 `http://localhost:5173/styleguide`。

- [ ] **Step 3: 肉眼验收清单**（对照 design-system.md）

- [ ] 整页底色为暖炭黑（非 EP 默认浅灰），文字暖白。
- [ ] 顶栏 / 侧栏为 `bg-surface` 暖炭黑，分隔是细线非阴影。
- [ ] 「＋ 新建程序」主按钮为实心**陶土橙**（非 EP 蓝）。
- [ ] 状态：草稿=空心暖灰点、已发布=**鼠尾草绿**实心点、归档=暗点、末项带描边红「废止」tag。
- [ ] el-input 聚焦时边框转**陶土橙**；el-table 暗底、行线分隔。
- [ ] 「亮纸文档区」卡片为浅米白底 + 墨黑字，与四周暗壳形成「桌上一张纸」对比。
- [ ] 编号 `QC-0001` 等需要等宽时类名 `font-mono` 渲染为 JetBrains Mono（可在表格中加 `class="font-mono"` 临时验证；列表页正式应用见后续 §41 计划）。

> 任一项不符 → 回到对应 Task 调样式；若涉及配色语义变更，先回写 design-system.md + feature-clarifications §49 再改代码。

---

## 自查（Self-Review）

**Spec 覆盖（design-system.md）：**
- §2.1 色板 → Task 2（tokens）+ Task 4（Tailwind）✅
- §2.2 字体 → Task 1（安装）+ Task 3（导入）+ Task 4（fontFamily）✅
- §2.4 圆角/边框/阴影 → Task 2（`--el-border-radius` + 令牌）✅
- §2.1 状态盘（修订 Q172）→ Task 5（meta）+ Task 6（组件）✅
- §3.1 应用框架 → Task 7（AppLayout）✅
- §3.4 状态指示 → Task 6 ✅
- §3.8 亮纸孤岛 → Task 2（`.paper`）+ Task 8（演示）✅
- §4 EP 改造（暗模式 + 变量重映射 + 亮纸孤岛 + 单一来源）→ Task 2/3 ✅
- §4.5 自建 vs EP 分工 → 体现在 Task 6/7 自建 + Task 8 用 EP 控件 ✅

**已知缺口（有意，留给后续页面级计划）：**
- §3.2 侧栏树激活态、§3.5 程序库列表行、§3.6 输入封装、§3.7 卡片/表格组件化、§3.9 模态/Toast/空状态 → 这些在具体页面（§41 列表页等）中落地，本地基计划只提供令牌 + 框架 + 状态组件 + EP 暗化基础。
- `wangeditor-overrides.css` → WangEditor 未安装，待编辑器构建时做。

**占位符扫描：** 无 TBD/TODO；所有代码步骤含完整代码。

**类型一致性：** `ProcedureStatus` / `StatusMeta` / `STATUS_META`（Task 5）被 `StatusIndicator`（Task 6）按相同签名引用；`token` 字段值（`st-draft` 等）与 `tokens.css`（Task 2）变量名一一对应；测试断言 `var(--st-published)` 与组件 `dotStyle` 一致。
