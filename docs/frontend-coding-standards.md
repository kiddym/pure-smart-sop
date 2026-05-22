# 前端代码规范（Frontend Coding Standards）

> 适用于 `frontend/` 下所有 Vue / TypeScript 代码。

## 1. 语言与工具链

| 项 | 选型 / 版本 |
|---|------------|
| Node | 20.x LTS |
| 包管理 | `npm`（团队统一） |
| 框架 | Vue 3.4 + Composition API |
| 语言 | TypeScript 5.5 `strict: true` |
| 构建 | Vite 5 |
| UI | Element Plus 2.7 |
| 状态 | Pinia 2.1 |
| 路由 | Vue Router 4 |
| HTTP | Axios |
| 样式 | Tailwind CSS 3.4（utility-first）+ scoped CSS |
| 格式化 | Prettier 3 |
| Linter | ESLint 9（含 `eslint-plugin-vue`、`@typescript-eslint`） |
| 测试 | Vitest + Vue Test Utils；e2e 用 Playwright |

## 2. 目录与模块划分

```
src/
├── api/             # 接口调用层（仅薄封装 axios）
├── components/      # 全局可复用组件
├── views/           # 路由级页面（按模块分目录）
├── store/           # Pinia 模块
├── router/          # 路由配置
├── types/           # 全局类型定义（与后端 schema 对齐）
├── utils/           # 通用工具
├── layouts/         # 布局
└── assets/          # 静态资源
```

**调用方向**：`views → components / api / store`，`components` 之间避免相互依赖（页面级组合在 views 完成）。

## 3. 命名约定

| 类型 | 命名 | 例 |
|------|------|----|
| 文件 - 组件 | PascalCase | `ProcedureEditor.vue` |
| 文件 - 工具 | camelCase | `formatDate.ts` |
| 文件 - 类型 | camelCase | `procedure.ts` |
| 目录 | kebab-case | `procedure-editor/` |
| 组件标签 | PascalCase | `<ProcedureEditor />` |
| Props | camelCase | `:procedure-id` |
| Events | kebab-case | `@update:value` |
| TS 类型 | PascalCase | `interface ProcedureItem` |
| 变量 / 函数 | camelCase | `fetchProcedures` |
| 常量 | SCREAMING_SNAKE_CASE | `MAX_FOLDER_DEPTH` |

## 4. 组件规范

### 4.1 SFC 结构

固定顺序：`<script setup lang="ts">` → `<template>` → `<style scoped>`。

```vue
<script setup lang="ts">
import { ref, computed } from 'vue'
import type { Procedure } from '@/types/procedure'

interface Props {
  procedureId: string
}

const props = defineProps<Props>()
const emit = defineEmits<{
  (e: 'update:value', value: Procedure): void
}>()

const loading = ref(false)
const procedure = ref<Procedure | null>(null)

const displayName = computed(() => procedure.value?.name ?? '加载中…')
</script>

<template>
  <div class="procedure-card">
    {{ displayName }}
  </div>
</template>

<style scoped>
.procedure-card {
  /* ... */
}
</style>
```

### 4.2 强制要求

- **全部用 `<script setup>` + Composition API**，禁止 Options API
- Props / Emits 必须用 TypeScript 泛型声明，禁止字符串数组
- 单组件不超过 300 行；超过则拆分子组件或抽 composables
- v-for 必须有 `:key`
- 异步操作必须处理 loading 与 error 两种状态
- 不在 template 写复杂表达式，用 `computed`

## 5. 状态管理（Pinia）

### 5.1 Store 命名

- 文件 / 导出函数 / store id 三者保持一致：`useProcedureEditorStore` ↔ `procedureEditor.ts` ↔ `id: 'procedureEditor'`
- 模块化拆分：编辑器、列表、设置各一个 store，禁止单一巨型 store

### 5.2 Store 结构

```typescript
import { defineStore } from 'pinia'

export const useProcedureEditorStore = defineStore('procedureEditor', {
  state: () => ({
    procedure: null as Procedure | null,
    selectedId: null as string | null,
    hasUnsavedChanges: false,
  }),
  getters: {
    isEditing: (state) => state.procedure !== null,
  },
  actions: {
    async loadProcedure(id: string) {
      this.procedure = await fetchProcedureDetail(id)
    },
  },
})
```

**规范**：

- State 字段必须显式标注类型（避免推断成 `never`）
- Action 调用 API 必须 await，错误向上抛
- 跨组件共享的临时 UI 状态可入 store；纯组件内部状态用 `ref`

## 6. API 层

### 6.1 文件结构

`src/api/` 按资源拆分：

```typescript
// api/http.ts
import axios from 'axios'

export const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? '/api/v1',
  timeout: 30_000,
})
```

