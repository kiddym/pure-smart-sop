# 纯净 SOP 模块剥离 — 设计文档

- 日期：2026-06-11
- 范围：在 `SmartSOP-pure` 拷贝中，原地删除全部非 SOP（CMMS）模块，得到一个仅含程序管理（SOP）能力、可编译可启动可测试的纯净系统。
- 方式：原地删除（保留 git 历史，可回滚）。
- 深度：彻底清理（代码 + alembic 迁移 + 测试 + 前端 i18n/导航 + 种子 + 依赖 + 文档/CI）。

## 1. 背景与目标

本仓库由完整的 Smart CMMS 系统拷贝而来，包含 SOP（程序管理）与大量 CMMS 模块（设备、工单、库存、采购、维护、计量、分析、计费等）。目标是剥离出**纯净 SOP 模块**：

- 后端 `pytest` 全绿；
- `alembic upgrade head` 成功，仅创建 SOP 相关表；
- 前端 `build` 与单测通过；
- 应用可启动并跑通 SOP 全流程（登录 → 程序库 → Word 导入/解析 → 编辑器 → 版本审批发布 → 通知/审计）。

### 关键命名澄清（务必区分）

代码库里有两个"asset"概念，**完全不同**：

- `app/models/asset.py` → `ProcedureAsset` / `ProcedureAssetReference`，表 `tb_procedure_asset`：**SOP 文档的图片二进制资源存储**（Word 导入抽图、编辑器内嵌图、按公司 sha256 去重）。→ **SOP 核心，保留**。
- `app/models/maintenance_asset.py` → `Asset` / `AssetTeam` / `AssetUser`，表 `tb_asset`：**CMMS 设备资产**。→ **删除**。

## 2. 模块边界

### 2.1 保留（KEEP）

**SOP 核心**
- routers：`procedures`、`procedure_groups`、`folders`、`nodes`、`fields`、`field_configurations`、`heading_rules`、`parse`、`batch_imports`、`attachments`
- models：`procedure`、`node`、`field`(ProcedureField)、`folder`(+FolderSequence)、`heading_rule`、`heading_learning_event`、`numbering_profile`、`sequence`、`source_docx`、`batch`、`attachment`、`procedure_asset`（由 `asset.py` 重命名而来）、`settings`(ProcedureSettings)、`form_field_config` 除外（见删除项）
- services：`procedure_service`、`node_service`、`node_numbering`、`node_tree`、`folder_service`、`field_service`、`field_validation`、`heading_rule_service`、`heading_learning_service`、`numbering_profile_service`、`sequence_service`、`sequence_generator`、`parse_service`、`batch_*`(parse/review/apply/import/media)、`source_docx_service`、`attachment_service`、`attachment_hooks`、`upload_service`、`version_flow_service`、`version_service`、`import_service`(仅 SOP 用部分，待核)、`procedure_asset_service`（由 `asset_service.py` 重命名）、`layer_walk`、`optimistic_lock`、`_invariants`、`pdf/` 包
- schemas：对应以上各项

**配套（用户确认保留）**
- 通知：routers `notifications`、`notification_preferences`；models `notification`(+NotificationArm)、`notification_preference`、`push_token`；service `notification_service`（切除工单专用逻辑，见 §4）、`notification_preference_service`
- 审计：router `audit_logs`；models `audit`(FolderAuditLog/ProcedureAuditLog)；service `audit_service`

**基础设施**
- 认证/账号：`auth`、`users`、`roles`、`teams`、`permissions`；models `user`、`role`、`team`(+TeamUser)、`password_reset_token`、`user_invitation`、`verification_token`、`super_account_relation`；services `auth_service`、`user_service`、`role_service`、`team_service`、`invitation_service`、`password_reset_service`、`email_verification_service`
- 公司/平台/设置：`company`、`company_settings`、`platform`、`settings`；models `company`、`company_settings`；services 对应项、`settings_service`、`company_service`、`company_settings_service`
- 邮件：models `email_outbox`；services `email_outbox_service`；`app/email/`
- 计费门控（最小保留）：`billing/catalog.py` 仅保留 `Feature.sop`（procedures.py 用 `require_feature(Feature.sop)`），裁剪其余枚举；删除 `routers/billing.py`、`billing_service`、`model billing_event`、前端 billing 视图
- 中间件：`tenant_middleware`、`middleware`(RequestId)、`config`、`db`、`logging_config`、`seed`（无污染）

### 2.2 删除（DELETE）

