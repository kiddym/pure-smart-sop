# Phase 5B 邮件通知 + 生产级文件存储设计

> **状态**：已与用户头脑风暴定稿，待写实现计划（writing-plans）。
> **路线图归属**：Master Roadmap 的 Phase 5「通知与文件」。5A（站内通知）已完成；本期 5B 一次性交付 Phase 5 剩余的两个独立子系统——**邮件通知**与**生产级文件存储**，合并为一个 spec/plan。
> **分支**：在 `phase-0-platform-foundation` 续作，不合并（与 [[phase-0-status]]…[[phase-5a-status]] 同分支）。

## 1. 目标与范围

在已完成的 Phase 0–5A 之上交付两个相互独立的后端子系统：

**子系统 A — 邮件通知**：把 5A 的站内通知**同步投递为邮件**。事件发生时在同事务内除写 `Notification` 外、按用户偏好为该收邮件的收件人写一条 `email_outbox` 行；独立调度 tick 扫 `pending` 行、渲染、经可插拔 `EmailBackend` 投递、写回状态/重试。提供 per-user 通知偏好（全局总闸 + 每类型开关）。

**子系统 B — 生产级文件存储**：抽出 `StorageBackend` 协议（`write/read/delete/exists`），两实现 `LocalBackend`（等价现状）与 `S3Backend`（boto3，兼容 S3/MinIO）。把**持久产物**（asset / attachment / source_docx）散落各 service 的物理 IO 收口到该后端；**临时上传 tmp 保持本地盘**不动。DB 仍存相对 `storage_path`，在 S3 下即 object key，**存储子系统零迁移、DB schema 零改动**。

**本期交付**：
- 2 张新表（`tb_email_outbox` + `tb_notification_preference`）+ 1 迁移（`phase5b_email_storage`）。
- `app/email/`：`EmailBackend` 协议 + SMTP/Console/Memory 三实现 + 渲染模板。
- `app/storage_backends/`：`StorageBackend` 协议 + Local/S3 两实现 + 工厂。
- `email_outbox_service`（enqueue + 投递）、`notification_preference_service`。
- 邮件投递调度 tick（注册进 scheduler，job 数 +1）。
- `/api/v1/notification-preferences` API（仅本人）。
- 三类持久产物消费方（asset/attachment/source_docx + 其 GC/清理任务）的物理 IO 收口到 `StorageBackend`。

**关键原则**：
- **附加式 / 收口式，零行为变化**：邮件挂在 5A `notify()` 单一入口内部，**不改 9 个事件触发逻辑**；存储收口为精确 Edit 替换物理 IO，**不动业务逻辑、不动 DB 字段、不动 tmp/upload_service**。
- 邮件发送绝不内联进业务请求：outbox 行与业务动作同 commit（原子），网络投递由独立调度 tick 异步完成，失败可重试可审计。
- 多租户 SaaS：两张新表 `company_id` NOT NULL，偏好 API 靠既有 `with_loader_criteria` 自动作用域；投递 tick 无请求上下文，`bypass_tenant_scope` 扫描后逐租户 `set_current_company_id` 显式落行（仿 5A `due_reminder` / PM / meter 任务）。
- 跨方言：outbox 的 `subject`/`body`/`params` 用 `Text` 存（渲染后字符串或 json.dumps），偏好 `disabled_types` 用 `Text` 存 json 数组；不用方言 JSON、无 SQL 聚合。
- clean-room：不出现 "Atlas" 字样、不抄第三方源码/DDL/文案；boto3（Apache-2.0）、smtplib（stdlib）均无 GPL 义务。
- 开箱即用、测试零网络：默认 `storage_backend=local` + `email_backend=console`，CI/测试不连真 SMTP/S3。

## 2. 明确不在 5B 内（YAGNI）

- 摘要/批量邮件（digest）——本期逐条即时投递。
- SES/SendGrid 等云厂商 API 后端——`EmailBackend` 协议预留扩展点，本期只做 SMTP/Console/Memory。
- presigned URL 直连下载——下载继续走应用代理流式（`backend.read()`）。
- 既有本地文件 → S3 的自动迁移——切 S3 是部署期一次性 ops 同步，非本期代码。
- per-user locale 邮件——统一用 `default_locale` 文案渲染（用户级 locale 字段本期不加）。
- tmp 上传 / 解析工作目录走对象存储——保持本地盘。
- in-app 通知按类型订阅退订——偏好仅作用于**邮件**通道；站内通知不加开关（5A 已交付且本期不改）。
- 实时推送、前端渲染——延续 5A 边界，本期纯后端。
- 模板引擎（Jinja 等）——纯 Python 字典/f-string 模板。

