# 通用附件基础设施 — 设计文档（Atlas 复刻补全 · 第 1 组之 ②）

- 日期：2026-06-02
- 状态：设计草案，**待人工评审**（用户已明确：②风险高于①，spec 须人工确认后再出 plan）
- 背景：核实发现"已完成模块未完全复刻 Atlas"（见 `atlas-parity-backfill`）。Atlas 的 `File` 可挂多种实体（procedure / work_order / asset / request …），本 CMMS 仅 SOP 程序有附件。本 spec 把现有"程序专属附件"**原地泛化**为可挂任意实体的通用附件基础设施。
- 前置：① 平台账户与配置补全**已合并入 main**（merge `f2f6ae1`，alembic head = `platform_account_config`）。本任务从最新 main 切分支 `feat/universal-attachment`。
- 关联：[Atlas 复刻 gap 总账](2026-06-01-remaining-work-audit.md) · ① 设计 [platform-account-config](2026-06-02-platform-account-config-backfill-design.md) · 净室红线见 `cmms-clean-room-baseline`（记忆）

---

## 1. 目标与范围

让附件不再绑死在程序，而是通过 `(entity_type, entity_id)` 多态软关联挂到任意业务实体；新增实体仅改应用层白名单常量，**零迁移**。现有 SOP 程序附件**无损平移**、行为不变、前端零改。

### 1.1 范围（后端，净室——参照 Atlas「File 挂多实体」行为全新原创）
- 多态 `Attachment` 单表（原地泛化 `tb_procedure_attachment`）。
- `ENTITY_REGISTRY`：entity_type → (宿主 model, view_perm, edit_perm)，动态 RBAC。
- 统一 `/attachments` query/form 端点（list/upload/download/preview/update/delete）。
- 兼容别名 `/procedures/{id}/attachments`（前端 SOP 零改）。
- 删宿主时附件清理（扩展现有孤儿清理 task）。

### 1.2 白名单实体（应用层常量，加实体零迁移）
`procedure | work_order | asset | request | location | part`

### 1.3 明确不做（范围决策）
- 不动 `storage` / `storage_backends`（S3/local 落盘、`attachment_path`、GC 物理删除复用现状）。
- 不改上传上限语义（50MB/单 + 30 个/实体 + 200MB/实体，对所有实体统一适用）。
- 不改预览白名单（全局：png/jpeg/gif/webp/pdf）。
- 即时删除钩子可选；MVP 靠清理 task 兜底（同原设计）。
- 工单/资产/库存/分析等业务补全是后续独立 spec，本 spec 只做附件地基。

---

## 2. 核实结论与风险决策（落地前必做项的结论 —— 评审重点）

> 任务要求"先做两个核实、写进 spec 结论"。结论如下，**第 2.3 节是本 spec 与①的最大差异、评审重点**。

### 2.1 核实①：`Procedure.attachments` 的使用面（泛化的主要风险点）
通读结论：**业务代码几乎不直接遍历 ORM relationship**，全部经 `attachment_service`，故泛化面比预想小：

| 位置 | 现状 | 处理 |
|---|---|---|
| `models/procedure.py:67` | `attachments = relationship(back_populates="procedure")` | **移除**该 relationship |
| `models/attachment.py:37` | `procedure = relationship(back_populates="attachments")` | **移除**（连同 FK） |
| `services/procedure_service.py:613` | `attachment_service.rows_for(db, proc_id)` | service 内部改，调用点不变 |
| `services/version_flow_service.py:189,469` | `attachment_service.copy_for_version(...)` | 保留，仅底层模型改名 |
| `services/pdf/context.py:209-220` | **直接 `select(ProcedureAttachment)`** | 改为 `select(Attachment).where(entity_type=='procedure', entity_id==proc.id, ...)`，或改走 `attachment_service.rows_for` |
| `schemas/procedure.py:225`、`pdf/*` | `attachments: list[AttachmentOut]` 字段 | 不变（仍走 service 喂数据） |

结论：唯一直接触达模型的非 service 处是 PDF `context.py`，迁移时一并改。其余只需 service 内部泛化。

### 2.2 核实②：各 entity_type 的精确权限码（permissions.py）

| entity_type | 宿主 model（表） | view_perm | edit_perm |
|---|---|---|---|
| procedure | `Procedure`（tb_procedure） | **None** | **None**（SOP 附件现状裸奔，保持不破坏） |
| work_order | `WorkOrder`（tb_work_order） | `work_order.view` | `work_order.edit` |
| asset | `Asset`（tb_asset, maintenance_asset.py） | `asset.view` | `asset.edit` |
| location | `Location`（tb_location） | `location.view` | `location.edit` |
| part | `Part`（tb_part） | `part.view` | `part.edit` |
| request | `Request`（tb_request） | `request.view` | **`request.create`**（⚠️见下） |

