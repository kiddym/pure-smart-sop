# 可折叠的导入面板（原文 / 详情）设计

**日期：** 2026-05-25
**状态：** 已批准
**作者：** 协作设计（cui_yuming + Claude）

## 背景与目标

V2 beta 的"从 Word 导入"对话框是三栏布局：

- **左**：`WordPreviewPanel`（Word 原文预览）
- **中**：`ImportTreePanel`（章节/步骤列表，用户主要工作区）
- **右**：`ImportDetailPanel`（选中节点详情）

三栏之间用可拖拽的分隔条（splitter）调宽，宽度以百分比存于 localStorage（`smartsop.import.cols`）。

用户实际操作主要在**中栏**。左右两栏经常只是参考，希望能**一键折叠**左、右两栏，把空间让给中栏；再一键展开恢复。

**目标：** 给左栏（原文）和右栏（详情）各加一个一键折叠/展开能力，折叠后变成一根细竖条（rail），中栏自动填满；折叠状态像列宽一样被记住。

## 范围

**做：**
- 折叠/展开 左栏 与 右栏（中栏不可折叠）。
- 折叠后该栏变 32px 竖条，含展开箭头 + 竖排标签。
- 折叠状态持久化（localStorage）。

**不做（YAGNI）：**
- 中栏折叠。
- 折叠动画/过渡（可后续加，先求正确）。
- 改动 `WordPreviewPanel` / `ImportDetailPanel` 内部（两者保持不变）。
- 改动现有拖拽/双击重置逻辑的语义。

## 架构

所有折叠 UI 与状态都收敛在 `ImportDialog.vue`，两个子面板**完全不改**。纯布局计算抽到 `importCols.ts` 做成可单测的纯函数。新增一个轻量展示组件 `ImportSideRail.vue` 渲染折叠后的竖条。

### 状态

`ImportDialog.vue` 新增：

```ts
const collapsed = useStorage<CollapseState>('smartsop.import.collapsed', { left: false, right: false })
collapsed.value = sanitizeCollapsed(collapsed.value)
```

- `cols`（百分比）在折叠期间**不变**，因此展开后恢复到用户记住的宽度。
- 折叠状态独立持久化，不与 `cols` 混存。

### 纯布局函数（`importCols.ts`）

新增：

```ts
/** 折叠后竖条宽度，像素。 */
export const RAIL_PX = 32

export interface CollapseState {
  left: boolean
  right: boolean
}

export interface ColFlex {
  /** 每列的 CSS flex 简写值。 */
  left: string
  mid: string
  right: string
  /** 左|中 分隔条是否可见（左栏折叠时隐藏）。 */
  showLM: boolean
  /** 中|右 分隔条是否可见（右栏折叠时隐藏）。 */
  showMR: boolean
}

/**
 * 由列宽百分比 + 折叠状态算出三列的 flex 值与分隔条可见性。
 * - 可见列 → flex 权重 = 其百分比（`"<pct> 1 0%"`），按比例瓜分剩余空间；
 * - 折叠列 → 固定细条（`"0 0 ${RAIL_PX}px"`）；
 * - 折叠那侧的分隔条隐藏。
 */
export function colFlex(c: ColWidths, s: CollapseState): ColFlex

/** 校验持久化的折叠状态，非法时回退到 { left:false, right:false }。 */
export function sanitizeCollapsed(v: unknown): CollapseState
```

`colFlex` 行为契约：

| 折叠状态 | left flex | mid flex | right flex | showLM | showMR |
|---|---|---|---|---|---|
| 都不折叠 | `"38 1 0%"` | `"28 1 0%"` | `"34 1 0%"` | true | true |
| 仅左折叠 | `"0 0 32px"` | `"28 1 0%"` | `"34 1 0%"` | false | true |
| 仅右折叠 | `"38 1 0%"` | `"28 1 0%"` | `"0 0 32px"` | true | false |
| 都折叠 | `"0 0 32px"` | `"28 1 0%"` | `"0 0 32px"` | false | false |

（表中数字以默认 `{ left:38, mid:28 }`、`rightOf=34` 为例。）

权重值用百分比即可——flex-grow 只看比例，folded 侧退出后剩余两列按各自百分比比例瓜分；都折叠时中栏是唯一可增长列，自动填满。

`sanitizeCollapsed`：仅当输入是对象且 `left`/`right` 为 boolean 时按位取值，否则整体回退 `{ left:false, right:false }`。

### 折叠/展开交互（`ImportDialog.vue`）

**折叠触发器** = 分隔条上的一个小箭头按钮：

- 左|中 分隔条：`«`，`title="折叠原文预览"`，点击 → `collapsed.left = true`
- 中|右 分隔条：`»`，`title="折叠详情"`，点击 → `collapsed.right = true`
- 按钮 `@click.stop` + `@pointerdown.stop`，避免触发拖拽/双击重置；分隔条其余区域照常拖拽。