- **设备/位置**：maintenance_asset、asset_category、asset_downtime、asset_status、location(+LocationTeam/User)、floor_plan、deprecation
- **库存/采购/往来**：part(+5 关联)、part_category、part_consumption、multi_part(+item)、purchase_order(+line/activity/category)、vendor(+3 关联)、customer(+3 关联)
- **工单/维护/计量**：work_order(+activity/assignee/team/labor/additional_cost/category/step_result)、request(+activity/status)、preventive_maintenance(+pm_activity/assignee/team/frequency)、meter(+reading/trigger/category/comparator)
- **字典**：cost_category、currency、time_category
- **其他业务**：analytics（router + `services/analytics/` 包）、workflow（workflow_engine/workflow_service，驱动工单/请求流）、billing 视图、CMMS 的 CSV 导入导出（`routers/imports.py`、`routers/exports.py`）
- **通用自定义字段（用户确认删除）**：删除 `routers/custom_fields` + `custom_field_def`（目标实体全为 CMMS）与 `routers/field_configurations` 中的 `form_field_config`（仅 REQUEST/WORK_ORDER）。
  - 注意区分：SOP 原生字段系统 = `routers/fields`(ProcedureField) + `routers/heading_rules`，**保留**；被删的是面向 CMMS 实体的通用 custom_field / form_field_config。`field_configurations` router 若同时承载 SOP 与 CMMS 表单配置，需拆分——保留 SOP 部分、删除 work_order/request 部分（实现时核对该 router 内容）。

> 待实现时逐一核对 `import_service.py`、`routers/imports.py`/`exports.py` 的真实归属：SOP 的 Word 批量导入走 `parse_service` + `batch_*`；CSV 实体导入导出属 CMMS，删除。前端 `admin-imports`/`admin-files` 视图需确认是 SOP 批量审阅入口还是 CMMS CSV 入口后再决定去留。

## 3. 架构（剥离后）

剥离后系统保持原分层：FastAPI router → service → SQLAlchemy model，多租户由 `tenant_middleware` 统一注入 company 上下文（fail-closed）。SOP 数据主链：

```
Folder (tb_folder, 自引用树) ──< Procedure (tb_procedure)
                                     ├──< ProcedureNode (tb_procedure_node, FK procedure)
                                     ├──< ProcedureField (tb_procedure_field)
                                     ├──< ProcedureSourceDocx
                                     └──< ProcedureAssetReference >── ProcedureAsset (tb_procedure_asset, 图片去重)
Attachment (多态, entity_type 仅 'procedure')
通知 / 审计 / 编号(sequence,numbering_profile) / 标题规则(heading_rule + learning)
```

SOP 模型对 CMMS 模块**无外键依赖**（已核实），删除是可行的；耦合只存在于少数"保留但被污染"的基础设施文件（见 §4）。

## 4. 解耦改动点（保留文件中的污染切除）

| 文件 | 改动 |
|---|---|
| `app/models/asset.py` | 重命名为 `app/models/procedure_asset.py`（与 CMMS 彻底脱钩） |
| `app/services/asset_service.py` | 重命名为 `procedure_asset_service.py`，import 改 `app.models.procedure_asset` |
| `app/services/version_flow_service.py` | 第 18 行 import 改为 `from app.models.procedure_asset import ProcedureAssetReference` |
| `app/services/batch_media_service.py` | 更新注释/引用指向 procedure_asset |
| `app/services/notification_service.py` | 删除 `resolve_wo_recipients` / `on_wo_created` / `on_wo_status_changed` / `on_wo_auto_generated`（约 104-219 行）及 `from app.models.work_order import ...`；保留 SOP/通用通知能力 |
| `app/services/attachment_entities.py` | `ENTITY_REGISTRY` 仅保留 `"procedure"`，移除 asset/location/part/work_order/request/work_order_step_result 及对应 import |
| `app/models/__init__.py` | 删除全部被删模型的 import 与 `__all__` 条目；`asset` import 改为 `procedure_asset` |
| `app/main.py` | 删除被删 router 的 import（约 24-73 行相应项）与 `include_router` 调用（约 140-189 行相应项） |
| `app/billing/catalog.py` | `Feature` 枚举仅留 `sop`，移除 pm/meters/purchasing/analytics 等 |
| `app/tasks/` | 删除 `asset_gc.py`、`pm_generate.py`、`due_reminder.py`；保留 `batch_parse`、`email_dispatch`、`cleanup_attachments`、`cleanup_uploads`、`sweep_source_docx` |
| 前端 `src/components/AppSidebar.vue` | 删除维护/资产/库存/往来单位/分析菜单组（约 152-195 行）；移除 `useBillingStore` 门控逻辑；保留 SOP 组 + 管理组 |
| 前端 `src/router/routes.ts` | 删除 CMMS 路由（约 217-337 行）及 `config-work-order` 路由（约 130-140 行）与相关 redirect |
| 前端 `views/admin/config/` | 删除 `WorkOrderConfigView.vue`、`RequestConfigView.vue`、`CustomFieldsConfigView.vue`；`ConfigConsoleView` 移除对应入口卡片 |
| 前端 `views/settings/WorkflowsView.vue` | 随 workflow 删除（依赖 workOrderCategories） |
| 前端 `src/store/billing.ts` | 删除（或裁剪为无门控空实现，优先删除） |

