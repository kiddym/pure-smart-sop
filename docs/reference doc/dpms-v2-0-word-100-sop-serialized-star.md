# DPMS V2.0 Word 解析代码独立评估与重构建议

## Context（背景）

用户正在 `smart sop` 项目中规划 Word→SOP 结构化导入功能，希望独立评估参考项目 **DPMS V2.0**（路径：`D:\project devleoment\Huawei\DPMS_V2.0`）的 Word 解析代码，回答两个问题：

1. **是否能够 100% 提取一个标准 SOP 的所有章节和内容**（文字、图片、表格）？
2. 如果不能，**应该如何重构**？

本文档基于对 1700+ 行解析代码的逐行审计得出结论，不包含任何执行步骤——它是一份**评估报告 + 重构建议**，供 smart sop 项目实现自身解析器时参考。

---

## 一、被评估代码清单

| 文件 | 行数 | 角色 |
|---|---|---|
| `backend/procedure/document_parser/parser.py` | 481 | v1 入口：5 种策略（Auto/Style/Numbering/TitleGuided/ContentBlock） |
| `backend/procedure/document_parser/strategies/smart_parser.py` | 192 | v2 推荐：多信号启发式 |
| `backend/procedure/document_parser/strategies/standard_parser.py` | 154 | v2 严格：仅依赖 Heading 样式 |
| `backend/procedure/document_parser/utils/xml_traversal.py` | 258 | 底层 XML 遍历 / 图片 / 表格抽取 |
| `backend/procedure/document_parser/utils/heading_detector.py` | 263 | 6 信号加权评分 |
| `backend/procedure/document_parser/validators/template_validator.py` | 337 | 8 条模板校验规则（H001–T002） |
| `backend/procedure/views/parse.py` | 217 | REST 入口 `/procedure/parse/` |

调用链：`POST /procedure/parse/` → `parse_document_v2(file, mode)` → `Standard|SmartParser.parse()` → 返回章节树 → `POST /procedure/import/` → 写入 `ProcedureChapter.rich_content`（单个 TEXT 字段）。

---

## 二、核心结论：**不能 100% 提取**

> **明确判断：当前实现无法 100% 提取一个标准 SOP 的全部章节与内容。**
> SmartParser 在常见场景下可达 **约 70%–85%** 覆盖率；StandardParser 在模板严格的场景下能达到 90%+ 章节识别，但**内容保真度仍有显著漏洞**。

### 能可靠提取的部分 ✅

- 段落纯文本
- 标题层级（v2 双策略 + 多信号评分覆盖中文/英文/编号）
- **段内内联图片**（`<w:drawing>` + 现代 DrawingML，少量 `<w:pict>` 兼容）
- 顶层原生 Word 表格（`<w:gridSpan>` 列合并、单元格文本）
- 元数据（标题、作者、章节数、图片/表格计数）
- 封面/目录的跳过（通过 `find_body_start` + TOC 字段域检测）
- 置信度分级（HIGH ≥0.60 / MEDIUM ≥0.30 / LOW），便于人工复核

### 会丢失或严重失真的部分 ❌