> ⚠️ **request 无 `.edit` 权限码**。permissions.py 中 request 仅有 `view/create/cancel/delete/approve`。**待人工拍板** edit_perm 取值：建议 **`request.create`**（有建请求权 ≈ 可补充其附件，语义最近），备选 `request.view`（读即可写，最宽松，不推荐）。本 spec 暂记 `request.create`，评审定夺。

权限检查机制（沿用 deps.py 现状）：`_user_permission_codes(db, user)` 返回 `set[str]`，判断 `perm in codes`，不足 → 403。

### 2.3 ⚠️ 关键发现：现有 service 远不止 RBAC 的 procedure 耦合（②的真正风险）
原 brainstorm 聚焦"多态模型 + registry RBAC"，但核实发现 `attachment_service` 的 procedure 耦合**深于 RBAC**，泛化必须处理：

| procedure 专属行为 | 代码 | 泛化处理 |
|---|---|---|
| **可写态校验** `_assert_editable`（废止 → PROCEDURE_DEPRECATED；非当前草稿 → PROCEDURE_READONLY） | service:54 | 设为 **EntitySpec 的可选 write 前置钩子**；procedure 注册此钩子，其余实体不注册（任意态可改附件） |
| **审计** `log_procedure_action`（带 `procedure_group_id`） | service:176 等 | 设为 **EntitySpec 的可选审计钩子**；procedure 注册；其余实体 MVP 不写专属审计（或后续接通用审计，本 spec 不做） |
| **跨版本元数据复制** `copy_for_version` | service:243 | procedure 专属，**保留为独立函数**（version_flow 调用），仅模型改名；其余实体无版本概念，不涉及 |
| **上传上限**（50/30/200） | service:31-33 | **泛化为对所有 (entity_type,entity_id) 统一适用**（计数/总量按宿主分组） |
| **预览白名单** | service:36 | 全局保留，所有实体共用 |

**架构决策（评审重点）**：service 拆为「**泛型核心** + **per-entity 钩子**」：
- **读路径**（list/download/preview）：完全泛型、registry 驱动、对所有 entity_type（含 procedure）一致。
- **写路径**（upload/update/delete）：泛型核心（resolve + authorize + 上限 + 落盘/软删 + storage）+ 从 EntitySpec 取可选钩子（write 前置校验、审计）。**procedure 经钩子保留全部既有行为**，故 procedure 别名端点行为与现状逐字节一致、现有测试全绿。
- **procedure 别名端点**与新 `/attachments` 端点**调用同一套泛型函数**（entity_type='procedure'），不再有两套写路径，杜绝"绕过 editability"的 bug 面。

> 该决策把"service 泛化"具体化为"泛型核心 + 钩子"，是对原 brainstorm 的**必要补全**，请评审确认后再出 plan。

---

## 3. 组件分解

复用：`storage` / `storage_backends`（落盘/GC，不动）、`audit_service`（procedure 钩子内）、`tenant` ORM 自动隔离 + `set_current_company_id`（get_current_user 已设）、`deps.get_current_user`、`permissions`、`errors`（bad_request/not_found/forbidden/app_error）。

| 文件 | 类型 | 职责 |
|---|---|---|
| `models/attachment.py` | 改 | `ProcedureAttachment` → `Attachment`（多态：entity_type+entity_id，去 FK，新索引，去 relationship） |
| `services/attachment_registry.py` | 新增 | `ENTITY_REGISTRY`、`EntitySpec`（model/view_perm/edit_perm/write_guard/audit hooks）、`resolve_and_authorize` |
| `services/attachment_service.py` | 改 | 写路径加 entity_type/entity_id + 钩子；读/上限/孤儿清理泛化；`copy_for_version` 保留 |
| `services/attachment_hooks.py` | 新增（或并入 registry） | procedure 的 write_guard（_assert_editable）+ 审计钩子，避免 service↔procedure 循环依赖 |
| `routers/attachments.py` | 改 | 新增 `/attachments` query/form 端点；procedure 别名转泛型 service |
| `schemas/attachment.py` | 改 | `AttachmentOut` 加 `entity_type`/`entity_id`（`procedure_id` 保留为兼容别名见 §6）；新增 list/upload 入参校验 |
| `services/pdf/context.py` | 改 | 直接 `select(ProcedureAttachment)` → 泛化查询（见 §2.1） |
| `services/procedure.py` model | 改 | 移除 `attachments` relationship |
| `tasks/cleanup_attachments.py` + service 清理函数 | 改 | 扩展：扫宿主不存在 → 软删附件（bypass 租户）+ 沿用 storage GC |
| alembic 迁移 | 新增（**末置 task**） | 原地泛化 `tb_procedure_attachment` → `tb_attachment` |

---