## 5. 数据库迁移：压缩为单一 SOP 基线

现有 59 个 alembic 迁移链式串联，CMMS 表被后续 20+ 迁移以外键/回填引用，无法逐个安全删除。采用**基线压缩**：

1. 删除 `backend/alembic/versions/` 下全部现有迁移文件。
2. 在干净的本地库上由仅含 SOP 模型的 `Base.metadata` 生成单一基线迁移 `xxxx_sop_baseline.py`（`alembic revision --autogenerate`），人工校对：确保只建 SOP 相关表（tb_folder、tb_procedure、tb_procedure_node、tb_procedure_field、tb_procedure_asset(+reference)、tb_heading_style_rule、tb_heading_learning_event、tb_numbering_profile、tb_sequence、tb_source_docx、tb_batch_import*、tb_attachment、tb_notification(+arm/preference)、tb_audit_log、tb_company、tb_company_settings、tb_user、tb_role、tb_team(+user)、tb_email_outbox、tb_*_token、tb_super_account_relation、tb_push_token、tb_procedure_settings 等），不含任何 CMMS 表。
3. `alembic downgrade base && alembic upgrade head` 验证可逆且与 `create_all` 一致（可用模型 metadata diff 校验无残漂移）。

> 前提：该纯净拷贝无需保留生产数据，可放心重建基线。

## 6. 测试与依赖清理

- **后端 tests**：删除 assets/work_order/request/pm/meter/part/vendor/customer/purchase_order/analytics/workflow/billing 相关测试（约 80+ 文件）、`test_permissions_phase1a..3c`、`test_phase*_cross_tenant_e2e`；审查 `conftest.py` 的 Factory，移除被删实体的构造方法。保留 SOP/导入/解析/PDF/附件/通知/审计/auth/security 测试。
- **前端 tests**：删除被删模块的 `.spec.ts`（约 100+），保留 SOP 编辑/导入/通知/权限相关。
- **依赖**：后端移除 `stripe`；保留 `reportlab`/`python-docx`/`lxml`/`PyYAML`/`Pillow`/`APScheduler`（均 SOP 用）。前端核对 `echarts`/`vue-echarts` 是否仅 analytics 用，是则删除。
- **i18n**：删除 zh-CN locale 中 maintenance/inventory/assets/locations/analytics/billing 等命名空间，保留 auth/account/common/procedures/notifications/audit 等。
- **文档/CI**：核对 `docs/` 与 README，删除/更新被删模块章节；`.github/workflows` 通用 lint/test 一般无需改动，仅核对路径过滤。

## 7. 验收标准

1. `cd backend && alembic upgrade head` 成功，DB 中无任何 CMMS 表。
2. `cd backend && pytest` 全绿。
3. `cd frontend && npm run build` 成功，`npm run test:unit` 全绿。
4. 应用启动后：登录 → 程序库 → 新建/Word 导入程序 → 编辑器（含图片）→ 提交审批 → 发布 → 通知与审计可见；侧边栏只剩 SOP + 管理两组；无 404/控制台报错指向被删模块。
5. 全仓 `grep` 无对被删模块符号的悬挂 import（work_order/asset(maintenance)/part/meter/request/pm/vendor/customer/purchase_order/analytics/workflow/billing/custom_field/form_field_config）。

## 8. 实施顺序（建议）

1. 后端模型层：重命名 `asset.py→procedure_asset.py`，清 `models/__init__.py`，删除 CMMS model 文件。
2. 后端 service/router：删除 CMMS 文件，切除 §4 污染点，清 `main.py`。
3. 迁移基线压缩（§5），跑通 `upgrade head`。
4. 后端测试清理 + `pytest` 绿。
5. 前端：删 views/components/api/store，清 `routes.ts`/`AppSidebar`/i18n，切除污染。
6. 前端 `build` + 单测绿。
7. 依赖/文档/CI 清理。
8. 端到端冒烟（§7.4）。

每个阶段结束提交一次，便于回滚与审阅。