| 类别 | 状态 | 证据位置 | 影响 |
|---|---|---|---|
| **浮动/锚定图片**（`<w:anchor>`） | 全部丢失 | `xml_traversal.py:123-132` 只 `findall("w:drawing")`，未区分 inline vs anchor | SOP 中流程图、印章、批注图常用 anchor |
| **同一段内多张图片** | 仅保留第 1 张 | `xml_traversal.py:135-167` 单 `return`，二张起被丢弃 | 并列示意图直接消失 |
| **表格单元格内的图片** | 全部丢失 | `xml_traversal.py:232` 用 `cell.text`，仅取文字 | SOP 表格中嵌图非常常见 |
| **嵌套表格** | 仅取顶层 cell 文本 | `iter_body_blocks` 不递归；`cell.text` 拍平 | 复杂矩阵表完全失真 |
| **跨行合并 `<w:vMerge>`** | 渲染破损 | `xml_traversal.py:230` `continue` 跳过 continue 单元格，但 restart 行 rowspan 始终=1，没有真正计算合并跨度 | HTML 表格视觉错位 |
| **页眉 / 页脚** | 全部丢失 | 仅遍历 `doc.element.body`，未访问 `headers` / `footers` parts | SOP 文件号、版本号、日期常放页眉 |
| **脚注 / 尾注** | 全部丢失 | 未读 `footnotes.xml` / `endnotes.xml` | 引用、注解丢失 |
| **文本框 `<w:txbxContent>`** | 全部丢失 | `iter_body_blocks` 仅识别 `w:p / w:tbl / w:sdt`；`template_validator` B002 仅"警告"不提取 | 流程图旁注释、印章框丢失 |
| **公式 `<m:oMath>`** | 文本被破坏 | python-docx `.text` 不返回 OMML | 工艺参数公式变乱码或空白 |
| **超链接 `<w:hyperlink>`** | 仅文本，URL 丢失 | 段落转 `<p>{text}</p>`，未处理 hyperlink runs | 引用其它文档的链接全失效 |
| **列表格式 / 编号** | 仅作为文本特征用于评分，结构丢失 | `<w:numPr>` 只参与 heading 评分，未还原 `<ol>/<ul>` | 步骤列表退化成纯文本段 |
| **粗体 / 斜体 / 颜色 / 字号** | 全部丢失 | 段落转 `<p>{text}</p>`，runs 信息扔掉 | "**警告**"、"红字注意事项"全部失格 |
| **修订/批注** | 全部丢失 | 未读 `comments.xml` / `<w:ins>` / `<w:del>` | 审阅留痕丢失 |
| **嵌入对象 OLE / 图表** | 全部丢失 | 未处理 `<w:object>` / `<c:chart>` | Excel/Visio 嵌入丢失 |
| **章节分隔符 `<w:sectPr>`** | 仅做"检测"未保留 | 仅 T002 校验告警 | 分节、页面方向信息丢失 |
| **首张内容在第一个标题之前** | 全部丢失 | smart_parser.py:82,93 `if flat_chapters:` 检查导致悬空内容被丢弃 | "目的"段落写在 Heading 之前会被吞 |
| **`w:sdt` 内的嵌套 `w:sdt`** | 仅展开 1 层 | `iter_body_blocks` 子循环非递归 | 复杂表单丢内容 |
| **`steps[]`** | 始终为空 | 解析器从未填充，但 `ProcedureChapter` 模型支持 | 步骤结构语义丢失 |

### 数据模型瓶颈 ❗

`ProcedureChapter.rich_content` 是**单个 TEXT 字段**，所有图片以 **base64 data URI** 嵌入：

- **存储膨胀**：1 张 1 MB 图片 → base64 后 ~1.36 MB → 进 MySQL TEXT 列，单 SOP 含 30 张图 → 单字段近 40 MB
- **传输放大**：API 响应携带全部 base64，前端首屏可能数十 MB
- **无法去重**、无法 CDN 缓存、无法独立鉴权
- **无法事后引用**：图片没有独立 ID / URL，无法在其他地方复用

---

## 三、被忽视/有 bug 的关键代码点

1. **`smart_parser.py:79-89`**  
   `has_inline_image` 在判定为 heading 之后又重新追加图片到当前章节，导致"段落同时含标题文本和图片"时图片会进入新章节而不是上一章节末尾——逻辑可疑且未测试。

2. **`xml_traversal.py:165-167`**  
   `return` 写在 `for blip in blips` 里——一段中有多 blip 时第二张起被丢弃。**应改为收集 list 返回**。

3. **`xml_traversal.py:224-230`**  
   `<w:vMerge val="continue">` 的逻辑是 `continue`（跳过），但起始单元格 `restart` 的 `rowspan` 硬编码 1。**没有任何代码统计垂直跨度**，最终 HTML 行结构错乱。

4. **`xml_traversal.py:112-120`**  
   SDT 子循环遍历的是 `element.iterchildren()`，但 SDT 的真实内容在 `<w:sdtContent>` 中，**当前代码会跳过 sdtContent 包装层而失败匹配**（在某些 Word 版本生成的文档中）。

5. **`parser.py` 的 5 种 v1 策略**  
   全部**仅遍历 `doc.paragraphs`**，**图片、表格 100% 丢失**；同时 `parser.py` 与 `strategies/*.py` 之间存在两套并行的章节数据模型（`ParsedChapter` dataclass vs. dict），**没有统一**。建议直接弃用 v1 策略。

6. **零单元测试**  
   `procedure/tests/` 中没有任何 `test_parser*.py`；也没有任何 sample `.docx` fixture。所有上述 bug 都**未被任何测试拦截**。

7. **零文档**  
   `parser.py` 无 module docstring，无 SOP 模板规范文档，仅 `06-程序管理模块功能说明.md` 提到流程但未规范输入格式。

---

## 四、重构建议（按优先级）