**折叠后渲染**：某侧折叠时，该 `.col` 渲染 `ImportSideRail` 取代原面板；对应分隔条（由 `showLM`/`showMR` 控制）隐藏。

模板结构（示意）：

```
<div class="cols">
  <div class="col" :style="{ flex: cf.left }">
    <ImportSideRail v-if="collapsed.left" label="Word 原文预览" side="left" @expand="collapsed.left = false" />
    <WordPreviewPanel v-else :file="ctx.file.value" />
  </div>
  <div v-if="cf.showLM" class="splitter" ...拖拽/双击... >
    <button class="collapse-btn" title="折叠原文预览" @click.stop="collapsed.left = true" @pointerdown.stop>«</button>
  </div>
  <div class="col" :style="{ flex: cf.mid }"><ImportTreePanel :ctx="ctx" /></div>
  <div v-if="cf.showMR" class="splitter" ...拖拽/双击... >
    <button class="collapse-btn" title="折叠详情" @click.stop="collapsed.right = true" @pointerdown.stop>»</button>
  </div>
  <div class="col" :style="{ flex: cf.right }">
    <ImportSideRail v-if="collapsed.right" label="详情" side="right" @expand="collapsed.right = false" />
    <ImportDetailPanel v-else :ctx="ctx" />
  </div>
</div>
```

其中 `cf = colFlex(cols.value, collapsed.value)`（computed）。原来用 `width: x%` 改为 `flex: cf.xxx`。

### 新组件 `ImportSideRail.vue`

折叠后的竖条。

- **props**：`{ label: string; side: 'left' | 'right' }`
- **emit**：`(e: 'expand')`
- **渲染**：32px 宽、占满高度的竖条；顶部一个展开箭头（`side==='left'` → `»`，`side==='right'` → `«`，即"朝向面板原本展开的方向"）；箭头下方竖排标签（`writing-mode: vertical-rl`）。
- **交互**：点击整条（或箭头）emit `expand`；`cursor: pointer`；hover 高亮。
- 左条 label 传 "Word 原文预览"，右条传 "详情"。

## 数据流

1. 用户点分隔条上的折叠箭头 → `collapsed.left/right = true` → `useStorage` 落盘。
2. `cf = colFlex(cols, collapsed)` 重算 → 对应列变 32px rail、分隔条隐藏、其余列按比例填满。
3. 折叠列渲染 `ImportSideRail`；点击 rail → emit `expand` → `collapsed.x = false` → 恢复到 `cols` 记住的百分比。
4. 重新打开对话框 → `useStorage` 读回上次折叠状态（经 `sanitizeCollapsed`）。

## 边界与错误处理

- **两侧都折叠**：中栏 flex 唯一增长，填满（减去两条 32px）。
- **拖拽 / 双击重置**：只作用于可见分隔条；语义不变。折叠状态与 `cols` 解耦，重置只动 `cols`。
- **持久化脏值**：`sanitizeCollapsed` 回退到全展开。
- **折叠期间不丢宽度**：`cols` 不被折叠改写，展开即恢复。

## 测试

- `tests/unit/utils/importCols.spec.ts`（扩展）：
  - `colFlex`：四种折叠组合各断言三列 flex 值 + `showLM`/`showMR`。
  - `sanitizeCollapsed`：合法对象透传；非对象 / 缺字段 / 非布尔 → 回退全展开。
- `tests/unit/ImportSideRail.spec.ts`（新建）：
  - 渲染传入 label。
  - 点击竖条 emit `expand`。
  - `side` 决定箭头字符（left→`»`，right→`«`）。
- `ImportDialog.vue` 接线：仓库无 `ImportDialog.spec`（它依赖大量 api 模块），由 `typecheck` + `build` + 手动冒烟覆盖。

Gate（在 `frontend/`）：`npm run lint && npm run typecheck && npm run test && npm run build`，`--max-warnings 0`。

## 文件清单

- 修改 `frontend/src/utils/importCols.ts`：加 `RAIL_PX`、`CollapseState`、`ColFlex`、`colFlex`、`sanitizeCollapsed`。
- 修改 `frontend/tests/unit/utils/importCols.spec.ts`：加 `colFlex` / `sanitizeCollapsed` 测试。
- 新建 `frontend/src/components/import-v2/ImportSideRail.vue`。
- 新建 `frontend/tests/unit/ImportSideRail.spec.ts`。
- 修改 `frontend/src/components/import-v2/ImportDialog.vue`：折叠状态、`colFlex` 接线、分隔条折叠按钮、rail 渲染。
- 不改 `WordPreviewPanel.vue` / `ImportDetailPanel.vue`。