## 4. 数据模型 + 迁移

### 4.1 `Attachment`（tb_attachment）
沿用 `UUIDMixin / TimestampMixin / SoftDeleteMixin / NullableTenantMixin`（与现 ProcedureAttachment 一致——附件租户随宿主，可空容忍 SOP 裸奔现状）。

| 字段 | 类型 | 说明 |
|---|---|---|
| `entity_type` | String(32) | 白名单常量；迁移 default `'procedure'` |
| `entity_id` | String(36), index | 多态软关联，**无硬 FK** |
| file_name | String(255) | |
| storage_path | String(500), index | 物理路径（跨引用去重 GC 的 key） |
| mime_type | String(100) | |
| size_bytes | BigInteger | |
| description | Text default '' | |
| sort_order | Integer default 0 | |
| company_id | String nullable | NullableTenantMixin；写入由租户 before_flush stamp |

索引：`Index(entity_type, entity_id)`、`Index(storage_path)`（替换原 procedure_id 索引）。

### 4.2 迁移（原地泛化，无损平移；**末置单独 task**）
> 测试用 SQLite `create_all` 不依赖 alembic；本迁移是生产 artifact，最后写并验 up/down/up，与模型零漂移。

`down_revision` = `platform_account_config`（plan 阶段 `alembic heads` 复核）。

upgrade：
1. `tb_procedure_attachment` rename → `tb_attachment`。
2. 加列 `entity_type`（NOT NULL，server_default `'procedure'`），加 `entity_id`。
3. `UPDATE tb_attachment SET entity_id = procedure_id`，drop `procedure_id` 列。
4. **drop 对 `tb_procedure` 的外键**（rename 后随列在；MySQL 需先按名 drop constraint）。
5. drop 旧索引 `ix_tb_procedure_attachment_*`，建 `ix_tb_attachment_entity`(entity_type,entity_id)、`ix_tb_attachment_storage_path`。
6. （可选）去掉 entity_type server_default，交由应用层。

downgrade：反向（建 procedure_id ← entity_id where entity_type='procedure'、重建 FK 与旧索引、rename 回）。非 procedure 行在 down 时丢弃或报错——down 用于回滚到无通用附件的世界，记 plan 决策。

> ⚠️ MySQL 与 SQLite 在 drop FK / rename / drop column 的方言差异在 plan 的迁移 task 内用 `batch_alter_table` 处理，并实测 MySQL（记忆 `batch-word-parsing-mvp` 的"集成项待手动验证"同理）。

---

## 5. entity_registry + 校验 + 权限

```
EntitySpec = (model, view_perm: str|None, edit_perm: str|None,
              write_guard: Callable|None, audit: AuditHooks|None)
ENTITY_REGISTRY: dict[entity_type -> EntitySpec]   # §2.2 的映射 + §2.3 的钩子
```

`resolve_and_authorize(db, user, entity_type, entity_id, action) -> host`：
1. `entity_type` 不在 registry → **400**（未知类型）。
2. 查宿主：`db.get(spec.model, entity_id)`（业务实体 TenantMixin → ORM 事件按 `set_current_company_id` 自动 scope；procedure 沿用 is_active 存在性）。查不到 → **404**（合并"不存在/跨租户"，不泄漏存在性）。
3. 权限：action=read 用 view_perm、write 用 edit_perm；**为 None 则跳过**（procedure）；非 None 且 `perm not in _user_permission_codes(db,user)` → **403**。
4. 返回宿主（写路径据此调 write_guard）。

端点用 `Depends(get_current_user)`，**不用固定 `require_permission`**（权限随 entity_type 动态，在 service 内动态取 registry 校验）——这是与现有路由不同的一处，特此声明。

---

## 6. 端点 + service + 兼容

### 6.1 端点（统一 `/attachments` 前缀，避免 `/{entity_type}` 吞噬路由）
```
GET    /api/v1/attachments?entity_type=&entity_id=          list（read 授权）
POST   /api/v1/attachments                                  upload（multipart: entity_type, entity_id, file, description?；write 授权）
GET    /api/v1/attachments/{id}/download                    强制 attachment（防 XSS）
GET    /api/v1/attachments/{id}/preview                     仅白名单 inline，否则 415
PUT    /api/v1/attachments/{id}                             description / sort_order（write 授权）
DELETE /api/v1/attachments/{id}                             软删（write 授权）
```
单资源端点（download/preview/PUT/DELETE）先按 id 取 Attachment 行 → 据其 `entity_type/entity_id` 走 `resolve_and_authorize`。

### 6.2 兼容别名（前端 SOP 零改）
保留 `GET/POST /procedures/{id}/attachments`，内部转 `entity_type='procedure', entity_id=id` 的同一泛型 service。`AttachmentOut` 保留 `procedure_id` 字段作为兼容别名（= entity_id when procedure），新增 `entity_type`/`entity_id`，避免前端 SOP 解析失败。