### P0｜架构层：把"解析"和"持久化"解耦

```
原始 .docx
    │
    ▼
┌──────────────────────────────────────────────┐
│  Stage 1: DocxNormalizer                     │
│  - 完整 OPC 包解压（含 media/、headers/、    │
│    footers/、footnotes/、comments/）         │
│  - 把所有图片资源提前抽出，分配 asset_id     │
│  - 输出"规范化 IR"（顺序保持的块流）         │
└──────────────────────────────────────────────┘
    │  规范化块流 [Heading|Para|Image|Table|List|…]
    ▼
┌──────────────────────────────────────────────┐
│  Stage 2: SectionStructurer                  │
│  - 仅消费 IR，做标题识别 + 层级归并          │
│  - 多策略：style / outline / numbering /     │
│    template-guided                           │
└──────────────────────────────────────────────┘
    │  ChapterTree (chapter + ordered content blocks)
    ▼
┌──────────────────────────────────────────────┐
│  Stage 3: ContentSerializer                  │
│  - 把 IR 内容块渲染成富文本（HTML/JSON-AST） │
│  - 图片用 asset_id 占位，不内联 base64       │
│  - 公式 → MathML / LaTeX 字符串              │
│  - 表格 → 结构化 JSON + 渲染时拼 HTML        │
└──────────────────────────────────────────────┘
    │
    ▼
持久化：章节表 + 资源表（assets）+ AST 字段
```

**收益**：每层可独立测试；新增内容类型（公式、文本框）只改 Normalizer；前端可懒加载图片。

### P1｜遍历层：从 `doc.paragraphs` 升级到全 OPC 遍历

- **必须使用 `lxml`**，从 `document.xml` `<w:body>` 起按 child order 流式产出块。
- 块类型至少覆盖：`paragraph / table / sdt / drawing-anchor / textbox / sectionBreak`。
- **递归展开**：`w:sdt → w:sdtContent`、`w:txbxContent`、嵌套 `w:tbl`。
- 同时遍历：`word/header*.xml`、`word/footer*.xml`、`word/footnotes.xml`、`word/comments.xml`、`word/embeddings/*`。

参考库：保留 `python-docx` 做高层 API，但底层用 `docx.oxml` 直接拿 lxml element；复杂场景可引入 `docx2python`（已处理 anchor / textbox / footnote）做兜底。

### P2｜资源层：图片/嵌入对象独立化

- 解压 `word/media/` 全部资源，按 `rId` 建立映射。
- 每张图分配 `asset_id`（uuid）、计算 sha256（去重）、存到对象存储（或 Django `FileField`）。
- 富文本中用 `<img data-asset="{asset_id}">` 占位，渲染时再签 URL。
- 同段多图、表内图、anchor 图统一走这条路径。
- 公式：通过 `<m:oMath>` 序列化为 OMML / MathML，存独立字段。

### P3｜表格层：用结构化 JSON 取代 HTML 字符串

```json
{
  "type": "table",
  "rows": 4, "cols": 5,
  "cells": [
    {"row":0,"col":0,"rowspan":1,"colspan":2,"blocks":[...]},
    ...
  ]
}
```

- `blocks` 内可放任意内容块（嵌套表、图、段落），实现**真正的递归内容**。
- 合并单元格用 `rowspan`/`colspan` 双向记录，渲染时一次性消费。
- 修正 `<w:vMerge>` 的真实跨度计算（需要双 pass：先扫描出每个 restart 列向下连续多少个 continue）。

### P4｜标题识别：保留多信号，但加"全文相对化"

当前 `heading_detector.py` 把"字号 ≥18pt"等阈值**硬编码**，而 SOP 排版各家不同。改造：

1. 第一遍扫描得到文档**字号分布**与**bold 比例**，算出阈值（如取 top-10% 字号视为标题候选）。
2. 第二遍按相对阈值评分。
3. 暴露 `level_hints` 接口，允许调用方塞入"必有章节"白名单（PPA Procedure Writer's Manual 之类 SOP 通常有固定 12 个一级标题）。

### P5｜模板校验：补充内容完整性校验

`TemplateValidator` 当前只校验 heading/样式/分节，**没有任何"内容是否完整提取"的校验**。补加：

- C001：原始 `<w:drawing>` 数 vs. 解析后 `imageCount` 一致
- C002：原始 `<w:tbl>` 数 vs. 解析后 `tableCount` 一致
- C003：原始 `<w:p>` 非空段数 vs. 解析后段落数 ≥ 95%
- C004：每个 SOP 必备一级章节都被识别（结合 hints）

