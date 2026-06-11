# 纯净 SOP 模块剥离 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `SmartSOP-pure` 中原地删除全部 CMMS 模块，得到仅含 SOP（程序管理）能力、可编译可启动可测试的纯净系统。

**Architecture:** 保持原 FastAPI(router→service→model) + Vue3 分层。SOP 模型对 CMMS 无外键依赖，故删除可行；耦合仅存在于少数"保留但被污染"的基础设施文件，需切除。alembic 压缩为单一 SOP 基线。

**Tech Stack:** 后端 FastAPI / SQLAlchemy / alembic / pytest；前端 Vue3 + TS / Vite / vitest。

> **本计划是删除/重构型，非新增功能**：不写红-绿测试。每个阶段以**验证门**结尾（`python -c import` 通过 / `pytest` 绿 / `npm run build` 成功 / `alembic upgrade head` 成功），作为该阶段的测试。所有删除以 `git rm` 执行，保留可回滚历史。
>
> 设计依据：`docs/superpowers/specs/2026-06-11-pure-sop-extraction-design.md`

---

## 阶段 0：分支与基线

### Task 0: 建立工作分支并记录基线

**Files:** 无（仅 git 与命令）

- [ ] **Step 1: 从 main 切出工作分支**

```bash
cd "/Users/yuming/Desktop/smart CMMS/pure sop session/SmartSOP-pure"
git checkout -b feat/pure-sop-extraction
```

- [ ] **Step 2: 记录后端基线（确认起点可跑）**

```bash
cd backend && python -c "import app.main" && echo "IMPORT OK"
```
Expected: 打印 `IMPORT OK`（若失败说明起点已坏，先停下排查）。

- [ ] **Step 3: 记录前端基线**

```bash
cd ../frontend && npm run build >/tmp/fe_baseline.log 2>&1; tail -3 /tmp/fe_baseline.log
```
Expected: build 成功（记录现状，作为后续对照）。

- [ ] **Step 4: 提交空标记（可选，便于回滚锚点）**

```bash
cd .. && git commit --allow-empty -m "chore: start pure-sop extraction"
```

---

## 阶段 1：后端模型层

### Task 1: 重命名 ProcedureAsset 模型文件，与 CMMS 脱钩

**Files:**
- Rename: `backend/app/models/asset.py` → `backend/app/models/procedure_asset.py`
- Modify: `backend/app/services/asset_service.py`（import 源）
- Modify: `backend/app/services/version_flow_service.py:18`
- Modify: `backend/app/services/import_service.py`（import asset_service 处）

- [ ] **Step 1: git mv 模型文件**

```bash
cd "/Users/yuming/Desktop/smart CMMS/pure sop session/SmartSOP-pure"
git mv backend/app/models/asset.py backend/app/models/procedure_asset.py
```

- [ ] **Step 2: 重命名 service 文件**

```bash
git mv backend/app/services/asset_service.py backend/app/services/procedure_asset_service.py
```

- [ ] **Step 3: 修正 procedure_asset_service.py 内的 import**

把 `from app.models.asset import ...` 改为 `from app.models.procedure_asset import ProcedureAsset, ProcedureAssetReference`。

```bash
grep -rn "from app.models.asset import\|models\.asset\b" backend/app/services/procedure_asset_service.py
```
对每一处把 `app.models.asset` 替换为 `app.models.procedure_asset`。

- [ ] **Step 4: 修正所有引用 asset_service 与 models.asset 的保留文件**

```bash
grep -rln "import asset_service\|asset_service\.\|from app.models.asset import\|app\.models\.asset\b" backend/app --include="*.py"
```
对每个命中文件（预期含 `version_flow_service.py`、`import_service.py`、`batch_media_service.py` 注释）：
- `from app.services import asset_service` / `import asset_service` → `procedure_asset_service`，调用处 `asset_service.` → `procedure_asset_service.`
- `from app.models.asset import ...` → `from app.models.procedure_asset import ...`

- [ ] **Step 5: 验证导入仍成立**

```bash
cd backend && python -c "import app.models.procedure_asset; import app.services.procedure_asset_service" && echo "OK"
```
Expected: `OK`

- [ ] **Step 6: 提交**

```bash
cd .. && git add -A && git commit -m "refactor(sop): rename asset.py→procedure_asset.py to decouple from CMMS"
```

### Task 2: 删除 CMMS 模型文件

**Files:**
- Delete（共 40 个，保留 `procedure_asset.py` 与 `numbering_profile.py`）

- [ ] **Step 1: 删除 CMMS model 文件**