---

# 子系统 A — 邮件通知

## A3. 数据模型（2 张新表）

### A3.1 `tb_notification_preference`
基类 `UUIDMixin + TimestampMixin + TenantMixin`（`company_id` NOT NULL）。每用户至多一行。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | CHAR(36) PK | UUIDMixin |
| `company_id` | String(36) NOT NULL index | TenantMixin |
| `created_at` / `updated_at` | DATETIME6 | TimestampMixin |
| `user_id` | String(36) index | 所属用户（弱引用，无 FK，零侵入） |
| `email_enabled` | Boolean NOT NULL default True | 全局总闸 |
| `disabled_types` | Text NOT NULL default `"[]"` | json 数组：被关掉的类型码（**黑名单**） |

约束：`UniqueConstraint("company_id", "user_id", name="uq_notif_pref_user")`。

**收邮件判定**：`email_enabled AND type ∉ json.loads(disabled_types)`。**未建记录 = 全默认开**（黑名单语义：新增通知类型自动纳入，用户只需显式关闭不想要的）。

### A3.2 `tb_email_outbox`
基类 `UUIDMixin + TimestampMixin + TenantMixin`。append-only，无软删。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | CHAR(36) PK | UUIDMixin |
| `company_id` | String(36) NOT NULL index | TenantMixin |
| `created_at` / `updated_at` | DATETIME6 | TimestampMixin |
| `recipient_user_id` | String(36) index | 收件人 user id |
| `recipient_email` | String(255) | 入队时邮箱快照（用户后续改邮箱不影响已入队件） |
| `type` | String(40) | 复用 5A 9 种通知类型码 |
| `subject` | Text | 渲染后主题 |
| `body` | Text | 渲染后正文（纯文本或简单 HTML） |
| `status` | String(16) NOT NULL default `pending` | `pending` / `sent` / `failed` |
| `attempts` | Integer NOT NULL default 0 | 已尝试次数 |
| `last_error` | Text nullable | 末次失败信息 |
| `sent_at` | DATETIME6 nullable | 成功投递时刻 |
| `notification_id` | String(36) nullable | 溯源对应站内通知（弱引用，无 FK） |

索引：`ix_email_outbox_status(company_id, status)`（tick 扫 `pending` 用）。

## A4. 邮件类型与渲染

- **类型** = 复用 5A 的 9 种：`WO_ASSIGNED`、`WO_STATUS_CHANGED`、`WO_AUTO_GENERATED`、`REQUEST_SUBMITTED`、`PO_SUBMITTED`、`PO_APPROVED`、`WO_DUE_SOON`、`WO_OVERDUE`、`PART_LOW_STOCK`。
- **渲染**：`app/email/templates.py` 按 `type` + 入队时传入的 `params`（实体标题/自定义 id 等，复用 5A `notify()` 已有的 entity 信息）产出 `(subject, body)`。纯 Python 字典/f-string，文案取 `default_locale`（复用既有 i18n 字典；无用户级 locale）。渲染在 **enqueue 时**完成并落库（subject/body 快照），tick 只负责投递——这样模板/数据变化不影响已入队件，且 tick 无需重查实体。

## A5. 投递后端（`EmailBackend`）

`app/email/backends.py` 定义协议，单方法：
```
send(to: str, subject: str, body: str, *, from_addr: str) -> None   # 失败抛异常
```
- `SMTPBackend`：stdlib `smtplib`（`smtp_host/port/user/password/use_tls`），生产用。
- `ConsoleBackend`：渲染信息打印到日志，开发默认。
- `MemoryBackend`：把发送件收集到进程内列表，供测试断言。
- `app/email/__init__.py` 提供 `get_email_backend()`，按 `settings.email_backend`（`smtp`/`console`/`memory`）返回单例；测试可 monkeypatch。

## A6. 生成与投递流程

### A6.1 入队（同事务，commit 前 · 收进 `notify()` 单一入口）
5A 既有的 `notify(db, *, company_id, recipient_ids, type, entity_type, entity_id, params, ...)` 内部，在写完每条 `Notification` 后追加：对每个收件人查偏好 → 该收邮件则用 `params` 渲染并写一条 `pending` `email_outbox` 行（携 `notification_id`、`recipient_email` 快照）。

