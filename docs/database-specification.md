# 数据库规范（Database Specification）

> 适用于 Smart SOP 的 MySQL 8.0 数据库及 SQLAlchemy / Alembic 相关代码。

## 1. 数据库选型

| 项 | 选型 |
|---|------|
| 数据库 | MySQL 8.0 |
| 字符集 | `utf8mb4` |
| 排序规则 | `utf8mb4_0900_ai_ci` |
| 存储引擎 | InnoDB |
| 时区 | 数据库存 UTC，应用层负责展示转换 |

## 2. 命名规范

### 2.1 表名

- **`tb_` 前缀 + 小写蛇形单数**（B6 决策，与 dpms 一致）：`tb_folder`、`tb_procedure`、`tb_procedure_chapter`、`tb_procedure_step`
- 关联表（多对多）`tb_<a>_<b>`：（本项目当前无）
- 审计日志表用 `_audit_log` 后缀：`tb_folder_audit_log`、`tb_procedure_audit_log`

### 2.2 字段名

- **小写蛇形**：`created_at`、`folder_id`
- 外键字段统一以 `_id` 结尾：`parent_id`、`procedure_id`
- 布尔字段语义化：`is_active`、`require_confirmation`、`skip_numbering`
- 时间戳统一：`created_at`、`updated_at`、`deleted_at`、`last_reset_at`
- JSON 字段后缀 `_log` / `_schema` / `_rules`（语义明确）

### 2.3 索引名

| 类型 | 模式 | 例 |
|------|------|----|
| 主键 | `pk_<table>` | `pk_tb_folder` |
| 唯一 | `uq_<table>_<cols>` | `uq_tb_folder_parent_name` |
| 普通 | `ix_<table>_<cols>` | `ix_tb_procedure_folder_id` |
| 外键 | `fk_<table>_<col>` | `fk_tb_procedure_folder_id` |

### 2.4 约束命名

- check 约束：`ck_<table>_<rule>`
- 枚举值集中在应用层，DB 用 `VARCHAR` + 应用校验，**不用** MySQL 原生 `ENUM`（变更不灵活）

## 3. 通用字段（所有业务表必备）

继承自 SQLAlchemy 的两个 Mixin：

```python
class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)


class SoftDeleteMixin:
    is_active: Mapped[bool] = mapped_column(default=True, index=True)
    deleted_at: Mapped[datetime | None] = mapped_column(default=None)
```

**所有业务表**必须包含：

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | `CHAR(36)` UUID | 主键，应用层生成（uuid4） |
| `created_at` | `DATETIME(6)` | 创建时间，自动 |
| `updated_at` | `DATETIME(6)` | 更新时间，自动 |
| `is_active` | `BOOLEAN` | 软删除标志，默认 true |
| `deleted_at` | `DATETIME(6) NULL` | 软删除时间 |

**审计日志表例外**：只追加，不更新，不软删，因此只保留 `created_at`。

## 4. 主键

- 全部用 UUID v4 字符串（`CHAR(36)`），应用层生成
- **不用** 自增 int（除审计日志为追加优化用 `BIGINT AUTO_INCREMENT`）
- 理由：跨库迁移友好；前端可在创建前生成 id（乐观更新）

## 5. 字段类型规范

| 业务语义 | MySQL 类型 |
|---------|-----------|
| UUID | `CHAR(36)` |
| 短文本（≤ 100）| `VARCHAR(100)` |
| 中文本（≤ 500）| `VARCHAR(500)` |
| 富文本 / 长内容 | `LONGTEXT` |
| 布尔 | `BOOLEAN`（实际 `TINYINT(1)`） |
| 整数 | `INT` |
| 大整数（如 audit_log id）| `BIGINT` |
| 浮点 | `DECIMAL(p, s)`（金额）/ `DOUBLE`（指标）|
| 时间 | `DATETIME(6)`（6 位精度毫秒）|
| JSON | `JSON`（MySQL 8.0 原生）|
| 枚举（如 status）| `VARCHAR(20)` + 应用校验 |

### 5.1 长度选择

| 字段语义 | 建议长度 |
|---------|---------|
| 名称（name）| 100 |
| 编码（code）| 100 |
| 标题（title）| 500 |
| 简短描述（description / reason）| `TEXT` |
| 长描述 / 富文本 | `LONGTEXT` |
| IP | `VARCHAR(45)`（兼容 IPv6） |
| User-Agent | `VARCHAR(500)` |
| 操作者标识（operator / deprecated_by 等）| `VARCHAR(128)`（项目无登录体系，预留长度足以容纳 client-supplied identifier）|

## 6. 索引

### 6.1 强制索引

