# 评估：Smart SOP 的 PDF 渲染规范 vs PPA AP-907-005 标准

## Context

用户请求评估本项目 PDF 预览样式是否符合 *PPA AP-907-005 Procedure Writer's Manual (Rev. 2, 2016)* 对**标准 procedure** 的要求。

**关键前提**：项目 PDF 实现尚未编写（`backend/app/services/pdf/` 只有空 `__init__.py`，字体目录 `backend/app/assets/fonts/` 也是空的；前端 `package.json` 无任何 PDF 预览库依赖）。

本评估的对象是项目的**规范文档** [docs/pdf-rendering.md](docs/pdf-rendering.md)（473 行，权威 PDF 规范）+ [docs/data-model.md](docs/data-model.md) 中与 PDF 相关的字段。等同评估"未来按规范实现后是否符合 PPA"。

PPA 适用范围：human-factored technical / administrative procedures。本评估假设 Smart SOP 的目标群体覆盖这两类。

---

## 一、对照评估表

按 PPA 章节顺序逐项核查。

| PPA 章节 | PPA 要求 | Smart SOP 现状 | 评估 |
|---|---|---|---|
| §4.3 Page Layout | Letter 8.5×11"，T/B 0.5"、L/R 0.8" | A4 210×297mm，T/B 1.27cm(≈0.5")、L/R 2.03cm(≈0.8") | ⚠ **纸型不同**（A4 vs Letter），边距数值匹配。中文场景 A4 合理，但与 PPA 字面要求不符 |
| §4.4 Fonts | Arial 11/12pt 或 Times New Roman 12pt | 中文 SimSun 12pt、英文 TNR 12pt | ✓ 英文符合；中文为本地化补充 |
| §4.5 Headers | 强制含：title / number / revision / page number | header 含 编号+名称+版本+第X页/共Y页 | ✓ 完全符合 |
| §4.6 Page Numbering | "Page X of Y"；**封面应计入总页数** | "第 X 页 / 共 Y 页"，**T 仅统计内容页**，封面/TOC/修订页不计 | ✗ **不符合**：T 的统计口径与 PPA 相反 |
| §4.7 Line Spacing | "Consider single line spacing"，步骤间至少 1 行空白 | 1.5× 行距 | ⚠ 偏差但可接受（PPA 反对"压缩"而非反对"加宽"） |
| §4.8 Continuation Heading | 跨页步骤须加 "X.X (continued)" 续行标题 | 自定义 ContinuedFlowable 加「续 step {code}」 | ✓ 概念符合，措辞不同 |
| §4.9 Step Numbering | 最多 4 级：1.0 → 1 → a → (1) → (a) | 章节 level 1-3 + step 一层子节点（如 1.2.1） | ⚠ **深度不足**：缺少 a / (1) / (a) 三级；且 step 之间无 substep 概念。复杂程序无法表达 |
| §4.11 Cover Page | 强制：title / number / revision / **Level of Use** | 含：name / code / version / folder path / risk / quality / dates / 签名栏 | ✗ **缺失"Level of Use"**（PPA 四项必备之一：Reference Use / Continuous Use / Information Use） |
| §4.12 TOC | 列章节 + **附件** + 页码；续页加 "(continued)" | 列 chapter，附件未列；续页保留"目录"标题但**无 "(continued)"** | ⚠ 不含附件；续页标记不符 |
| §4.13.1 Sections | 强制章节顺序：Purpose / Scope / References / Definitions / Responsibilities / Precautions & Limitations / Prerequisites / Instructions / Acceptance Criteria / Retention of Records / Summary of Alterations / Attachments | 用户自由创建章节树，**无模板强制结构** | ✗ **重大缺失**：没有模板层强制 12 个标准 section |
| §4.13.13 Attachments | 必备结构区段，独立编号 "Page 1 of N"，继承父 header | `tb_procedure_attachment` 表存在（文件上传/下载），但 [docs/pdf-rendering.md](docs/pdf-rendering.md) **未渲染附件到 PDF** | ✗ **重大缺失**：附件不进 PDF 主体 |
| §4.15 Notes/Cautions/Warnings | **三类独立盒子**，顺序 Note→Caution→Warning；多条同框 | 仅一个 `warning-block`（黄底） | ✗ **重大不符**：未区分三类。黄色对应 Caution 视觉，但语义混淆 |
| §4.16 Conditional Steps | IF / WHEN / THEN / AND / OR / NOT / IF AT ANY TIME / WHILE 须特殊 emphasis（如全大写） | 规范未约束这些关键词的渲染 | ✗ **缺失** |
| §4.17 Signoffs & Placekeeping | 默认**右边距**留白，初始线/Initials/CV | 执行记录区在**步骤下方**（text/pass_fail/measurement 三种盒子） | ⚠ **位置不符**：PPA 习惯右边距，Smart SOP 居下。功能等价但视觉布局完全不同 |
| §4.18 Hold Points | "HOLD POINT" 大写标签，可加前缀（如 "QC HOLD POINT"），含签名+日期 | `hold-point` 块"◈ HOLD POINT 检查点"红色双框，自带签名+日期 | ✓ 实现完整，但 ⚠ **缺少类型前缀**（固定标签，无法表达 QC / Eng Hold Point 等子类） |
| §4.19 Commitment Referencing | step 级唯一标识引用 `[PER 257317]` | 规范未提及 | ✗ **缺失** |
| §4.20 Emphasis | Action Verb / Component Position / Notes 等使用不同 emphasis；不用 italics / shading / highlight / quotes | 规范未强制约束（依赖 WangEditor 用户手填） | ✗ **未约束**：渲染层不保证 |
| §4.24 Tables | 跨页表头重绘；超宽缩放；表注用 *字母* 不用数字 | LongTable + 表头重绘 ✓；嵌套表格降级为缩进列表 | ✓ 基本符合 |
| §4.27 Numerals & Tolerances | 0-9 拼写；公差用 `400 psig (392 to 408 psig)` 而非 `±2%`；上标用 `E` 不用 `×10^x` | 规范未约束 | ✗ **未约束** |

---

## 二、按"符合度"分组汇总

### A. 完全符合（≈ 5 项）
- Header 内容元素
- 字体选型（英文部分）
- 边距数值
- 表格跨页表头重绘
- 签名栏（封面三栏）

### B. 部分符合 / 偏差但可辩护（≈ 6 项）
- 纸型 A4 vs Letter（本地化合理）
- 行距 1.5× vs 单倍（不压缩，可接受）
- 章节标题字号梯度（与 PPA 未明示，自洽即可）
- Hold Point（缺前缀）
- TOC 续页标记
- Step 跨页续行措辞

### C. 不符合 / 重大缺失（≈ 9 项 — 这是必须正视的差距）
1. **页码统计口径** 反向（T 不含封面）
2. **缺 Level of Use** 封面强制字段
3. **无强制 12 个标准 section** 结构（procedure 模板层）
4. **附件不进 PDF 主体**（数据库有 `tb_procedure_attachment`，但 PDF 规范未渲染）
5. **Notes / Cautions / Warnings 三合一为单一 warning-block**
6. **Conditional Term emphasis 未实现**（IF / THEN / WHEN 不强调）
7. **Action Verb emphasis 未强制**
8. **Signoff 位置** 在步骤下方而非右边距
9. **Commitment 引用 / 公差写法 / 数字规则** 等微观格式未约束

---

## 三、整体结论

> **当前 PDF 规范覆盖了"标准 procedure"的物理外观骨架（封面 + TOC + 修订记录 + 内容页 + header/footer + 字体 + 表格 / 图片处理），但在以下三个维度系统性偏离 PPA AP-907-005：**
>
> **1. 结构层（最严重）**：没有强制 PPA 12 个标准 section（Purpose / Scope / Instructions / ...）的模板；附件作为程序末尾的标准 section 也未渲染到 PDF。Smart SOP 当前是"自由章节树 + 富文本"模型，**用户可以写出 PPA 不允许的程序结构**。
>
> **2. 语义层**：警示分级（Note / Caution / Warning 三类）合并为单一 `warning-block`，丢失了 PPA 对"信息 / 设备风险 / 人身风险"的递进语义；Hold Point 无类型前缀；Conditional Term 与 Action Verb 的 emphasis 协议未在渲染管线中固定。
>
> **3. 微观格式层**：页码 P/T 中 T 的统计口径反向；签字位置（右边距 vs 步骤下方）布局完全不同；封面缺 Level of Use。

**符合度自评：约 50%–60%**。
满足"看起来像一份 procedure"的视觉门槛，但**不能直接作为 PPA AP-907-005 合规交付物**用于核电、DOE 或同等安全监管场景。

---

## 四、若要达到 PPA 合规，须做的改动（优先级排序）

按"影响合规判定的严重程度 × 改动成本"排序，供后续 spec 修订参考：

### P0（合规必须）
1. **Procedure 模板**：在 `tb_procedure` 增加 `procedure_type` 字段（Testing / Maintenance / Operating / Admin），新增"标准 section 模板"机制，在创建 procedure 时自动产出 PPA Table 1 要求的 R 类章节，渲染时按 PPA 顺序强制排序。涉及 [docs/data-model.md](docs/data-model.md) + [docs/pdf-rendering.md](docs/pdf-rendering.md) §6.2。
2. **封面**：增加 `level_of_use`（Reference Use / Continuous Use / Information Use）。改 [docs/pdf-rendering.md:43-53](docs/pdf-rendering.md:43)。
3. **Notes / Cautions / Warnings 三类块**：扩展 `warning-block` 为三种 class（`note-block` / `caution-block` / `warning-block`），各自独立视觉样式 + 顺序约束（Note→Caution→Warning）。改 [docs/pdf-rendering.md:265-291](docs/pdf-rendering.md:265)。
4. **附件渲染入 PDF**：把 `tb_procedure_attachment` 作为最后一节渲染到 PDF（至少元数据 + 独立编号 "Page 1 of N"），文件本身另发链接。新增 [docs/pdf-rendering.md](docs/pdf-rendering.md) §15。
5. **页码统计**：T 改为含封面/TOC/修订页，与 PPA §4.6 step 3 对齐。改 [docs/pdf-rendering.md:178](docs/pdf-rendering.md:178)。

### P1（强烈建议）
6. **Step 多级子步**（a / (1) / (a)）：当前 step 单层不够；至少把 step.input_schema 扩展为 substeps，或允许 step 下挂子 step。data-model 改动较大。
7. **Conditional Term 自动 emphasis**：渲染管线扫描 `IF` / `WHEN` / `THEN` / `AND` / `OR` 等关键词自动加粗大写（或在 WangEditor 提供按钮）。
8. **TOC 续页加 "(continued)"**。改 [docs/pdf-rendering.md:111](docs/pdf-rendering.md:111)。
9. **Hold Point 类型前缀**：`hold-point` 块支持 `data-type` 属性（QC / Eng / Safety）渲染前缀。改 [docs/pdf-rendering.md:292-314](docs/pdf-rendering.md:292)。
10. **Signoff 改右边距渲染**（或至少作为可选布局）。改 [docs/pdf-rendering.md:201-247](docs/pdf-rendering.md:201)。

### P2（细节合规）
11. Commitment 引用语法 `[PER xxx]` 标记 + 渲染。
12. Numeral / Tolerance / Symbol 规则在编辑器/渲染器加 lint 提示。
13. Action Verb 列表（PPA 附件 1）作为受控词表，编辑器联想。

---

## 五、验证方式

1. 通读 [docs/pdf-rendering.md](docs/pdf-rendering.md) 全文，对照本文档第一节表格逐行确认。
2. 通读 [docs/data-model.md](docs/data-model.md) §3.3–§3.6（tb_procedure / chapter / step / attachment），确认结构是否能承载 PPA 标准 section。
3. 阅读 PDF 手册关键章节：§4.5, §4.6, §4.11, §4.12, §4.13.1, §4.13.13, §4.15, §4.17 — 这八节是合规底线。
4. （实现完成后）生成一份典型 procedure 的 PDF，与 PPA 附图 10 (Sample Cover Page) / 图 11 (Sample TOC) / 图 28 (Notes/Cautions/Warnings) / 图 36 (Hold Point) 视觉比对。

## 关键引用

- PPA 手册原文：`D:\project devleoment\Claude code projects\smart sop\smart sop\smart sop\docs\reference doc/PPA Procedure Writer's Manual.pdf` (68 页)
- 项目 PDF 规范：[docs/pdf-rendering.md](docs/pdf-rendering.md)
- 项目数据模型：[docs/data-model.md](docs/data-model.md)
- 后端实现占位：[backend/app/services/pdf/](backend/app/services/pdf/)（空）
- 字体目录：[backend/app/assets/fonts/](backend/app/assets/fonts/)（空）