```bash
cd "/Users/yuming/Desktop/smart CMMS/pure sop session/SmartSOP-pure"
git rm backend/app/models/maintenance_asset.py backend/app/models/asset_category.py \
  backend/app/models/asset_downtime.py backend/app/models/asset_status.py \
  backend/app/models/location.py backend/app/models/floor_plan.py backend/app/models/deprecation.py \
  backend/app/models/part.py backend/app/models/part_category.py backend/app/models/part_consumption.py \
  backend/app/models/multi_part.py backend/app/models/purchase_order.py \
  backend/app/models/purchase_order_category.py backend/app/models/purchase_order_status.py \
  backend/app/models/vendor.py backend/app/models/customer.py \
  backend/app/models/work_order.py backend/app/models/work_order_activity.py \
  backend/app/models/work_order_additional_cost.py backend/app/models/work_order_category.py \
  backend/app/models/work_order_labor.py backend/app/models/work_order_status.py \
  backend/app/models/work_order_step_result.py backend/app/models/request.py \
  backend/app/models/request_activity.py backend/app/models/request_status.py \
  backend/app/models/preventive_maintenance.py backend/app/models/pm_activity.py \
  backend/app/models/pm_frequency.py backend/app/models/meter.py backend/app/models/meter_category.py \
  backend/app/models/meter_comparator.py backend/app/models/meter_reading.py \
  backend/app/models/meter_trigger.py backend/app/models/cost_category.py \
  backend/app/models/currency.py backend/app/models/time_category.py \
  backend/app/models/billing_event.py backend/app/models/workflow.py \
  backend/app/models/custom_field_def.py backend/app/models/form_field_config.py
```

- [ ] **Step 2: 清理 `models/__init__.py`**

打开 `backend/app/models/__init__.py`：
- 把 `from app.models.asset import ProcedureAsset, ProcedureAssetReference` 改为 `from app.models.procedure_asset import ProcedureAsset, ProcedureAssetReference`
- 删除所有被删模型的 `from app.models.<x> import ...` 行（asset_category/asset_downtime/billing_event/cost_category/currency/custom_field_def/customer/deprecation/floor_plan/form_field_config/location/maintenance_asset/meter*/multi_part/part*/preventive_maintenance/pm_activity/purchase_order*/request*/time_category/vendor/work_order*/workflow）
- 同步删除 `__all__` 列表中对应的类名（Asset/AssetCategory/AssetDeprecation/AssetDowntime/AssetTeam/AssetUser/BillingEvent/CostCategory/Currency/CustomFieldDef/Customer*/FloorPlan/FormFieldConfig/Location*/Meter*/MultiPart*/Part*/PM*/PreventiveMaintenance/PurchaseOrder*/Request*/TimeCategory/Vendor*/WorkOrder*/Workflow）
- 保留：Procedure/ProcedureAsset/ProcedureAssetReference/ProcedureField/ProcedureNode/ProcedureSettings/ProcedureSourceDocx/Folder/FolderSequence/FolderAuditLog/ProcedureAuditLog/HeadingStyleRule/HeadingLearningEvent/NumberingProfile/Sequence/Attachment/BatchImport*/Notification*/NotificationPreference/PushToken/Company/CompanySettings/User/Role/Team/TeamUser/EmailOutbox/PasswordResetToken/UserInvitation/VerificationToken/SuperAccountRelation/Base

- [ ] **Step 3: 验证模型包可导入**

```bash
cd backend && python -c "import app.models" && echo "MODELS OK"
```
Expected: `MODELS OK`（若报 NameError/ImportError，按提示补删 `__init__.py` 残留条目）

- [ ] **Step 4: 提交**

```bash
cd .. && git add -A && git commit -m "feat(sop): remove CMMS model files, clean models registry"
```

---

## 阶段 2：后端服务、任务、调度

### Task 3: 删除 CMMS service 文件与 analytics 包

**Files:**
- Delete services（32 个，**保留** `import_service.py`、`numbering_profile_service.py`、`procedure_asset_service.py`）
- Delete dir: `backend/app/services/analytics/`

- [ ] **Step 1: 删除 CMMS service**

```bash
cd "/Users/yuming/Desktop/smart CMMS/pure sop session/SmartSOP-pure"
git rm backend/app/services/maintenance_asset_service.py backend/app/services/asset_category_service.py \
  backend/app/services/location_service.py backend/app/services/floor_plan_service.py \
  backend/app/services/deprecation_service.py backend/app/services/part_service.py \
  backend/app/services/part_category_service.py backend/app/services/part_consumption_service.py \
  backend/app/services/multi_part_service.py backend/app/services/purchase_order_service.py \
  backend/app/services/purchase_order_category_service.py backend/app/services/vendor_service.py \
  backend/app/services/customer_service.py backend/app/services/work_order_service.py \
  backend/app/services/work_order_category_service.py backend/app/services/work_order_cost_service.py \
  backend/app/services/work_order_labor_service.py backend/app/services/work_order_additional_cost_service.py \
  backend/app/services/work_order_execution_service.py backend/app/services/request_service.py \
  backend/app/services/pm_service.py backend/app/services/meter_service.py \
  backend/app/services/meter_category_service.py backend/app/services/meter_trigger_service.py \
  backend/app/services/cost_category_service.py backend/app/services/currency_service.py \
  backend/app/services/time_category_service.py backend/app/services/billing_service.py \
  backend/app/services/custom_field_service.py backend/app/services/form_field_config_service.py \
  backend/app/services/workflow_service.py backend/app/services/workflow_engine.py
git rm -r backend/app/services/analytics
```