### 6.3 service 写路径（钩子串联，§2.3）
```
upload/update/delete:
  host = resolve_and_authorize(...write)
  spec.write_guard(host)  if any         # procedure: _assert_editable
  <泛型核心：上限校验 / 落盘 / 软删 / flush>
  spec.audit.<action>(...) if any        # procedure: log_procedure_action
```
读路径无钩子。`copy_for_version` 独立保留（procedure 版本流专用）。

---

## 7. 删宿主清理（扩展孤儿 task）

现有 `cleanup_attachments` 仅按"软删 + ≥retention 天 + 无 active 引用 storage_path"做物理 GC。**新增宿主存在性孤儿化**：
- bypass 租户 scope 扫各 entity_type 的 active 附件，宿主（按 entity_type→model）不存在 → **软删该附件**（触发后续 storage GC 走既有逻辑）。
- 跨租户用 bypass + per-item 切上下文（同 `multi-tenancy-phase0-branch` 的 worker 模式）。
- 即时钩子可选，MVP 靠 task 兜底。
- 物理删除（storage GC）逻辑不动。

---

## 8. 错误处理

| 场景 | 处理 |
|---|---|
| 未知 entity_type | 400 |
| 宿主不存在 / 跨租户 | 404（合并，不泄漏存在性） |
| 写权限不足（非 None perm） | 403 |
| procedure 非草稿 / 已废止写 | 400（PROCEDURE_READONLY / PROCEDURE_DEPRECATED，钩子，现状不变） |
| 单文件 >50MB / >30 个 / >200MB | 400 ATTACHMENT_LIMIT_EXCEEDED |
| 预览非白名单 | 415 |
| 附件 / 文件不存在 | 404 |

---

## 9. 测试策略（pytest + SQLite create_all，门禁 ruff 0.15 / mypy 1.20）

- **通用流**：work_order / asset 上传→list→download→update→delete 全绿。
- **多态校验**：未知 type→400；宿主不存在/跨租户→404；写权限不足→403；procedure 不做 RBAC（None 跳过）。
- **现有兼容不破**：`/procedures/{id}/attachments` 仍正常；procedure 草稿/废止写约束仍生效（钩子）；现有 SOP 附件全部测试不改即绿；PDF 导出附件章节正常。
- **跨租户对抗**：A 公司附件不泄漏给 B（list/download/单资源端点全覆盖）。
- **request edit_perm**：按评审定的码校验（默认 `request.create`）。
- **孤儿清理**：宿主删 → 附件被软删 + storage GC；既有"软删 ≥30 天 GC"回归不变。
- **迁移 task**：alembic up/down/up 通过；`tb_procedure_attachment` 数据无损平移（entity_type='procedure'、procedure_id→entity_id）；与 create_all 零漂移；MySQL 方言实测。
- **收口**：全量 `pytest -q` + `ruff check app/` + `mypy app/` 全绿。

---

## 10. 净室声明

参照 Atlas「File 挂多实体（polymorphic attachable）」的**功能行为**全新原创实现；不复制其源码、字段命名、文案、DDL；产品不出现 "Atlas"。GPL 合规前提（见 `cmms-clean-room-baseline`）。仅中文，不做 i18n。

---

## 11. 实现顺序建议（细化留给 writing-plans，TDD bite-sized，迁移末置）

1. 模型泛化 `Attachment`（改名 + 多态字段 + 去 FK/relationship；移除 `Procedure.attachments`；PDF context 查询改）——测试用 create_all。
2. `attachment_registry`（EntitySpec + ENTITY_REGISTRY + resolve_and_authorize）+ procedure 钩子模块。
3. service 写路径泛化（钩子串联）+ 读/上限泛化；`copy_for_version` 保留回归。
4. `/attachments` 端点 + schema（entity_type/entity_id + procedure_id 兼容别名）+ procedure 别名转泛型。
5. 孤儿清理扩展（宿主存在性 + bypass 跨租户）。
6. **alembic 迁移**（原地泛化，up/down/up + MySQL 实测，零漂移）。

依赖：2 依赖 1；3 依赖 2；4 依赖 3；6 末置独立。

---

## 12. 待人工决策项（评审请逐条确认）

1. **request.edit_perm**：`request.create`（建议）/ `request.view` / 其他？
2. **§2.3 架构**："泛型核心 + per-entity 钩子"是否认可（procedure 行为经钩子完全保留）？
3. **非 procedure 实体的审计**：MVP 不写专属审计，可否（后续接通用审计另立）？
4. **downgrade 对非 procedure 行**：丢弃 / 报错阻止回滚——倾向？
5. 上限（50/30/200）对所有实体统一适用，可否？