- **9 个事件挂钩点零新增**：邮件能力随 `notify()` 自动覆盖全部事件，最不易漏。
- **原子性**：outbox 行与 Notification、与业务动作同一 `db.commit()`；业务回滚则通知与邮件均不入队（延续 5A）。
- 偏好查询、邮箱快照、渲染全部显式按 `company_id` 过滤（不依赖租户事件），以便调度上下文下亦正确。

### A6.2 投递 tick（无请求上下文 · 仿 5A `due_reminder`）
`app/tasks/email_dispatch.py`：
1. `bypass_tenant_scope` 扫所有租户 `status=pending AND attempts < email_max_attempts` 的 outbox 行。
2. 逐租户 `set_current_company_id` 后：调 `EmailBackend.send(...)`。
   - 成功 → `status=sent, sent_at=now`。
   - 异常 → `attempts += 1, last_error=str(e)`；若 `attempts >= email_max_attempts` 置 `status=failed`，否则保持 `pending` 下轮重试。
3. 单次 tick 末尾 `db.commit()`；逐租户 `set/reset_current_company_id`。提供 CLI `main()`（仿既有任务）。
- **去重/不重发**：`sent`/`failed` 不再被扫，天然幂等。
- 注册进 `scheduler.build_scheduler()`：`add_job(..., id="email_dispatch", CronTrigger(每 5 分钟))`。job 数 5→6，更新 `test_scheduler_has_*_jobs`。

## A7. 偏好 API（`/api/v1/notification-preferences`）
复用 5A「仅 `get_current_user` 认证、无额外权限码、全部按 `current_user.id` 过滤」模式：
- `GET ""` → 当前用户偏好；无记录返回默认 `{email_enabled: true, disabled_types: []}`。
- `PUT ""` → upsert（`email_enabled` + `disabled_types` 全量替换）。

outbox **不开放 API**（纯后台队列，运维查库）。

---

# 子系统 B — 生产级文件存储

## B3. `StorageBackend` 协议（`app/storage_backends/base.py`）
键为相对路径字符串（= 现有 DB 里存的相对 `storage_path`）。最小集：
```
write(key: str, data: bytes) -> None     # 自动建父级（Local）
read(key: str) -> bytes                  # 不存在抛 FileNotFoundError
delete(key: str) -> None                 # 幂等，不存在不报错
exists(key: str) -> bool
```

## B4. 两实现
- **`LocalBackend`**（`app/storage_backends/local.py`，默认）：封装现有 `pathlib` 行为，`key` → `storage_root()/key`；`write` 建父目录后 `write_bytes`，`read` `read_bytes`，`delete` `unlink(missing_ok=True)`，`exists` `Path.exists`。**完全等价现状**。
- **`S3Backend`**（`app/storage_backends/s3.py`）：boto3 client，`key` 即 bucket 内 object key；`put_object`/`get_object`/`delete_object`/`head_object`。`get_object` 命中 `NoSuchKey`/404 → 抛 `FileNotFoundError`（对齐 Local 语义）；`delete` 幂等。配置：`s3_bucket`/`s3_endpoint_url`(兼容 MinIO)/`s3_region`/`s3_access_key`/`s3_secret_key`。
- `app/storage_backends/__init__.py` 提供 `get_storage_backend()`，按 `settings.storage_backend`（`local`/`s3`）返回单例；测试可 monkeypatch 为临时目录 Local 或内存假后端。

## B5. 消费方收口（仅持久产物三类 · tmp 不动）
路径助手 `app/storage.py` 仍负责派生相对 key（保留）；「落盘/读盘/删盘」动作从各 service 抽到 backend：
- **`asset_service`**：`asset_path(...).write_bytes/read_bytes` → `backend.write/read(相对 key)`。
- **`attachment_service`**：`upload`（`path.write_bytes`）、`download`/`preview`（`_file_or_404().read_bytes`）、孤儿物理清理 → 走 backend。
- **`source_docx_service`** + `sweep_source_docx` 任务：写/删源 docx → 走 backend。
- 后台任务 `asset_gc` / `cleanup_attachments` / `sweep_source_docx` 中删物理文件 → `backend.delete(key)`。
- **不动**：`upload_service` / tmp 工作目录、解析管线中间文件、`storage.py` 的 key 派生函数、任何 DB 字段。

**为何 key=相对路径**：现有 DB 已存相对路径，直接复用作 backend key，使 Local↔S3 切换对数据层透明、且无迁移。下载/预览继续走应用路由，`backend.read()` 取字节后流式返回，auth + 租户隔离门控不变。S3 不对外暴露。