- [ ] **Step 2: 切除 notification_service.py 的工单耦合**

打开 `backend/app/services/notification_service.py`：
- 删除 `from app.models.work_order import WorkOrder, WorkOrderAssignee, WorkOrderTeam`
- 删除工单专用函数：`resolve_wo_recipients`、`on_wo_created`、`on_wo_status_changed`、`on_wo_auto_generated`（约第 104-219 行；以函数定义边界为准，逐个删除整函数）
- 保留通用通知 CRUD/分发能力（create/list/mark-read 等）

验证：
```bash
cd backend && python -c "from app.services import notification_service" && echo "NS OK"
```
Expected: `NS OK`

- [ ] **Step 3: 切除 attachment_entities.py 的多实体注册**

打开 `backend/app/services/attachment_entities.py`：
- 删除对 `Asset`/`Location`/`Part`/`WorkOrder`/`WorkOrderStepResult`/`Request` 的 import
- `ENTITY_REGISTRY` 仅保留 `"procedure"` 一项

验证：
```bash
cd backend && python -c "from app.services import attachment_entities as a; assert set(a.ENTITY_REGISTRY)=={'procedure'}, a.ENTITY_REGISTRY; print('REG OK')"
```
Expected: `REG OK`

- [ ] **Step 4: 提交**

```bash
cd .. && git add -A && git commit -m "feat(sop): remove CMMS services, decouple notification/attachment"
```

### Task 4: 删除 CMMS 后台任务并清理调度注册

**Files:**
- Delete: `backend/app/tasks/asset_gc.py`、`due_reminder.py`、`pm_generate.py`
- Modify: `backend/app/tasks/scheduler.py`

- [ ] **Step 1: 查看 scheduler 注册了哪些任务**

```bash
cd "/Users/yuming/Desktop/smart CMMS/pure sop session/SmartSOP-pure"
grep -nE "asset_gc|due_reminder|pm_generate|import" backend/app/tasks/scheduler.py
```

- [ ] **Step 2: 删除任务文件**

```bash
git rm backend/app/tasks/asset_gc.py backend/app/tasks/due_reminder.py backend/app/tasks/pm_generate.py
```

- [ ] **Step 3: 从 scheduler.py 移除对应注册**

打开 `backend/app/tasks/scheduler.py`，删除 `asset_gc`/`due_reminder`/`pm_generate` 的 import 与 `add_job`（或等价）注册行。保留 `batch_parse`/`email_dispatch`/`cleanup_attachments`/`cleanup_uploads`/`sweep_source_docx`。

验证：
```bash
cd backend && python -c "from app.tasks import scheduler" && echo "SCHED OK"
```
Expected: `SCHED OK`

- [ ] **Step 4: 提交**

```bash
cd .. && git add -A && git commit -m "feat(sop): remove CMMS background tasks"
```

---

## 阶段 3：后端路由、schema、入口、计费门控

### Task 5: 删除 CMMS router 与 schema 文件

**Files:**
- Delete routers（30 个）与 schemas（19 个）

- [ ] **Step 1: 删除 CMMS routers**

```bash
cd "/Users/yuming/Desktop/smart CMMS/pure sop session/SmartSOP-pure"
git rm backend/app/routers/assets.py backend/app/routers/asset_categories.py \
  backend/app/routers/locations.py backend/app/routers/floor_plans.py backend/app/routers/deprecations.py \
  backend/app/routers/parts.py backend/app/routers/part_categories.py backend/app/routers/part_consumptions.py \
  backend/app/routers/multi_parts.py backend/app/routers/purchase_orders.py \
  backend/app/routers/purchase_order_categories.py backend/app/routers/vendors.py \
  backend/app/routers/customers.py backend/app/routers/work_orders.py \
  backend/app/routers/work_order_categories.py backend/app/routers/work_order_costs.py \
  backend/app/routers/requests.py backend/app/routers/preventive_maintenances.py \
  backend/app/routers/meters.py backend/app/routers/meter_categories.py \
  backend/app/routers/cost_categories.py backend/app/routers/currencies.py \
  backend/app/routers/time_categories.py backend/app/routers/analytics.py \
  backend/app/routers/exports.py backend/app/routers/imports.py backend/app/routers/billing.py \
  backend/app/routers/workflows.py backend/app/routers/custom_fields.py \
  backend/app/routers/field_configurations.py
```

- [ ] **Step 2: 删除 CMMS schemas**

