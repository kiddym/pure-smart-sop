# Word 导入「层级标定」改为平铺逐段打标 — 设计文档

- 日期：2026-05-24
- 状态：已通过 brainstorming 设计评审，待用户复审 → 写实施计划
- 关联：承接 import-v2 导入弹窗系列改动（三栏可拖拽列宽等）。本设计重做**中栏在「层级标定」模式下的交互**。

## 1. 目标与背景

导入 Word 时，自动解析出的一级/二级/三级标题常与原文不符。当前修正方式（`ImportTreePanel.vue` 的层级标定模式）是：进模式 → 勾选若干行 → 点 `→一级/→二级/→三级/→正文/→忽略` 之一 → **每次操作后自动退出**。要把不同段落设成不同级别，得反复「进模式→勾选→点级别→退出」，非常繁琐。

本设计把「层级标定」模式的中栏从**嵌套树 + 复选框 + 批量按钮**整体替换为**按原文顺序排列的平铺清单**，每段一行配一个 `一级│二级│三级│正文` 分段选择器。每行预选解析器当前猜的级别，用户**只点改错的行**即可。每个模式只干一件事：

- **普通模式**：管「内容 / 顺序 / 存在」——加子章节/内容、上移/下移（同级换位）、删除、改标题。
- **层级标定模式**：只管「级别」——平铺逐段选。
- **步骤标注模式**：不动。

**这是纯前端改动**（实现策略①）。平铺清单的数据从现有 `tree`（解析结果已是原文顺序）拍平得到；维护一张 `每段id → 级别` 映射表（`roleMap`）作为标定期间唯一真相源；点「完成」时用它一次性重建嵌套树，复用现有 `applyLayerRole` 的重建语义。无后端改动、无新依赖。

## 2. 范围

### 做（In scope）

1. 层级标定模式中栏整体改为平铺清单：每段一行 + `一级│二级│三级│正文` 分段选择器（当前级别高亮，预选解析器现值）。
2. 行按 Word 原文顺序排列、**永不跳动**；行文本左侧缩进体现所选级别（一级顶格、二级/三级递进、正文挂在标题下）。**所见即所选**：缩进按用户字面选择显示，层级跳跃（如选了二级但上方无一级）不当场纠正，重建树时再夹紧。
3. 标定模式工具条精简为 `搜索框` + `完成`；移除 `→一级/→二级/→三级/→正文/→忽略` 这一排批量按钮。
4. 标定模式去掉「忽略」入口——剔除页眉页脚等垃圾段改由普通模式的删除完成。
5. 普通模式动态条移除 `⇤ 提升 / ⇥ 降级` 两个按钮（平铺标定已完整覆盖其「改层级」能力）。
6. 新增纯函数 `flattenForMarking(tree)` 与 `buildTreeFromRoles(tree, roleMap)`；后者复用 `applyLayerRole` 后半段的重建逻辑。
7. 单测：上述两个纯函数全覆盖（vitest）。
8. 跑通前端门禁：lint / typecheck / build / vitest。

### 不做（Out of scope，YAGNI）

- 批量操作（多选一次设同级）。预选默认值已大幅减少点击量；如长文档仍嫌烦，留作后续增量。
- 后端 `import_blocks` 管线（实现策略②）。当前以「树里可见的节点」为打标粒度已够用；还原解析器合并/丢弃的更细原始段落是另一个更大的功能。
- 标定模式内新增「忽略」选项。
- 拖拽排序、键盘快捷键标定。
- 任何后端改动、数据库迁移。

## 3. 数据模型与状态

```ts
type LayerRole = 'chapter_1' | 'chapter_2' | 'chapter_3' | 'content'

// 标定期间唯一真相源：每段 id → 目标级别
const roleMap = ref<Map<string, LayerRole>>(new Map())
```

- 进入层级标定模式时：`roleMap` 由 `flattenForMarking(tree)` 初始化，每段预填**解析器当前级别**——
  - `content_type === 'content'` → `'content'`
  - 否则按其在树中的深度 → `chapter_${min(depth, 3)}`
- 点选某行 → `setRole(id, role)` 只改 `roleMap` 中该 id 的值；行缩进随之实时刷新（缩进由 `roleMap` 派生，不重排顺序）。
- 点「完成」→ `tree.value = buildTreeFromRoles(tree.value, roleMap.value)`，重建嵌套树并退回普通模式；用户在嵌套树里看到层级跳跃被夹紧后的真实结果。
- 退出标定模式即清空 `roleMap`。

为何 `roleMap` 而非直接改树：标定时若每点一下就重建树，夹紧可能让「意图」与「显示」漂移；以 `roleMap` 为真相源、显示按字面、重建只在「完成」时发生一次，行为可预测且顺序稳定。

## 4. 核心纯函数（`utils/importTree.ts`）

### 4.1 `flattenForMarking(nodes): MarkRow[]`

按文档序深度遍历，产出平铺行：

```ts
interface MarkRow {
  id: string
  label: string        // 章节用 title；正文用 rich_content 去标签摘要
  defaultRole: LayerRole
}
```

`defaultRole` 即上文「预填解析器当前级别」规则。顺序 = 深度优先前序遍历 = Word 原文顺序。

### 4.2 `buildTreeFromRoles(nodes, roleMap): WizardNode[]`

复用现有 `applyLayerRole` 的后半段（§ importTree.ts L362–408 的重建循环），但**每段都有显式目标级别**，因此比现状更简单——无需再为「未选中后代」推导 delta：