---

## 8. 配置项（`config.py` 新增）
```
# 邮件
email_backend: str = "console"        # console | smtp | memory
email_from: str = "no-reply@smart-cmms.local"
email_max_attempts: int = 5
smtp_host: str = ""
smtp_port: int = 587
smtp_user: str = ""
smtp_password: str = ""
smtp_use_tls: bool = True
# 存储
storage_backend: str = "local"        # local | s3
s3_bucket: str = ""
s3_endpoint_url: str = ""             # 空=AWS 默认；填写兼容 MinIO 等
s3_region: str = ""
s3_access_key: str = ""
s3_secret_key: str = ""
```
默认值保证开箱即用、测试零网络（`local` + `console`）；生产经环境变量切 `s3` + `smtp`。

## 9. 迁移
`alembic/versions/20260531_0016_phase5b_email_storage.py`，`revision="phase5b_email_storage"`，`down_revision="phase5a_notification"`：
- 建 `tb_notification_preference`（含 `uq_notif_pref_user`）+ `tb_email_outbox`（含 `ix_email_outbox_status`）。
- 对称 downgrade：反序 `drop_index` → `drop_table`。
- 同步在 `app/models/__init__.py` 注册 `EmailOutbox` / `NotificationPreference`（供 `create_all`/Alembic 包含）。
- **alembic 单 head 推进为 `phase5b_email_storage`**。
- **存储子系统零迁移**（DB schema 不变）。

## 10. RBAC / 租户 / 跨方言
- 偏好 API 仅认证、按本人过滤（改/查他人 → 404；跨租户靠 `with_loader_criteria` 对 `NotificationPreference`(TenantMixin) 生效）。
- 投递 tick 无请求上下文：`bypass_tenant_scope` 扫描 + 逐租户 `set_current_company_id`，所有写显式传/落 `company_id`（不靠 contextvar 填充）。沿用 [[tenant-isolation-architecture]]。
- 跨方言：`subject`/`body`/`disabled_types` 用 `Text`；无方言 JSON、无 SQL 聚合。

## 11. 测试策略（预估 +30~40 测）
- **偏好模型/服务**：黑名单语义、未建记录默认全开、`disabled_types` 全量替换、json 往返。
- **enqueue（收进 notify）**：按偏好生成 outbox（总闸关 → 0 行、某类型关 → 跳过、邮箱快照正确、subject/body 已渲染）、与业务同事务回滚 → 无 outbox 行。
- **投递 tick**：`pending`→`sent`、失败 `attempts+1` 并保留 `pending`、达上限 → `failed`、`MemoryBackend` 断言收件内容、跨租户逐租户投递、`sent`/`failed` 不重扫。
- **EmailBackend**：Console（日志）/Memory（列表）/SMTP（monkeypatch `smtplib`）三实现。
- **偏好 API**：GET 默认值、PUT upsert、本人过滤 404、跨租户隔离。
- **StorageBackend**：`LocalBackend` 走真实临时目录（asset/attachment/source_docx 收口后**回归不变**——证明零行为变化）；`S3Backend` 用 mock 的 boto3 client（手写 stub 或 `moto` 若已在依赖）窄单测：key 映射、`get_object` 404 → `FileNotFoundError`、`delete` 幂等。**不连真 S3**。
- **scheduler**：job 数 +1（`email_dispatch`），更新既有断言。

**成功标准**：全量 pytest 0 failed（基线 1077 + 本期新增）；ruff 干净（本期新文件 + 被收口的既有 service）；alembic 单 head `phase5b_email_storage`；Atlas 扫描 0；`storage_backend=local` 下既有附件/asset/docx 全部回归通过；默认 `local`+`console` 开箱即用、CI 零网络。

## 12. 单元边界（isolation & clarity）
- `app/email/backends.py`（投递实现，纯 IO，可独立测）、`app/email/templates.py`（纯函数 type+params→(subject,body)）、`email_outbox_service`（enqueue + tick 逻辑，依赖偏好服务与 backend）、`notification_preference_service`（偏好 CRUD）各自单一职责。
- `app/storage_backends/`（base 协议 + local + s3 + 工厂）：消费方仅依赖协议，实现可替换且各自独立测；`storage.py` 仍是纯 key 派生。
- enqueue 收进 `notify()` 单一入口 → 邮件覆盖随事件自动扩展，挂钩点零散修改面最小。