```bash
git rm backend/app/schemas/asset.py backend/app/schemas/asset_category.py \
  backend/app/schemas/location.py backend/app/schemas/floor_plan.py backend/app/schemas/deprecation.py \
  backend/app/schemas/part.py backend/app/schemas/purchase_order.py \
  backend/app/schemas/purchase_order_category.py backend/app/schemas/partner.py \
  backend/app/schemas/work_order.py backend/app/schemas/work_order_category.py \
  backend/app/schemas/work_order_cost.py backend/app/schemas/request.py backend/app/schemas/meter.py \
  backend/app/schemas/meter_category.py backend/app/schemas/pm.py backend/app/schemas/analytics.py \
  backend/app/schemas/billing.py backend/app/schemas/custom_field.py backend/app/schemas/workflow.py
```

- [ ] **Step 3: 提交（main.py 下一任务处理，故此处尚不可 import）**

```bash
git add -A && git commit -m "feat(sop): remove CMMS routers and schemas"
```

### Task 6: 清理 main.py 路由挂载

**Files:**
- Modify: `backend/app/main.py`

- [ ] **Step 1: 删除 import 块中的被删 router**

在 `backend/app/main.py` 的 `from app.routers import (...)` 块中，删除：analytics, asset_categories, assets, cost_categories, currencies, customers, deprecations, exports, field_configurations, floor_plans, imports, locations, meter_categories, meters, multi_parts, part_categories, part_consumptions, parts, preventive_maintenances, purchase_order_categories, purchase_orders, requests, time_categories, vendors, work_order_categories, work_order_costs, work_orders, workflows, billing, custom_fields。
保留：attachments, audit_logs, auth, batch_imports, company, company_settings, fields, folders, heading_rules, nodes, notification_preferences, notifications, parse, platform, procedure_groups, procedures, roles, teams, users（及 `permissions as permissions_router`、`settings as settings_router`）。

- [ ] **Step 2: 删除 include_router 调用**

删除以下行（按符号匹配，行号会随上步变动）：
`assets, locations, work_orders, requests, preventive_maintenances, meters, meter_categories, part_categories, parts, multi_parts, part_consumptions, work_order_costs, cost_categories, time_categories, work_order_categories, vendors, customers, purchase_order_categories, purchase_orders, analytics, exports, imports, asset_categories, deprecations, floor_plans, currencies, custom_fields, billing, workflows, field_configurations` 的 `app.include_router(...)`。
保留 SOP/基础设施的 include_router。

- [ ] **Step 3: 验证应用可导入**

```bash
cd backend && python -c "import app.main" && echo "MAIN OK"
```
Expected: `MAIN OK`（若 ImportError，按提示是 main.py 残留引用或 schema/service 漏删，回到对应任务补齐）

- [ ] **Step 4: 提交**

```bash
cd .. && git add -A && git commit -m "feat(sop): prune main.py router wiring to SOP only"
```

### Task 7: 裁剪 billing 特性枚举

**Files:**
- Modify: `backend/app/billing/catalog.py`
- 可能 Modify: `backend/app/billing/` 下引用 billing_service/billing_event 的文件

- [ ] **Step 1: 查看 catalog 与 billing 目录**

```bash
cd "/Users/yuming/Desktop/smart CMMS/pure sop session/SmartSOP-pure"
ls backend/app/billing/ && grep -nE "class Feature|pm|meter|purchas|analytic|sop" backend/app/billing/catalog.py
```

- [ ] **Step 2: 裁剪 Feature 枚举仅留 sop**

编辑 `catalog.py`：`Feature` 枚举仅保留 `sop`，删除 pm/meters/purchasing/analytics 等成员及其在档位映射中的条目。删除任何 import 自被删 `billing_service`/`billing_event` 的语句。

- [ ] **Step 3: 验证**

```bash
cd backend && python -c "from app.billing.catalog import Feature; print([f.name for f in Feature])"
```
Expected: 仅含 `sop`

- [ ] **Step 4: 提交**

```bash
cd .. && git add -A && git commit -m "feat(sop): trim billing Feature enum to sop only"
```

### Task 8: 后端悬挂引用全量扫描与修复

**Files:** 全后端

- [ ] **Step 1: 扫描对被删模块符号的残留引用**

```bash
cd "/Users/yuming/Desktop/smart CMMS/pure sop session/SmartSOP-pure/backend"
grep -rnE "from app\.(models|services|schemas|routers)\.(maintenance_asset|asset_category|asset_downtime|asset_status|location|floor_plan|deprecation|part|part_category|part_consumption|multi_part|purchase_order|vendor|customer|work_order|request|preventive_maintenance|pm_activity|meter|cost_category|currency|time_category|billing|workflow|custom_field|form_field_config)" app --include="*.py" | grep -v "procedure_asset"
```
Expected: 无输出（有则逐个清理）。

- [ ] **Step 2: 终极导入验证**

```bash
python -c "import app.main; import app.models; import app.tasks.scheduler" && echo "ALL IMPORTS OK"
```
Expected: `ALL IMPORTS OK`

- [ ] **Step 3: 提交（若有修复）**