- 所有外键字段必须有索引（MySQL 不会自动创建除非约束声明）
- 列表查询频繁过滤的字段加索引：`folder_id`、`status`、`created_at`
- 唯一约束的字段自动索引（不重复加）

### 6.2 唯一约束 + 软删除

MySQL 不支持 partial unique index（PostgreSQL 才有）。

**解决方案**：在 SQLAlchemy 中用 generated column + 唯一约束模拟：

```python
class Folder(Base):
    __tablename__ = "tb_folder"

    name: Mapped[str] = mapped_column(String(100))
    parent_id: Mapped[UUID | None] = mapped_column(ForeignKey("tb_folder.id"))
    is_active: Mapped[bool] = mapped_column(default=True)

    # generated column：仅当 is_active 时与 (parent_id, name) 一致
    active_unique_key: Mapped[str | None] = mapped_column(
        Computed("CASE WHEN is_active THEN CONCAT_WS('::', COALESCE(parent_id,''), name) END"),
        nullable=True,
    )

    __table_args__ = (
        UniqueConstraint("active_unique_key", name="uq_folder_active_parent_name"),
    )
```

> 也可以选择「软删除时给 name 追加 timestamp 后缀」，但 generated column 更优雅。

### 6.3 索引规模控制

- 单表索引总数 ≤ 7
- 复合索引按选择性高→低排序
- 大字段（`TEXT` / `LONGTEXT` / `JSON`）禁止建普通索引（必要时用前缀索引 `name(20)` 或函数索引）

## 7. JSON 字段

JSON 字段用于：

- `Procedure.version_change_log`：变更日志数组
- `ProcedureStep.input_schema`：JSON Schema
- `ProcedureField.default_value` / `options` / `validation_rules`
- `*AuditLog.old_value` / `new_value`

**规范**：

- 每个 JSON 字段必须在 ORM 中绑定 Pydantic 校验（应用层强校验结构）
- 禁止在 SQL 中用 JSON 函数做业务条件查询（如必要单独建关系表）
- JSON 字段不参与索引（MySQL 函数索引可，但避免依赖）

## 8. 外键

- 主表 → 子表关系全部建外键
- 默认 `ON DELETE RESTRICT`（防止级联删除事故）
- 自引用（如 `Folder.parent_id`）允许 NULL，无 cascade
- 物理删除场景极少（全部走软删），cascade 配置应保守

## 9. 软删除

### 9.1 原则

- **全部业务表走软删**（除 audit_log）
- 查询默认 `WHERE is_active = TRUE`，service 提供 `include_deleted=False` 参数
- 写操作以 `is_active = FALSE` 标记，更新 `deleted_at = NOW()`

### 9.2 数据保留

- 软删除数据保留 ≥ 365 天后可由定时任务物理删除（暂不实现）

## 10. Alembic 迁移

### 10.1 文件命名

由 Alembic 自动生成：`<revision>_<short_slug>.py`，slug 用动词开头描述变更。

```
20260518_1023_initial_schema.py
20260520_1530_add_meter_field_to_step.py
```

### 10.2 迁移规则

- **禁止**手改已发布的 migration；变更通过新增 migration 实现
- 每次模型变更：`alembic revision --autogenerate -m "<slug>"`，**人工审查**生成的代码再提交
- 大表加列 / 加索引：用 `op.execute(...)` 写 online DDL 或分批
- 数据迁移与结构迁移分文件
- 每个 migration 必须能 `downgrade()`（除特殊情况注明）

### 10.3 环境一致性

- CI 中跑 `alembic upgrade head && alembic check`（确保 model 与 migration 同步）
- 生产部署流程：先 migration，后启动新版本应用

## 11. 性能与限制

| 项 | 限制 |
|---|------|
| 单表行数预警 | 100 万行（届时考虑分区或归档） |
| 单事务时长 | ≤ 5s（避免长锁） |
| 单 SQL 复杂度 | join ≤ 3 表，子查询 ≤ 2 层 |
| 慢查询阈值 | 200ms（生产开启 slow_log） |

## 12. 备份与恢复

详见 [deployment.md](deployment.md) 的备份章节。要点：

- 每日 mysqldump 一次，保留 30 天
- 关键变更前手工 dump 一次
- 恢复演练每季度一次

## 13. 字符与编码

- 表 / 库默认 `utf8mb4 / utf8mb4_0900_ai_ci`
- emoji 全支持（避免 utf8 三字节问题）

## 14. 时间字段

- 数据库存 UTC
- 应用层 `datetime.utcnow()` 写入
- 前端按用户时区展示（前端 dayjs 处理）

## 15. 死代码 / 弃用字段

- 不再使用的字段**保留至少一个 release 周期**，标注 `Deprecated`
- 下个 release 通过新 migration 删除