```typescript
// api/folders.ts
import { http } from './http'
import type { Folder, FolderCreate, FolderUpdate } from '@/types/folder'

export const fetchFolderList = (params?: { search?: string }) =>
  http.get<PageResult<Folder>>('/folders', { params })

export const createFolder = (payload: FolderCreate) =>
  http.post<Folder>('/folders', payload)

export const updateFolder = (id: string, payload: FolderUpdate) =>
  http.put<Folder>(`/folders/${id}`, payload)

export const deleteFolder = (id: string) =>
  http.delete<void>(`/folders/${id}`)
```

### 6.2 规范

- 函数命名：`fetch*`（查）/ `create*` / `update*` / `delete*` / `*Action`（业务动作）
- 所有函数必须用 TS 泛型标注返回类型
- 错误处理在调用方处理；API 层不 catch
- 拦截器只做：透传 token（无）、统一错误提示、超时重试

## 7. 路由

- 路由文件按模块拆分：`router/modules/procedure.ts`、`router/modules/settings.ts`
- 用动态 import 实现懒加载：`component: () => import('@/views/procedure/library/index.vue')`
- meta 字段固定结构：`{ title: string; icon?: string; cache?: boolean }`

## 8. 样式

### 8.1 Tailwind + Scoped CSS 混用策略

- 布局、间距、颜色优先用 Tailwind
- 组件特有的复杂样式（动画、伪元素）用 `<style scoped>`
- **禁止**全局样式覆盖 Element Plus（如必须，写在 `assets/styles/element-overrides.css` 并集中管理）

### 8.2 颜色 / 间距

- 颜色统一从 `tailwind.config.js` 的 theme 取，禁止散落 hex
- 间距用 Tailwind 的 0-96 体系，避免 `margin: 13px` 这种魔数

**配色权威 = UI 设计系统**（暖炭黑 · Claude Code 本色，§49 / Q313–Q319）。完整令牌表与组件规范见 [design-system.md](design-system.md)；全部以 CSS 变量（`tokens.css`）为单一来源，Tailwind 与 Element Plus 共读。**禁止散落 hex，新增配色先回填 design-system.md §2.1。**

**状态色（暖盘，修订 Q172 → [feature-clarifications §49 Q317](feature-clarifications.md#四十九ui-设计系统q313q319)）**：

| 状态 | token | Hex | 呈现 |
|------|-------|------|------|
| DRAFT 草稿 | `st-draft` | `#A89A86` | ○ 空心暖灰点 |
| PUBLISHED 已发布 | `st-published` | `#88B07A` | ● 鼠尾草绿点 |
| ARCHIVED 已归档 | `st-archived` | `#6B635A` | ● 暗点 |
| 废止 DEPRECATED | `st-deprecated` | `#D9685E` | 描边小红 tag |

**核心壳色 / 强调色（节选，全表见 design-system.md §2.1）**：

| 用途 | token | Hex |
|------|-------|------|
| 侧栏 / 面板底（暖炭黑） | `bg-surface` | `#211E1B` |
| 卡片 / 弹层 | `bg-elevated` | `#2A2622` |
| 暖白文字 | `text-primary` | `#ECE6DD` |
| 陶土橙强调（仅交互） | `accent` | `#D97757` |
| 亮纸文档区底 | `paper-bg` | `#FAF8F4` |

> 已废弃旧 EP 默认盘（`chip-published #409EFF` 等，原 Q172）。与 [feature-clarifications.md §22.8 / §49](feature-clarifications.md#四十九ui-设计系统q313q319) 与 [editor-behavior.md §1.1](editor-behavior.md) 同步。

## 9. 国际化（Q327）

> 本期**仅中文**（UI + PDF）；**不引入 i18n 框架 / locale 文件**——属未发生需求的过度工程。唯一前向准备 = 不拼句。

- 用户可见文本统一写成中文字面量
- 不在代码中拼接句子（保留此习惯，将来真要 i18n 时低成本接入）

## 10. 测试

详见 [testing-standards.md](testing-standards.md)。前端要求：

- 单元测试用 Vitest + `@vue/test-utils`
- 组件测试聚焦：props 渲染、emit 时机、用户交互
- 关键页面 e2e 用 Playwright
- Mock API 用 MSW（Mock Service Worker），不直接 mock axios

## 11. 代码质量约束（CI 强制）

- `npm run lint` 零 error
- `npm run typecheck` 零 error
- `npm run test` 全部通过
- 单文件不超过 400 行（编辑器组件除外）

## 12. 性能

- 路由按需加载
- 大列表用虚拟滚动（Element Plus 自带的 `el-virtual-list` 或 `vueuse/core` 的 `useVirtualList`）
- 图片懒加载（`loading="lazy"`）
- 编辑器自动保存用防抖（≥ 1000ms）

## 13. 支持范围（Q330）

> 仅面向**桌面**；不做移动端 / 平板布局。

- 浏览器矩阵：现代常青浏览器（Chromium 系 / Firefox / Edge 近 2 个大版本）
- **最小适配宽度 ~1280px**；窄屏不保证可用（可后期再议只读降级）
- 不写移动断点 / 触控手势；布局以左树 + 右内容 + 多 tab 的桌面工作流为准