```bash
cd .. && git add -A && git commit -m "fix(sop): clean dangling backend references" || echo "nothing to commit"
```

---

## 阶段 4：数据库迁移基线压缩

### Task 9: 重建单一 SOP 基线迁移

**Files:**
- Delete: `backend/alembic/versions/*.py`（58 个）
- Create: `backend/alembic/versions/<rev>_sop_baseline.py`（autogenerate）

- [ ] **Step 1: 删除全部旧迁移**

```bash
cd "/Users/yuming/Desktop/smart CMMS/pure sop session/SmartSOP-pure"
git rm backend/alembic/versions/*.py
```

- [ ] **Step 2: 准备空库（用临时 SQLite 或配置的开发库）**

确认 `backend/alembic/env.py` 的 `target_metadata` 指向 `app.models.Base.metadata`：
```bash
grep -n "target_metadata" backend/alembic/env.py
```
若指向被删模块需修正为 `from app.models import Base; target_metadata = Base.metadata`。

- [ ] **Step 3: 在空库上 autogenerate 基线**

```bash
cd backend && alembic revision --autogenerate -m "sop baseline"
```
（确保连接的是一个**空**数据库；若用 MySQL，先 `DROP DATABASE`+`CREATE DATABASE` 重建空库再执行。）

- [ ] **Step 4: 人工校对生成的基线**

打开新生成的 `backend/alembic/versions/<rev>_sop_baseline.py`，确认：
- `down_revision = None`
- 仅 `create_table` SOP 相关表：tb_folder, tb_folder_sequence, tb_procedure, tb_procedure_node, tb_procedure_field, tb_procedure_asset, tb_procedure_asset_reference, tb_procedure_settings, tb_source_docx, tb_heading_style_rule, tb_heading_learning_event, tb_numbering_profile, tb_sequence, tb_batch_import_job, tb_batch_import_item, tb_attachment, tb_notification, tb_notification_arm, tb_notification_preference, tb_push_token, tb_audit_log（程序/文件夹）, tb_company, tb_company_settings, tb_user, tb_role, tb_team, tb_team_user, tb_email_outbox, tb_password_reset_token, tb_user_invitation, tb_verification_token, tb_super_account_relation 等
- **无任何** tb_asset/tb_work_order/tb_part/tb_meter/tb_request/tb_pm*/tb_vendor/tb_customer/tb_purchase_order*/tb_billing*/tb_custom_field*/tb_form_field*/tb_location/tb_floor_plan/tb_cost_category/tb_currency/tb_time_category/tb_workflow

发现多余表 → 回到阶段 1-3 检查是否有模型漏删；修正后重跑 Step 3。

- [ ] **Step 5: 验证可升降级且与模型一致**

```bash
cd backend && alembic upgrade head && alembic downgrade base && alembic upgrade head && echo "MIGRATION OK"
```
Expected: `MIGRATION OK`，无报错。

- [ ] **Step 6: 提交**

```bash
cd .. && git add -A && git commit -m "feat(sop): squash migrations into single SOP baseline"
```

---

## 阶段 5：后端测试清理

### Task 10: 删除 CMMS 测试并修复 fixtures

**Files:**
- Delete: `backend/tests/**` 中对应被删模块的测试
- 可能 Modify: `backend/tests/conftest.py`、`backend/tests/fixtures/`

- [ ] **Step 1: 定位 CMMS 测试文件**

```bash
cd "/Users/yuming/Desktop/smart CMMS/pure sop session/SmartSOP-pure/backend"
find tests -type f -name "*.py" | grep -iE "asset|work_order|workorder|part|meter|request|\bpm\b|preventive|vendor|customer|purchase|location|floor_plan|deprecat|analytic|billing|workflow|currency|cost_categor|time_categor|custom_field|field_config|multi_part|import(s)?_api|export" | grep -viE "procedure|sop"
```
人工核对该清单（排除 SOP 误伤：如 `test_imports.py`/`test_word_import.py` 是 SOP Word 导入，**保留**；`test_exports_api.py` 若是 SOP 导出则保留，若是 CMMS CSV 导出则删）。

- [ ] **Step 2: 删除确认的 CMMS 测试 + permissions phase 测试 + 跨租户 e2e**

```bash
# 示例（以 Step 1 核对结果为准，逐个 git rm）：
git rm backend/tests/**/test_permissions_phase1a.py backend/tests/**/test_permissions_phase1b.py 2>/dev/null
find backend/tests -name "test_phase*_cross_tenant_e2e.py" -exec git rm {} \;
# 其余按 Step 1 清单逐条 git rm
```

- [ ] **Step 3: 运行 pytest，按报错修 fixtures**

```bash
cd backend && pytest -x -q 2>&1 | tail -40
```
对 ImportError/fixture 引用被删模块的报错：编辑 `tests/conftest.py` 与 `tests/fixtures/` 删除被删实体的工厂/夹具；对个别 SOP 测试里引用被删实体的断言做最小修正。反复执行直至通过。