1. 把 `nodes` 拍平为文档序（沿用现有遍历）。
2. 逐段取 `role = roleMap.get(id) ?? 该段默认`，维护 `l1/l2/l3` 三个「当前打开章节」指针：
   - `content`：挂到最深已打开章节（`l3 ?? l2 ?? l1`），无则落根。
   - `chapter_1`：新建根章节，重置 `l1`，清 `l2/l3`。
   - `chapter_2`：挂到 `l1` 下；**`l1` 不存在则夹紧为根级**（层级跳跃所见所选→重建夹紧）；设 `l2`，清 `l3`。
   - `chapter_3`：挂到 `l2` 下；`l2` 不存在则退挂 `l1`；都没有则夹紧为根级；设 `l3`。
3. 内容↔章节互转保数据，**沿用现有逻辑**：章节→正文把标题文本回填正文（`<p>title</p>`）、`skip_numbering=true`；正文→章节用 `title || titleFromHtml(rich_content)` 作标题、清空正文、`skip_numbering=false`。

> 实现上可把现有 `applyLayerRole(nodes, ids, role)` 重构为薄封装：内部构造一张「ids→role、其余保持原级别」的 `roleMap` 再调 `buildTreeFromRoles`；或反之让 `buildTreeFromRoles` 成为通用底座、`applyLayerRole` 调它。择一以避免逻辑重复（细节留给实施计划）。

## 5. 界面（中栏，层级标定模式）

```
┌ 工具条 ────────────────────────────────┐
│ [搜索章节/步骤…]                    完成 │
├ 平铺清单（原文顺序，永不跳动）──────────┤
│ [一级│二级│三级│正文]  目的             │
│ [一级│二级│三级│正文]    适用范围       │   ← 缩进=所选级别
│ [一级│二级│三级│正文]    本文件适用于…  │
│ [一级│二级│三级│正文]  职责             │
└────────────────────────────────────────┘
```

- 分段选择器：Element Plus `el-radio-group` + `el-radio-button`（`size="small"`），四个值 `chapter_1/2/3/content`，当前值高亮。
- 行布局复用 `ImportTreeRow` 思路但去掉复选框、↑↓✕、各类 badge（标定模式只需文本 + 选择器 + 缩进）；建议新建专用行组件 `ImportMarkingRow.vue`，与 `ImportTreeRow.vue` 解耦。
- `ImportTreePanel.vue` 按 `mode` 分支：`layer-marking` 渲染平铺清单（`ImportMarkingRow` 列表），其余模式仍渲染嵌套树（`ImportTreeRow`）。
- 搜索：标定模式保留搜索框，仅过滤显示行，不改 `roleMap`。
- 底部「已忽略」区：保持现状（展示既有忽略项、可恢复）；标定模式不新增忽略。

## 6. 受影响文件

| 文件 | 改动 |
|------|------|
| `frontend/src/utils/importTree.ts` | 新增 `flattenForMarking`、`buildTreeFromRoles`；`applyLayerRole` 重构为复用后者；视引用情况删除 `promoteNode/demoteNode` |
| `frontend/src/composables/useImportDialog.ts` | 新增 `roleMap` 状态 + `setRole` + 进/出标定模式的初始化/清空 + 「完成」调 `buildTreeFromRoles`；移除 `promoteSelected/demoteSelected`（及导出） |
| `frontend/src/components/import-v2/ImportTreePanel.vue` | 按 mode 分支渲染平铺清单；标定模式工具条精简（仅搜索+完成）；普通模式动态条去掉提升/降级按钮 |
| `frontend/src/components/import-v2/ImportMarkingRow.vue` | 新建：单段平铺行（文本 + 缩进 + 分段选择器） |
| `frontend/tests/unit/utils/importTree.spec.ts` | 新增 `flattenForMarking`/`buildTreeFromRoles` 用例；删除 `promoteNode/demoteNode` 相关用例（若函数删除） |

无后端改动、无数据库迁移、无新依赖。

## 7. 测试（TDD，纯函数）

`flattenForMarking`：

| 用例 | 断言 |
|------|------|
| 多层树拍平 | 行顺序 = 文档前序；数量 = 节点总数 |
| 默认级别映射 | 章节按深度→chapter_1/2/3（深度>3 夹紧 3）；content→content |
| 正文摘要 | label 为 rich_content 去标签截断 |

`buildTreeFromRoles`：

| 用例 | 断言 |
|------|------|
| 默认级别 round-trip | 用 `flattenForMarking` 的默认 roleMap 重建，结构与原树一致 |
| 正文归属 | content 挂到最近已打开的最深章节；无章节时落根 |
| 层级跳跃夹紧 | chapter_2 无 l1 → 夹为根级；chapter_3 无 l2 → 退挂 l1 或根 |
| 顺序无关性 | roleMap 写入顺序不影响结果（按文档序重建） |
| 内容→章节保数据 | 标题取 title/titleFromHtml，正文清空，skip_numbering=false |
| 章节→正文保数据 | 标题回填正文 `<p>…</p>`，skip_numbering=true |
| 全选正文 | 所有段落落根、均为 content |

门禁：`npm run lint`、`npm run typecheck`（vue-tsc）、`npm run build`、`npm run test`（vitest）全绿。

## 8. 边界与决策记录

- **层级跳跃**：所见即所选（平铺清单按字面缩进），重建树时夹紧成合法层级，退出后在嵌套树查看真实结果。
- **预填默认**：每行预选解析器当前级别，用户只改错行，无需逐行从头点——这是去掉批量操作仍不繁琐的前提。
- **「忽略」与「提升/降级」下放/移除**：忽略归普通模式删除；提升/降级被平铺标定完整覆盖故移除。代价：调单个节点级别也需进一次标定模式，换来「改层级仅一个入口」。
- **空树 / 全文本**：平铺清单可为空（显示 el-empty）；全为正文时全部落根。