任何 C 类失败应返回 `warnings`，让前端展示"内容可能有遗漏"。

### P6｜测试：建立 fixture 驱动的回归套件

`procedure/tests/` 当前 0 个解析测试。建议：

```
backend/procedure/tests/parser/
├── fixtures/
│   ├── sop_well_formed.docx          # 完美模板
│   ├── sop_no_heading_style.docx     # 仅靠加粗+编号
│   ├── sop_with_textbox.docx
│   ├── sop_with_anchor_image.docx
│   ├── sop_with_nested_table.docx
│   ├── sop_with_merged_cells.docx
│   ├── sop_with_formula.docx
│   └── sop_with_header_footer.docx
├── test_normalizer.py
├── test_structurer.py
└── test_serializer.py
```

每个 fixture **都应该有一个"期望产物 JSON"**，做 golden file 对比。

### P7｜弃用 v1 `parser.py`

5 种 v1 策略**完全不抽图片表格**，且与 v2 数据结构不一致，是技术债。建议：

- 保留 `parse_document_v2`，把 v1 入口标记 `DeprecationWarning`。
- 一个版本周期后删除 `parser.py` 中所有 `AutoParseStrategy / StyleOnly / NumberingOnly / TitleGuided / ContentBlock`，只保留 `ParsedChapter` 和 `ParseResult` 数据类供两个 parser 共用。

---

## 五、给 smart sop 项目的"借鉴清单"

如果 smart sop 准备自研解析器，**可以直接复用**的设计：

- ✅ `MultiSignalHeadingDetector` 的 6 信号加权评分思路（heading_detector.py:1-263）——但权重要参数化、阈值要相对化
- ✅ `find_body_start` 的 TOC / 封面跳过启发（xml_traversal.py:15-95）——可扩展为"分节符 + 域 + 样式"三重判断
- ✅ 置信度分级（high/medium/low）+ `markStatus="review"` 的人机协作模式（smart_parser.py:61-73）
- ✅ `TemplateValidator` 8 条规则的代码 + level + actions 三段式结构（template_validator.py）

**不要照搬**的：

- ❌ `doc.paragraphs` 单次遍历（v1 parser.py）——必丢图表
- ❌ base64 内联到 `rich_content`——数据模型崩溃前兆
- ❌ `table_to_html` 字符串拼接 + `cell.text`——表格内容会失真
- ❌ 单一 TEXT 字段存富文本——应至少拆 `content_ast` (JSON) + `assets` (FK)

---

## 六、Critical Files（如果决定原地重构 DPMS 的话）

按修改影响面排序：

1. `backend/procedure/document_parser/utils/xml_traversal.py` — 重写为完整 OPC 遍历
2. `backend/procedure/document_parser/strategies/smart_parser.py` — 拆为 Normalizer + Structurer
3. `backend/procedure/document_parser/strategies/standard_parser.py` — 同上
4. `backend/procedure/document_parser/utils/heading_detector.py` — 阈值相对化 + 可配置权重
5. `backend/procedure/document_parser/validators/template_validator.py` — 补 C001-C004 内容完整性校验
6. `backend/procedure/models/procedure_chapter.py` — 字段拆分（content_ast JSON / assets FK）
7. `backend/procedure/views/parse.py` — 响应体加 `assets[]`、`completeness[]` 字段
8. `backend/procedure/tests/parser/` — 新增 fixture + golden test 套件
9. `backend/procedure/document_parser/parser.py` — 标记 Deprecated 或删除

---

## 七、验证方式（重构后如何确认达到 100%）

1. **OPC 二进制对账**：解压原始 `.docx`，统计 `<w:drawing>` / `<w:tbl>` / `<w:p>` 数量，与解析输出对账，差异需 0。
2. **图片字节级哈希**：解压 `word/media/` 中每个图片 sha256，与 `assets` 表记录一一对应。
3. **Round-trip 渲染**：把解析结果重新渲染回 docx（或 PDF），与原始文档做版面 / 文字 diff（参考 `docs/pdf-rendering.md` 中的渲染流程）。
4. **Golden test**：8 个 fixture（参见 P6）的解析输出 JSON 与预期 JSON 完全相等。
5. **Manual review**：选 5 份真实 SOP（参考 `PPA Procedure Writer's Manual.pdf` 中的标准格式），逐节点对比。

只有以上 5 项全过，才能声称"100% 提取"。