- [ ] **Step 4: 全量 pytest 绿**

```bash
cd backend && pytest -q 2>&1 | tail -15
```
Expected: 全部通过（0 failed / 0 errors）。

- [ ] **Step 5: 提交**

```bash
cd .. && git add -A && git commit -m "test(sop): remove CMMS tests, fix fixtures, green suite"
```

---

## 阶段 6：前端代码删除

### Task 11: 删除 CMMS 视图与组件

**Files:**
- Delete dirs: `frontend/src/views/{inventory,maindata,maintenance,analytics,billing}`、`frontend/src/components/{workorder,inventory,maindata,maintenance,analytics}`
- Delete: `frontend/src/views/admin/config/{WorkOrderConfigView,RequestConfigView,CustomFieldsConfigView}.vue`、`frontend/src/views/settings/WorkflowsView.vue`

- [ ] **Step 1: 删除视图/组件目录与文件**

```bash
cd "/Users/yuming/Desktop/smart CMMS/pure sop session/SmartSOP-pure"
git rm -r frontend/src/views/inventory frontend/src/views/maindata frontend/src/views/maintenance \
  frontend/src/views/analytics frontend/src/views/billing \
  frontend/src/components/workorder frontend/src/components/inventory \
  frontend/src/components/maindata frontend/src/components/maintenance frontend/src/components/analytics
git rm frontend/src/views/admin/config/WorkOrderConfigView.vue \
  frontend/src/views/admin/config/RequestConfigView.vue \
  frontend/src/views/admin/config/CustomFieldsConfigView.vue \
  frontend/src/views/settings/WorkflowsView.vue
```

- [ ] **Step 2: 提交**

```bash
git add -A && git commit -m "feat(sop): remove CMMS frontend views and components"
```

### Task 12: 删除 CMMS API 与 store

**Files:**
- Delete: `frontend/src/api/` 下 29 个 CMMS 文件
- Delete: `frontend/src/store/billing.ts`

- [ ] **Step 1: 删除 CMMS api 文件**

```bash
cd "/Users/yuming/Desktop/smart CMMS/pure sop session/SmartSOP-pure"
git rm frontend/src/api/analytics.ts frontend/src/api/assetCategories.ts frontend/src/api/assets.ts \
  frontend/src/api/billing.ts frontend/src/api/costCategories.ts frontend/src/api/currencies.ts \
  frontend/src/api/customers.ts frontend/src/api/customFields.ts frontend/src/api/deprecations.ts \
  frontend/src/api/exports.ts frontend/src/api/fieldConfigurations.ts frontend/src/api/floorPlans.ts \
  frontend/src/api/imports.ts frontend/src/api/locations.ts frontend/src/api/meterCategories.ts \
  frontend/src/api/meters.ts frontend/src/api/multiParts.ts frontend/src/api/partCategories.ts \
  frontend/src/api/partConsumptions.ts frontend/src/api/parts.ts frontend/src/api/preventiveMaintenances.ts \
  frontend/src/api/purchaseOrderCategories.ts frontend/src/api/purchaseOrders.ts frontend/src/api/requests.ts \
  frontend/src/api/timeCategories.ts frontend/src/api/vendors.ts frontend/src/api/workflows.ts \
  frontend/src/api/workOrderCategories.ts frontend/src/api/workOrders.ts
git rm frontend/src/store/billing.ts
```

> 注：`customFields.ts`/`fieldConfigurations.ts`/`imports.ts`/`exports.ts` 删除前确认无 SOP 视图引用（下一步 Step 2 会兜底检查）。`numberingProfiles.ts` **保留**（SOP heading 用）。

- [ ] **Step 2: 扫描 SOP 代码是否仍引用被删 api/store**

```bash
grep -rnE "@/api/(analytics|assets?|assetCategories|billing|costCategories|currencies|customers|customFields|deprecations|exports|fieldConfigurations|floorPlans|imports|locations|meter|meters|meterCategories|multiParts|part|parts|partCategories|partConsumptions|preventiveMaintenances|purchaseOrder|purchaseOrders|purchaseOrderCategories|requests|timeCategories|vendors|workflows|workOrder|workOrders|workOrderCategories)|@/store/billing" frontend/src --include="*.vue" --include="*.ts" | grep -v ".spec.ts"
```
Expected: 无输出。若有命中（残留引用），回到该 SOP 文件删除对应 import 与用法（多为 admin/config 聚合页的入口卡片、AppSidebar 门控）。

- [ ] **Step 3: 提交**

```bash
git add -A && git commit -m "feat(sop): remove CMMS api clients and billing store"
```

### Task 13: 清理路由、侧边栏、聚合配置页

**Files:**
- Modify: `frontend/src/router/routes.ts`
- Modify: `frontend/src/components/AppSidebar.vue`
- Modify: `frontend/src/views/admin/config/ConfigConsoleView.vue`

