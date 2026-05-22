# 下一步任务提示词 —— Phase 6 后端：Word 导入解析器

> 用途：在新会话中粘贴此提示词即可按既定方法论启动 Phase 6 后端。状态权威以 `docs/development-plan.md` §7 工时记录为准。

## 当前状态（2026-05-22）
- M1 / M2 / M3 全栈达成；**M4 Phase 7 后端已完成**（`version_flow_service` + 245 测试 + 评审修复）。
- 剩余 M4：**① Phase 6 后端（本任务）② M4 前端整段**（Phase 6 五步向导 + Phase 7 版本管理 UI）。
- `backend/app/parser/`（`strategies/` `utils/` `validators/`）目前为空骨架，待填充。

## 提示词（可直接粘贴）

```
请用 superpower 方法论（手动红/绿 TDD + 子代理独立评审 + 系统化调试，全部用内置工具，
插件未装）执行 Phase 6 后端：Word 导入解析器。按里程碑自动推进、仅在里程碑处停下汇报、
受阻才打断；后端先行（前端整段后补）；所有回复用中文；决策不臆测，落 docs/feature-clarifications.md。

开工前先通读并锁定解析架构（不要直接写码）：
- docs/reference doc/dpms-v2-0-word-100-sop-serialized-star.md（DPMS 原解析器序列化参考，移植蓝本）
- docs/feature-clarifications.md §25（Word 解析全套：§25.2 图片抽取 / §25.3 标题 3 级 /
  §25.4 正文起点判定 first_styled_heading / §25.5 smart 置信度分级 / §25.7 空树）、§19（章节模型：
  每个非 heading 顶层块→独立 content 子节点，不再汇入 chapter.rich_content）、§53（独立 scheduler 进程）、
  Q190/Q191/Q193/Q197/Q199/Q200/Q207/Q208/Q214-216/Q331/Q333
- docs/api-specification.md 的 /uploads、/parse/methods、/parse、/procedures/import、/procedures/{id}/assets
- docs/word-parser-solution.md（如存在的方案细化）

Phase 6 后端任务清单（dev-plan §3 Phase 6）：
1. 移植 document_parser 完整包到 app/parser/，按 §19 重构：非 heading 顶层块→独立 content 子节点。
2. 正文起点判定（§25.4）：first_styled_heading（styles.xml 反查 4 级：标准名/中文同义词/outlineLvl/
   basedOn 上溯，且 ≥ toc_field_end）→ TOC field end → 启发式首标题 → 跳封面；删旧「最后 section break」。
3. 标题最多 3 级（§25.3，H4-6/更深压缩为 L3）；编号引擎 3 级（复用 numbering_service 思路）。
4. smart 模式置信度分级（§25.5）：HIGH 免确认 / MEDIUM·LOW 标 mark_status='review'；编号分级字典 +
   误报抑制 + 等字号自适应；返回 detected_patterns[]；两层词典 heading_synonyms.yaml + heading_style_map。
5. 图片抽到 tmp/uploads/{token}/media/（§25.2）；import 时按 sha256 去重提升为 tb_procedure_asset +
   写 tb_procedure_asset_reference；rich_content <img src> 改 asset URL；EMF/WMF 转 PNG；单图 ≤10MB。
6. 端点：POST /uploads（→ upload_token）、GET /parse/methods、POST /parse（{upload_token, parse_mode}）、
   POST /procedures/import；FastAPI UploadFile 适配、30s 超时、50MB 上限、MIME 双校验。
7. 空树检测 → PARSE_NO_HEADINGS（仅 standard 或 smart 启发式也零命中时；零样式文档 smart 应产 review 候选）。
8. 编辑器图片直传端点 POST /procedures/{id}/assets（multipart，sha256 去重，返 {asset_id,url,width,height}；
   EMF/WMF 转 PNG；>10MB → IMAGE_TOO_LARGE）—— M3 前端 WangEditor 已为此预留（本期排除了图片菜单）。
9. 独立 scheduler 进程 + 临时上传清理任务（每 1h 扫 tmp/uploads，24h 超期清；CLI python -m app.tasks.<name> --once，§53）；
   asset GC（ref_count=0 ≥24h，行锁重核，行+文件同删，每日）。
10. /chapters/{id}/convert-to-content 已返 410（M3 已做，复核即可）。

遵守既有后端约定（见 memory）：
- 双方言（MySQL 生产 / SQLite 测试，StaticPool function-scoped）；MySQL-only 生成列只在迁移里；service 层 check-then-act。
- service 只 flush 不 commit，router 提交；错误用 app/errors.py 助手（信封 {detail:{code,message,field?}}）。
- ruff（extend-exclude 仅 alembic/versions，env.py 仍 lint）+ mypy --strict（app/，tests/ 与 alembic/versions 排除）+ ruff format。
- 工具经 backend/.venv/Scripts/python.exe 调用（-m ruff / -m mypy / -m pytest）。
- 测试用 conftest Factory + RequestMeta META 常量；集成测试需 seed 的用 run_seed(db)（client 与 db 共享 engine）。
- LibreOffice 依赖（EMF/WMF→PNG）：若环境无 soffice，须优雅降级 + 测试可跳过/打桩，不得让套件失败。
- Q-number 全局递增，分配前先 grep docs/feature-clarifications.md。

完成后跑全绿门禁（ruff+format+mypy+pytest）→ 子代理独立评审 → 修复 → 更新 dev-plan 勾选/工时 + 记忆 →
中文汇报 Phase 6 后端检查点，并提示 M4 前端整段为最后一块。
```

## 之后（M4 前端整段，Phase 6 后端完成后）
Phase 6 五步导入向导（Element Plus Steps；上传三档预警 20/40/50MB；standard/smart；校验报告；
树审查 review 黄标 +「重置为初始解析」；表单 name+folder_id）+ sessionStorage（key=procedure_import_wizard_v1，
24h 超期）+ beforeRouteLeave 拦截；**Phase 7 版本管理 UI**（顶栏升级/丢弃 DRAFT/复制为新程序 —— 替换 M3
EditorTopBar/版本历史 tab 的 Phase 7 占位；版本历史时间线 + 回退/废弃/恢复/查看/删除行内按钮 + reason 弹框；
程序详情 version_update_notes textarea；版本列表面板 GET /procedure-groups/{group_id}/versions）。
```
```