- [ ] **Step 1: 删除 routes.ts 中的 CMMS 路由**

打开 `frontend/src/router/routes.ts`，删除以下命名路由及其相关 redirect 别名：
- `config-work-order`（工单配置）、`config-request`（请求配置）、`config-custom-fields`（自定义字段）
- `admin-workflows`（工作流）
- `maindata-locations` / `maindata-location-detail` / `maindata-assets` / `maindata-asset-detail`
- `inventory-parts` / `inventory-multi-parts` / `inventory-part-detail` / `inventory-purchase-orders`
- `partners-vendors` / `partners-customers`
- `maintenance-requests` / `maintenance-preventive-maintenances` / `maintenance-meters` / `maintenance-work-orders` / `maintenance-work-order-detail`
- `analytics`、`billing-settings`、`billing-plans`
- 以及指向上述路径的 `redirect` 别名行（`/maindata/*`、`/inventory/*`、`/platform/*` 中已失效项、`/admin/work-order-fields`、`/admin/request-fields` 等）

保留：auth/account/procedures/folders/audit-logs/notification-center/config-console/config-sop/config-organization/admin-imports/admin-files/platform-users/platform-roles/platform-teams 及 `/` → `/procedures/library`。

- [ ] **Step 2: 删除 AppSidebar.vue 的 CMMS 菜单组与 billing 门控**

打开 `frontend/src/components/AppSidebar.vue`：
- 删除"维护""资产""库存采购""往来单位""分析"五个菜单组（约 152-195 行）
- 删除 `import { useBillingStore } from '@/store/billing'` 及其使用（门控锁定逻辑）
- 保留 SOP 组、管理组（人员权限 + 配置中心）；保留 `useCompanySettingsStore`

- [ ] **Step 3: 清理 ConfigConsoleView 聚合入口**

打开 `frontend/src/views/admin/config/ConfigConsoleView.vue`，删除指向已删配置页（工单/请求/自定义字段/工作流）的入口卡片/链接。保留 SOP 配置、组织设置。

- [ ] **Step 4: 验证无悬挂路由组件引用**

```bash
cd "/Users/yuming/Desktop/smart CMMS/pure sop session/SmartSOP-pure"
grep -rnE "WorkOrderConfigView|RequestConfigView|CustomFieldsConfigView|WorkflowsView|views/(inventory|maindata|maintenance|analytics|billing)" frontend/src --include="*.ts" --include="*.vue"
```
Expected: 无输出。

- [ ] **Step 5: 提交**

```bash
git add -A && git commit -m "feat(sop): prune routes, sidebar, config hub to SOP only"
```

### Task 14: 清理 i18n、types 与前端测试

**Files:**
- Modify: `frontend/src/i18n/locales/*.ts`
- Delete: `frontend/src/types/` 下 CMMS 类型文件（如 `workOrder.ts` 等）
- Delete: CMMS 前端 spec

- [ ] **Step 1: 删除 CMMS 前端测试**

```bash
cd "/Users/yuming/Desktop/smart CMMS/pure sop session/SmartSOP-pure"
find frontend -name "*.spec.ts" | grep -iE "asset|work_?order|part|meter|request|preventive|\bpm\b|vendor|customer|purchase|location|floor|deprecat|analytic|billing|workflow|currenc|cost_?categor|time_?categor|customField|fieldConfig|multiPart|inventory|maindata|maintenance" | grep -viE "procedure|sop|folder|notification|audit" | while read f; do git rm "$f"; done
```
人工复核被删清单，避免误删 SOP 测试。

- [ ] **Step 2: 删除 CMMS 类型文件并扫描残留 type 引用**

```bash
ls frontend/src/types/
grep -rlnE "types/(workOrder|asset|part|meter|request|location|vendor|customer|purchaseOrder)" frontend/src --include="*.ts" --include="*.vue" | grep -v ".spec.ts"
```
删除仅被删模块使用的 `frontend/src/types/*.ts`；对仍被 SOP 引用的类型保留。

- [ ] **Step 3: 清理 i18n 命名空间**

```bash
grep -nE "maintenance|inventory|assets|locations|analytics|billing|workOrder|workorder|vendor|customer|meter|part|request|preventive" frontend/src/i18n/locales/*.ts | head -60
```
编辑各 locale 文件，删除上述被删模块的文案命名空间；保留 auth/account/common/procedures/folders/notifications/audit/admin 等。

- [ ] **Step 4: 提交**

```bash
git add -A && git commit -m "feat(sop): clean i18n, types, and frontend tests"
```

---

## 阶段 7：前端验证与收尾

### Task 15: 前端构建与单测通过

**Files:** 无（验证 + 按需修复）

- [ ] **Step 1: 类型检查 / 构建**

```bash
cd "/Users/yuming/Desktop/smart CMMS/pure sop session/SmartSOP-pure/frontend" && npm run build 2>&1 | tail -30
```
Expected: 构建成功。对"找不到模块/未使用导入"报错，定位并删除残留 import。

- [ ] **Step 2: 单元测试**

```bash
cd "/Users/yuming/Desktop/smart CMMS/pure sop session/SmartSOP-pure/frontend" && npm run test:unit 2>&1 | tail -25
```
Expected: 全部通过。对引用被删模块的残留测试做删除/修正。

- [ ] **Step 3: 提交**

```bash
cd .. && git add -A && git commit -m "fix(sop): green frontend build and unit tests" || echo "nothing to commit"
```

### Task 16: 依赖、文档、CI 收尾

**Files:**
- Modify: `backend/requirements*.txt` 或 `pyproject.toml`、`frontend/package.json`
- Modify: `docs/`、`README.md`、`.github/workflows/*`、`docker-compose.yml`（按需）

- [ ] **Step 1: 移除 stripe 依赖并确认 echarts 归属**

```bash
cd "/Users/yuming/Desktop/smart CMMS/pure sop session/SmartSOP-pure"
grep -rn "stripe" backend/ --include="*.txt" --include="*.toml"
grep -rn "echarts\|vue-echarts" frontend/src --include="*.ts" --include="*.vue" | grep -v ".spec.ts"
```
- 从后端依赖清单删除 `stripe`。
- 若 echarts 无 SOP 引用（仅 analytics 用），从 `frontend/package.json` 删除 `echarts`/`vue-echarts` 并 `npm install` 更新锁文件。

- [ ] **Step 2: 删除 scripts 中的 CMMS 专用脚本（如有）**

```bash
grep -rlnE "work_order|asset|meter|part|request" scripts/ 2>/dev/null
```
仅删除明确属 CMMS 的脚本；SOP parser 评测脚本（eval_parser/validate_*）保留。

- [ ] **Step 3: 更新文档与 README**

```bash
grep -rlnE "工单|资产|库存|采购|维护|计量|分析|计费|work order|asset|inventory" docs/ README.md 2>/dev/null | head
```
删除/精简被删模块章节；README 描述对齐"纯净 SOP"。CI workflow 若含按模块的路径过滤/步骤，相应清理；否则不动。

- [ ] **Step 4: 提交**

```bash
git add -A && git commit -m "chore(sop): drop CMMS deps, update docs/CI"
```

### Task 17: 端到端冒烟验收

**Files:** 无（人工/脚本验证）

- [ ] **Step 1: 后端起服 + 迁移**

```bash
cd "/Users/yuming/Desktop/smart CMMS/pure sop session/SmartSOP-pure/backend"
alembic upgrade head && echo "DB OK"
# 启动（按项目实际命令，如 uvicorn app.main:app）
```
确认 `/docs` 路由表中只剩 SOP/基础设施端点。

- [ ] **Step 2: 全后端测试 + 前端测试最终复核**

```bash
cd backend && pytest -q 2>&1 | tail -5
cd ../frontend && npm run build >/dev/null 2>&1 && npm run test:unit 2>&1 | tail -5
```
Expected: 均通过。

- [ ] **Step 3: 全仓最终悬挂扫描**

```bash
cd "/Users/yuming/Desktop/smart CMMS/pure sop session/SmartSOP-pure"
grep -rnE "maintenance_asset|work_order|\bWorkOrder|preventive_maintenance|\bMeter\b|purchase_order|custom_field_def|form_field_config|workflow_engine" backend/app frontend/src --include="*.py" --include="*.ts" --include="*.vue" | grep -viE "procedure_asset|# |\"\"\"|//"
```
Expected: 无实质代码命中。

- [ ] **Step 4: 浏览器冒烟（人工）**

启动前后端，验证：登录 → 程序库 → 新建/Word 导入程序 → 编辑器（图片正常）→ 提交审批 → 发布 → 通知中心与审计日志可见；侧边栏仅 SOP + 管理两组；控制台无指向被删模块的报错。

- [ ] **Step 5: 最终提交并准备收尾**

```bash
git add -A && git commit -m "test(sop): e2e smoke verification passed" --allow-empty
```
完成后按 `superpowers:finishing-a-development-branch` 决定合并/PR。

---

## 自审备注（spec 覆盖核对）

- 模块边界（spec §2）：Task 2/3/5/11/12 覆盖删除；ProcedureAsset 保留与重命名 = Task 1。
- 解耦污染点（spec §4）：notification_service/attachment_entities = Task 3；asset 重命名 = Task 1；main.py = Task 6；billing catalog = Task 7；前端 sidebar/routes = Task 13。
- 迁移基线（spec §5）= Task 9。
- 测试/依赖/i18n/文档（spec §6）= Task 10/14/16。
- 验收标准（spec §7）= Task 8/9/10/15/17。
- 待核项（spec §2.2 尾注：field_configurations、imports/exports 归属）已在 Task 5/10/12 内以"删除 + grep 兜底"消解。
