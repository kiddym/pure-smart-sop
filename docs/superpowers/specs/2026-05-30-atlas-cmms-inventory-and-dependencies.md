# Atlas CMMS 完整盘点：功能边界与依赖关系

- **日期**: 2026-05-30
- **性质**: 行为/功能规格参考（净室重写依据）。**仅描述 What/关系，绝不复制 Atlas 源码。**
- **来源**: 对 `atlas cmms/Atlas_CMMS` 源码（api: Spring Boot Java；frontend: React；mobile: React Native）的系统盘点。
- **配套**: 见 [Smart CMMS 总体设计与路线图](./2026-05-30-smart-cmms-master-roadmap-design.md)

> 规模：后端 model 60+ 实体（106 个 java 文件含抽象/枚举）、62 个 Controller、64 个 Service、173 个 DTO。

---

## 0. 全局机制（贯穿所有模块）

### 0.1 多租户（shared-DB 行级隔离）
- **`Company` = 租户根**。无 schema-per-tenant，全部共库 + `company_id` 行级隔离。
- **继承骨架**：`DateAudit`(createdAt/updatedAt) → `Audit`(createdBy/updatedBy: 用户 id) → `CompanyAudit`(id + `@ManyToOne company`) → 专用基类（`WorkOrderBase` / `Time` / `BasicInfos`）。几乎所有业务实体继承 `CompanyAudit`。
- **写入加作用域**：`@PrePersist` 从 SecurityContext 取当前用户，强制 `company = user.company`（客户端无法伪造租户）。
- **读取强制校验**：`@PostLoad` 若 `加载行.company != 当前用户.company` 且非 SUPER_ADMIN → 抛 403。即使误查到他租户行也会在加载时炸掉。唯一例外：`File` 可经 `SuperAccountRelation` 跨组织访问。
- **Category 类**继承 `CategoryAbstract`（挂 `CompanySettings` 而非直接挂 Company）。
- **防御纵深**：列表/搜索端点显式 `filterCompany(user)`；`TenantAspect` 对所有 POST/PATCH 的 `@RequestBody` 反射，把引用到的 `CompanyAudit` 子对象按 id 重新 `find` 一次以触发 `@PostLoad` 跨租户校验。
- **当前用户/租户解析**：JWT（subject=email，claim `auth`=RoleType）→ `JwtTokenFilter` → `@CurrentUser` 注入 `OwnUser`。**JWT 内不含 company 声明**，租户永远从 `user.company` 派生。

> **对我们的启示**：Smart CMMS 用 FastAPI 时，等价做法 = 一个 `TenantMixin`（`company_id` 列）+ 依赖注入的"当前用户/租户"上下文 + SQLAlchemy 查询统一加 `company_id` 过滤（事件钩子或 base query）。

### 0.2 RBAC
- **Spring 权限只有两级**：`ROLE_SUPER_ADMIN`（跨租户平台管理员）、`ROLE_CLIENT`（所有普通租户用户）。`@PreAuthorize` 仅判这两者；**细粒度授权全部在 Controller 方法体内**对 `Role` 的权限集判断。
- **`Role`（每租户可自定义）** 持有 5 个权限集合（`Set<PermissionEntity>`）：`create` / `view` / `viewOther` / `editOther` / `deleteOther`。`OwnUser` 单角色（`@ManyToOne Role`）。
- **`PermissionEntity`（15 个权限域）**：`PEOPLE_AND_TEAMS, CATEGORIES, CATEGORIES_WEB, WORK_ORDERS, PREVENTIVE_MAINTENANCES, ASSETS, PARTS_AND_MULTIPARTS, PURCHASE_ORDERS, METERS, VENDORS_AND_CUSTOMERS, FILES, LOCATIONS, SETTINGS, REQUESTS, ANALYTICS`。`SETTINGS` 实为管理员门。
- **`RoleCode`（内置角色模板）**：`ADMIN, LIMITED_ADMIN, TECHNICIAN, LIMITED_TECHNICIAN, VIEW_ONLY, REQUESTER, USER_CREATED`。
- **内置默认角色**（每个新公司种入，均 ROLE_CLIENT）：

  | 角色 | code | 计费占座 | 权限概要 |
  |------|------|:--:|------|
  | Administrator | ADMIN | 是 | 全部 15 域全维度 |
  | Limited Administrator | LIMITED_ADMIN | 是 | 除 PEOPLE_AND_TEAMS/REQUESTS 创建、SETTINGS 查看外几乎全开；不可删 |
  | Technician | TECHNICIAN | 是 | 工单/资产/位置/文件 创建 + 多域查看；无删 |
  | Limited Technician | LIMITED_TECHNICIAN | 是 | 仅文件创建 + 多域查看；无删 |
  | View Only | VIEW_ONLY | 否 | 除 SETTINGS 外只读 |
  | Requester | REQUESTER | 否 | 仅 REQUESTS/FILES 创建 + 少量查看 |

- **方法体内判定范式**：list→需 view（无 viewOther 则再 `filterCreatedBy`）；get→view + (viewOther 或 owner)；create→create；patch→editOther 或 owner；delete→deleteOther 或 owner。"owner" = `createdBy == user.id`。

### 0.3 审计
- 全实体 `createdAt/updatedAt`（JPA 监听）+ `createdBy/updatedBy`（用户 id）。`WorkOrderBase` 关系用 Hibernate **Envers** 做字段级版本历史（`WorkOrderAud`，分析模块用它重建历史状态）。
- SmartSOP 已有等价的 `AuditLog`。

### 0.4 计费/功能门控
- **`PlanFeatures`（16 个功能旗标）**：`PREVENTIVE_MAINTENANCE, CHECKLIST, FILE, PURCHASE_ORDER, METER, REQUEST_CONFIGURATION, ADDITIONAL_TIME, ADDITIONAL_COST, ANALYTICS, REQUEST_PORTAL, SIGNATURE, ROLE, WORKFLOW, API_ACCESS, WEBHOOK, IMPORT_CSV`。
- **套餐 4 档**（启动时种入）：FREE(0 功能) / STARTER / PROFESSIONAL / BUSINESS(全功能)。新注册默认 BUSINESS 试用。
- **门控方式**：Controller 内联判 `company.subscription.plan.features.contains(XXX)`（无注解切面）。座席：`subscription.usersCount` 上限，邀请/启用/改角色处校验。
- **计费集成**：FastSpring webhook（`/fast-spring/*`）；自托管 License 经 **Keygen.sh** 校验（`/license/validity`），SSO 是被 license 门控的功能。

> **对我们的启示**：这是 Phase 6 商业化层。我们可用 Stripe 替代 FastSpring，套餐/功能旗标模型可直接借鉴（功能不受版权保护）。

### 0.5 i18n
- 后端 `Language` 枚举 + 前端/移动端各 8 语言：**en, fr, tr, es, pt_BR, pl, de, ar**（含阿拉伯语 RTL）。
- 我们：中文为主，架构预留 i18n（见路线图）。

---

## 1. 功能模块边界总览

> "拥有" = 该模块定义并管理的实体；"引用" = 跨模块依赖（指向其它模块拥有的实体）。

| 模块 | 拥有的核心实体 | 主要引用（依赖） |
|------|----------------|------------------|
| **P. 平台 Platform** | Company, CompanySettings, GeneralPreferences, UiConfiguration, OwnUser, UserSettings, Role, Team, UserInvitation, VerificationToken, SuperAccountRelation, Notification, PushNotificationToken, File, Currency, Subscription, SubscriptionPlan, SubscriptionChangeRequest, CustomField, FieldConfiguration, WorkOrderConfiguration, WorkOrderRequestConfiguration, CustomSequence | （被所有模块依赖；自身基本不向上依赖） |
| **WO. 工单与执行** | WorkOrder, WorkOrderHistory, Request, PreventiveMaintenance, Schedule, WorkOrderMeterTrigger, Task, TaskBase, TaskOption, Checklist, Labor, AdditionalCost, PartQuantity, PartConsumption, Relation, WorkOrderCategory, TimeCategory, CostCategory | Asset, Location, Meter/Reading, Part, User/Team/Customer, Company, File, Notification, Workflow |
| **AS. 资产/位置/计量** | Asset, AssetCategory, AssetDowntime, Deprecation, Location, Meter, MeterCategory, Reading, FloorPlan | WorkOrder（触发器建单/统计）, Part(M:N), User/Team, Company/CompanySettings, File, Customer/Vendor, Labor, Notification, Subscription |
| **IN. 库存与采购** | Part, MultiParts, PartCategory, PurchaseOrder, PurchaseOrderCategory, Vendor, Customer, Currency*, CostCategory* | WorkOrder（消耗/成本）, Asset/Location(M:N), User/Team, Company, File, Workflow, Subscription, Notification |
| **AN. 分析报表** | （无独立实体，全部 DTO；逻辑在 5 个 analytics Controller 内联计算） | 全模块数据 + Envers 历史 |
| **WF. 工作流自动化** | Workflow, WorkflowAction, WorkflowCondition | WorkOrder/Request/PurchaseOrder/Part/Task（条件与动作的目标） |

\* Currency/CostCategory 跨模块共享。

**关键观察（循环依赖）**：`WorkOrderBase` 放在平台层的 `model/abstracts` 却引用了 Team/File/User/Asset/Location/Customer；`File` 反向 M:N 回指 WorkOrder/Asset/Part/Request/Location；`OwnUser` M:N 回指 Asset/Meter/Part/PM/WorkOrder。Atlas 模块边界因这些"反向集合"而互相缠绕。
> **我们净室重写时应改进**：平台实体只做"被依赖方"，业务模块单向向内依赖；用单向（owning-side-only）映射替代双向回指集合，消除循环。

---

## 2. 实体详目（按模块，关键字段 + 关系）

### 2.1 平台 Platform

- **Company**（租户根, extends Audit）：name/address/phone/website/email/employeesCount/city/state/zipCode；`1:1 File logo`；`1:1 Subscription`；`1:1 CompanySettings`(cascade)。
- **CompanySettings**：`1:1`→ GeneralPreferences, WorkOrderConfiguration, WorkOrderRequestConfiguration, UiConfiguration；`1:N`→ Role(roleList), CostCategory, TimeCategory。
- **GeneralPreferences**：language(默认 EN)、dateFormat、`@ManyToOne Currency`、businessType、timeZone、autoAssignWorkOrders/Requests、askFeedBackOnWOClosed、laborCostInTotalCost、daysBeforePrevMaintNotification 等开关。
- **UiConfiguration**：requests/locations/meters/vendorsAndCustomers 四个模块可见性开关。
- **OwnUser**（extends Audit）：firstName/lastName/email(uniq)/phone/username/password(隐)/rate/jobTitle/lastLogin/enabled/enabledInSubscription/ownsCompany/ssoProvider*；`@ManyToOne Role`(必填)、`@ManyToOne Company`、`@ManyToOne Location`、`1:1 File image`、`1:1 UserSettings`(cascade)；M:N→ Asset/Location/Meter/Part/Team/PM/WorkOrder；`1:N superAccountRelations`、`1:1 parentSuperAccount`。
- **UserSettings**（每用户）：emailNotified + 各实体 emailUpdates 开关 + statsForAssignedWorkOrders。
- **Role**：见 §0.2（5 个权限集 + roleType + code + paid + companySettings）。
- **Team**：M:N→ OwnUser/Asset/Location。
- **UserInvitation**：email + `@ManyToOne Role`（邀请加入组织）。
- **VerificationToken**：token + payload + `1:1 OwnUser` + expiryDate（激活 & 重置密码共用）。
- **SuperAccountRelation**：`superUser`(M:1) + `childUser`(1:1)，跨公司多账号切换。
- **Notification**（extends Audit）：message/seen/notificationType/resourceId；`@ManyToOne OwnUser`。
- **PushNotificationToken**：token + `1:1 OwnUser`（Expo 推送）。
- **File**（extends CompanyAudit）：name/path/type(FileType)/hidden；`@ManyToOne Task`；M:N 回指 Asset/Part/Request/WorkOrder/Location。存储 GCP 或 MinIO（`StorageType`）。
- **Currency**（全局非租户）：name(uniq)/code(uniq)。仅 SUPER_ADMIN 维护。
- **Subscription**（extends Audit）：usersCount(座席)/monthly/cancelled/activated/startsOn/endsOn/up·downgradeNeeded/fastSpringId；`@ManyToOne SubscriptionPlan`。
- **SubscriptionPlan**：name/monthlyCostPerUser/yearlyCostPerUser/code/`Set<PlanFeatures>`。
- **SubscriptionChangeRequest**：code/monthly/usersCount（请求改套餐）。
- **CustomField**（实测仅挂 Vendor）：name/value + `@ManyToOne Vendor`。**注意：Atlas 并无通用的逐实体自定义字段框架**（仅 Vendor）。SmartSOP 已有更通用的 `CustomFieldDef` —— 这是我们的优势。
- **FieldConfiguration**：fieldName + `fieldType`(OPTIONAL/REQUIRED/HIDDEN) + 挂到 WorkOrderConfiguration / WorkOrderRequestConfiguration。控制工单/请求表单字段的显示与必填。
- **WorkOrderConfiguration**：为 description/asset/priority/images/primaryUser/assignedTo/team/location/dueDate/category/purchaseOrder/files/signature/completeFiles/completeTasks/completeTime/completeParts/completeCost 种入 FieldConfiguration。
- **WorkOrderRequestConfiguration**：为 asset/location/primaryUser/dueDate/category/team 种入。
- **CustomSequence**：每公司自增序列（生成 `customId`，如资产 `A%06d`）。

### 2.2 工单与执行 WO

- **WorkOrderBase**（抽象, extends CompanyAudit）：dueDate/priority(默认 NONE)/estimatedDuration/estimatedStartDate/description(≤10000)/title(必填)/requiredSignature；`1:1 File image`；`@ManyToOne` WorkOrderCategory/Location/Team/OwnUser(primaryUser)/Asset；M:N assignedTo(OwnUser)/customers(Customer)/files(File)。`getUsers()` = primaryUser ∪ team 成员 ∪ assignedTo。被 WorkOrder/Request/PreventiveMaintenance/WorkOrderMeterTrigger 继承。
- **WorkOrder**（extends WorkOrderBase, Envers 全历史）：customId/completedOn/`status`(默认 OPEN)/archived/feedback/firstTimeToReact；`@ManyToOne` completedBy(OwnUser)/parentRequest(Request)/parentPreventiveMaintenance(PM)；`1:1 File signature`。
  - 业务派生：`isCompliant()`（completedOn ≤ dueDate）；`isReactive()`（无 PM 父）；`canBeEditedBy()`（有 EDIT_OTHER 或 creator 或 assignee）。
  - **状态机** `Status` = OPEN / IN_PROGRESS / ON_HOLD / COMPLETE，任意→任意但有副作用：首次非 ON_HOLD 转换记 `firstTimeToReact`；转 COMPLETE 记 completedBy/On、若资产无其它未完工单则停资产停机、停所有运行中计时、通知、跑 `WORK_ORDER_CLOSED` 工作流、（可选）通知发起人；signature 仅当订阅含 SIGNATURE。
- **Request**（extends WorkOrderBase）：customId/cancelled/cancellationReason；`1:1 File audioDescription`；`1:1 WorkOrder`（批准后创建）。pending → approved(建 WO + 跑 REQUEST_APPROVED 工作流 + 设资产状态 + 通知) 或 cancelled。批准需 SETTINGS 查看或 LIMITED_ADMIN。
- **PreventiveMaintenance**（extends WorkOrderBase）：customId/name；`1:1 Schedule`(cascade)。生成的 WO 经 `parentPreventiveMaintenance` 回指。
- **Schedule**（extends Audit）：disabled/startsOn/frequency(天, ≥1)/endsOn/dueDateDelay；`1:1 PreventiveMaintenance`。发生时间 = 从 startsOn 每 +frequency 天迭代到 endsOn（仅日粒度，不预生成全部 WO，按日历投影）。
- **WorkOrderMeterTrigger**（extends WorkOrderBase = 完整工单模板）：recurrent/name/`triggerCondition`(LESS_THAN/MORE_THAN)/value(阈值)/waitBefore；`@ManyToOne Meter`。
- **Task**（执行实例, extends CompanyAudit）：notes/value(捕获的答案，统一存 String)；`@ManyToOne TaskBase`(必填)；`1:N File images`；`@ManyToOne WorkOrder` XOR `@ManyToOne PreventiveMaintenance`。
- **TaskBase**（步骤定义, extends CompanyAudit）：label(问题/指令)/`taskType`(默认 SUBTASK)；`1:N TaskOption options`(cascade)；可选 `@ManyToOne` user/asset/meter。
- **TaskOption**：label + `@ManyToOne TaskBase`（仅 MULTIPLE 类型用）。
- **Checklist**（extends DateAudit, 非 CompanyAudit）：`1:N TaskBase taskBases`（可复用模板库）。
- **Labor**（extends Time）：duration(秒)/includeToTotalTime/logged(运行中计时)/hourlyRate/startedAt/`status`(STOPPED/RUNNING)；`@ManyToOne` assignedTo/TimeCategory/WorkOrder。`getCost()` = hourlyRate × duration / 3600。
- **AdditionalCost**（extends Cost）：description/includeToTotalCost/date；`@ManyToOne` assignedTo/CostCategory/WorkOrder。
- **PartQuantity**（计划/请求行）：quantity；`@ManyToOne` Part(必填) + (WorkOrder XOR PurchaseOrder)。`getCost()` = qty × part.cost。
- **PartConsumption**（实际消耗台账）：quantity；`@ManyToOne` Part + WorkOrder。
- **WorkOrderHistory**（extends Audit）：name(事件描述) + `@ManyToOne` OwnUser + WorkOrder（人读事件流，补充 Envers 字段级历史）。
- **Relation**（工单间关联, extends CompanyAudit）：`relationType`(内部 4 值 DUPLICATE_OF/RELATED_TO/SPLIT_FROM/BLOCKS；展示 7 值含反向) + parent/child(WorkOrder)。
- **WorkOrderCategory / TimeCategory / CostCategory**：查找型分类。

#### ★ 工单"程序"现状（将被 SmartSOP 的 SOP 替代）—— 需求 #1 核心
Atlas 工单清单 = **一维扁平的 `Task` 列表**，每条 Task 配一个定义 `TaskBase` + 捕获结果。
- 定义层 `TaskBase`：`label` + `taskType`（**6 种**：`SUBTASK` 勾选 / `TEXT` 文本 / `NUMBER` 数值 / `INSPECTION` 通过-标记 / `MULTIPLE` 选项(TaskOption) / `METER` 抄表）+ 可选 user/asset/meter。
- 实例层 `Task`：`value`（所有答案统一存 String）+ `notes` + `images`(照片证据)；归属一个 WO 或 PM。
- 复用：`Checklist` = 命名的 TaskBase 集合（模板库），经 `PATCH /tasks/work-order/{id}` 推送到工单。
- **局限（正是 SOP 要解决的）**：单层无分组/无子步骤；答案全是字符串；除 MULTIPLE 选项外无条件/分支；**无程序版本固定**（TaskBase 改动不锁定到历史执行）；清单完成度**不**阻断工单完成；无封面/目录/文档结构。
- **SmartSOP SOP 的优势**：章节+步骤树形结构、富文本、整数版本 + JSON 快照（可锁版本）、Word 导入、ReportLab PDF。→ 融合设计见路线图 §4。

### 2.3 资产/位置/计量 AS

- **Asset**（树, extends CompanyAudit）：customId(`A%06d`)/archived/area/description/barCode(每公司唯一)/name/acquisitionCost/nfcId(唯一)/warrantyExpirationDate/inServiceDate/serialNumber/model/power/manufacturer/`status`(默认 OPERATIONAL)；`1:1 File image`；`@ManyToOne` Location/`parentAsset`(自引用,级联删)/AssetCategory/OwnUser(primaryUser)；`1:1 Deprecation`；M:N assignedTo/teams/vendors/customers/parts/files。`getAge()` 以 inServiceDate 起算。
- **Location**（树）：customId/name/address/longitude/latitude；`@ManyToOne parentLocation`(自引用,级联删)；`1:1 File image`；M:N workers/teams/vendors/customers/files。
- **AssetCategory / MeterCategory**（extends CategoryAbstract，挂 CompanySettings）。
- **AssetDowntime**：duration(秒, 0=进行中)/startsOn；`@ManyToOne Asset`(级联删)。`getEndsOn()` = startsOn + duration。
- **Deprecation**（折旧）：purchasePrice/purchaseDate/residualValue/usefulLife/rate/currentValue；被 Asset 1:1 拥有。
- **Meter**：name/unit/updateFrequency(天, ≥1)；`@ManyToOne` MeterCategory/Location/Asset(必填)；`1:1 File image`；M:N users。
- **Reading**（extends Audit, 非 CompanyAudit）：value；`@ManyToOne Meter`。
- **FloorPlan**（仅 id, 非租户基类）：name/area；`1:1 File image` + `@ManyToOne Location`。
- **`AssetStatus`（7 值）**：OPERATIONAL / DOWN / MODERNIZATION / STANDBY / INSPECTION_SCHEDULED / COMMISSIONING / EMERGENCY_SHUTDOWN。映射内部 UP/DOWN（DOWN 与 EMERGENCY_SHUTDOWN 为真停机）。

**层级与自动化**：
- Asset/Location 均为**邻接表**（parent 自引用），根 = parent 为空，递归遍历（无物化路径）。
- **停机传播**：资产转入"真停机"→ 建开放 downtime 并**向上**给所有祖先建 downtime + 改状态；恢复→关闭本机 downtime + **向下递归**关闭所有后代 downtime。
- **抄表→触发器→工单**：每条 Reading 先校验 updateFrequency 节奏，再对该表所有 `WorkOrderMeterTrigger` 判 LESS_THAN/MORE_THAN，命中则通知 + 用触发器模板建 WO。

### 2.4 库存与采购 IN

- **Part**（extends CompanyAudit）：name/cost/barcode/description/`quantity`(库存,≥0)/`minQuantity`(再订点)/area/nonStock/unit；`@ManyToOne PartCategory`；`1:1 File image`；M:N assignedTo(低库存通知对象)/files/customers/vendors/teams/assets/preventiveMaintenances/multiParts。
- **MultiParts**（套件）：name + M:N parts（仅分组，无数量、无自身库存）。
- **PartConsumption**：见 §2.2（实际消耗台账，按时间窗做报表）。
- **PartQuantity**：见 §2.2（WO 或 PO 的行项目）。
- **PurchaseOrder**（extends CompanyAudit）：`status`(ApprovalStatus, 默认 PENDING)/name + 收货块(shipping*) + 附加信息块(additionalInfo*)；`@ManyToOne` PurchaseOrderCategory/Vendor。行项目 = 外部 PartQuantity 引用本 PO。
- **Vendor**（extends BasicInfos）：vendorType/companyName/description/rate；M:N assets/locations/parts；可挂 CustomField。
- **Customer**（extends BasicInfos）：customerType/description/rate/billing*；`1:1 Currency billingCurrency`；M:N parts/locations/assets。
- **PartCategory / PurchaseOrderCategory / CostCategory**（extends CategoryAbstract）。
- **`ApprovalStatus`**：APPROVED / REJECTED / PENDING。

**机制**：
- 库存 = 单字段 `Part.quantity`（≥0）。`consumePart(part, qty, wo)`：减库存；qty>0 且库存不足→406；减后 < minQuantity → 发低库存通知给 assignedTo；建 PartConsumption。qty<0（更正）则回改最近一条消耗。
- WO 挂件即消耗 1 件并建 PartQuantity；改 WO 的 PartQuantity 按差额对冲库存。
- **PO 流程**：create(PENDING, 需 PURCHASE_ORDER 功能旗标) → 加行项目(PartQuantity, 不动库存) → `respond?approved=`(批准时**逐行 `part.quantity += 行数量`** 入库, 置 APPROVED/REJECTED, 不可重复批准) → delete。注意：WO 出库在挂件时即时扣减，PO 入库仅在批准时一次性增加 —— 两条流不对称。

### 2.5 分析报表 AN（无实体，5 个 Controller 内联计算 + Envers 历史）

> 全部 `@PreAuthorize ROLE_CLIENT` + 方法内 `canSeeAnalytics()`（需 ANALYTICS 权限 AND 套餐含 ANALYTICS）。多数接受 `DateRange` POST body，重度 `@Cacheable`。时间序列默认 ≤15 桶；周视图取近 5 周。

- **工单 `/analytics/work-orders`**：完成总览(total/complete/compliant/**mtta**/avgCycleTime)；移动端按状态计数；未完总览(averageAge)；按优先级/状态/资产/用户的未完分布；估时 vs 实际工时；按主责人/完成人/优先级/分类的完成计数；近 5 周计数与工时；成本与工时(labor/part/additional)；按日期的成本；按日期的状态分布（用 Envers 重建历史状态）。
- **资产/可靠性 `/analytics/assets`**：每资产工时&成本；停机；**MTBF**；平均间隔(停机间/维护间)；修复时长(MTTR 输入)；成本总览(**rav** 重置价值比/totalWOCosts/totalAcquisitionCost)；停机+成本；单资产总览(**mtbf/mttr/downtime/uptime/totalCost**)。
- **备件 `/analytics/parts`**：消耗总览；Pareto(按件成本降序)；按资产/件分类/WO 分类的消耗；按月消耗。
- **请求 `/analytics/requests`**：总览(approved/pending/cancelled/cycleTime)；按优先级；周期时间趋势；按分类计数；收到 vs 解决趋势。
- **人员/工时 `/analytics/users`**：当前用户创建/完成数；某用户 14 天每日创建/完成。

### 2.6 工作流自动化 WF

- **Workflow / WorkflowAction / WorkflowCondition**：规则引擎。需套餐含 WORKFLOW（FastSpring 按套餐启停公司工作流）。
- **触发事件 `WFMainCondition`**：WORK_ORDER_CREATED/CLOSED/ARCHIVED、REQUEST_CREATED/APPROVED/REJECTED、PURCHASE_ORDER_CREATED/UPDATED、TASK_UPDATED、PART_UPDATED。
- 各类型有 Condition/Action 枚举（详见附录）。例：TaskAction = CREATE_REQUEST / CREATE_WORK_ORDER / SET_ASSET_STATUS。

---

## 3. API 表面（62 Controller 分组）

- **平台/认证**：Auth, User, Role, Company, CompanySettings, GeneralPreferences, UiConfiguration, UserSettings, Team, Notification, File, Currency, Subscription, SubscriptionPlan, FastSpring, License, CustomField, FieldConfiguration, WorkOrderConfiguration, WorkOrderRequestConfiguration, Export, Import, HealthCheck。
- **工单域**：WorkOrder, Request, PreventiveMaintenance, Schedule, Task, TaskBase, Checklist, Labor, AdditionalCost, PartQuantity, Relation, WorkOrderHistory, WorkOrderMeterTrigger, WorkOrderCategory, TimeCategory, CostCategory。
- **资产域**：Asset, AssetCategory, AssetDowntime, Deprecation, Location, Meter, MeterCategory, Reading, FloorPlan, WorkOrderMeterTrigger(*同上)。
- **库存域**：Part, MultiParts, PartCategory, PurchaseOrder, PurchaseOrderCategory, Vendor, Customer。
- **分析**：analytics/{WO, Asset, Part, Request, User}。
- **工作流**：Workflow。

典型资源端点形态：`POST /search`(分页) · `GET /mini`(轻量下拉) · `GET /{id}` · `POST ""` · `PATCH /{id}` · `DELETE /{id}`，外加领域专属动作（如工单 `PATCH /{id}/change-status`、请求 `/approve` `/cancel`、PO `/respond`、抄表触发）。读多为 `permitAll()` 但靠 `@PostLoad` 兜底租户隔离。

---

## 4. 前端 / 移动端功能面

### 4.1 前端（React Router，认证后 app 布局）
工单(+日历/详情/筛选) · 资产(详情含 work-orders/details/parts/files/meters/downtimes/analytics 标签页) · 位置 · 库存(parts/sets) · 采购单 · 供应商&客户 · 请求 · 预防性维护 · 仪表 · 人员&团队 · 文件 · **分析**(work-orders:status/analysis/aging/time-cost；assets:reliability/cost/useful-life；parts:consumption；requests:analysis) · 分类(7 种) · 设置(general/work-order/request/roles/checklists/workflows/ui-configuration) · 账户(profile/company-profile) · 订阅(plans) · 导入(work-orders/assets/locations/parts/meters) · 升降级 · 切换账号。公开页：landing/pricing/privacy/terms 等。

### 4.2 移动端（React Native，技师子集）
首页+工单统计 · 工单(列表/详情/增改/Tasks/完成/附加成本&工时/筛选) · 资产(+扫码 NFC) · 位置 · 备件 · 仪表 · 请求 · 人员&团队 · 供应商&客户 · 通知 · 设置 · 各类选择器弹窗 · 认证(含自托管 CustomServer) · 切换账号。**无完整分析仪表盘**（仅工单统计）。

---

## 5. 完整枚举清单（净室参考）

- **Status**: OPEN, IN_PROGRESS, ON_HOLD, COMPLETE
- **Priority**: NONE, LOW, MEDIUM, HIGH
- **AssetStatus**: OPERATIONAL, DOWN, MODERNIZATION, STANDBY, INSPECTION_SCHEDULED, COMMISSIONING, EMERGENCY_SHUTDOWN
- **ApprovalStatus**: APPROVED, REJECTED, PENDING
- **TimeStatus**: STOPPED, RUNNING
- **TaskType**: SUBTASK, NUMBER, TEXT, INSPECTION, MULTIPLE, METER
- **FieldType**: OPTIONAL, REQUIRED, HIDDEN
- **FileType**: IMAGE, OTHER
- **DateFormat**: MMDDYY, DDMMYY
- **EnumName**: PRIORITY, STATUS, JS_DATE
- **WorkOrderMeterTriggerCondition**: LESS_THAN, MORE_THAN
- **NotificationType**: INFO, ASSET, WORK_ORDER, PART, METER, LOCATION, TEAM, REQUEST, PURCHASE_ORDER
- **ImportEntity**: WORK_ORDER, ASSET, LOCATION, PART, METER
- **StorageType**: GCP, MINIO
- **BusinessType**(15): BUILDING_MANAGEMENT, CHURCH_MANAGEMENT, CITY_MAINTENANCE, EQUIPMENT_MANAGEMENT, FACILITY_MANAGEMENT, FARMING_MAINTENANCE, FLEET_MANAGEMENT, GENERAL_ASSET_MANAGEMENT, GYM_FITNESS_MAINTENANCE, HOSPITALITY, MANUFACTURING_MANAGEMENT, PHYSICAL_ASSET_MANAGEMENT, PROPERTY_MANAGEMENT, RESTAURANT_MANAGEMENT, SCHOOL_MAINTENANCE
- **RelationType**: DUPLICATE_OF, DUPLICATED_BY, RELATED_TO, SPLIT_TO, SPLIT_FROM, BLOCKED_BY, BLOCKS
- **RelationTypeInternal**: DUPLICATE_OF, RELATED_TO, SPLIT_FROM, BLOCKS
- **RoleType**: ROLE_SUPER_ADMIN, ROLE_CLIENT
- **RoleCode**: ADMIN, LIMITED_ADMIN, TECHNICIAN, LIMITED_TECHNICIAN, VIEW_ONLY, REQUESTER, USER_CREATED
- **PermissionEntity**(15): 见 §0.2
- **BasicPermission**(14, 大多已废): CREATE_EDIT_*, DELETE_*, ACCESS_SETTINGS …
- **PlanFeatures**(16): 见 §0.4
- **Language**(8): EN, FR, TR, ES, PT_BR, PL, DE, AR
- **工作流枚举**：WFMainCondition / {WorkOrder,Request,PurchaseOrder,Part,Task}{Action,Condition} —— 见 §2.6。

---

## 6. 依赖关系图（模块级，箭头 = "依赖/引用"）

```
                     ┌─────────────────────────────┐
                     │   P. 平台 Platform           │  (被所有模块依赖)
                     │  Company/User/Role/Team/     │
                     │  File/Notification/Currency/ │
                     │  Subscription/Settings       │
                     └─────────────────────────────┘
                          ▲      ▲      ▲      ▲
        ┌─────────────────┘      │      │      └──────────────────┐
        │                        │      │                         │
┌───────────────┐      ┌─────────────────────┐          ┌──────────────────┐
│ AS. 资产/位置 │◀────▶│  WO. 工单与执行     │◀────────▶│ IN. 库存与采购   │
│ /计量         │ 触发 │  WorkOrder/Request/ │ 消耗/成本│ Part/PO/Vendor/  │
│ Asset/Location│ 建单 │  PM/Task/Labor      │          │ Customer         │
│ Meter/Reading │ 统计 │  + SmartSOP SOP ★   │          │                  │
└───────────────┘      └─────────────────────┘          └──────────────────┘
        ▲                  ▲   ▲   ▲   ▲                          ▲
        └──────────────────┴───┼───┴──────────────────────────────┘
                               │
                   ┌───────────┴───────────┐        ┌───────────────────┐
                   │ AN. 分析 (读全模块+   │        │ WF. 工作流 (挂钩   │
                   │ Envers 历史)          │        │ WO/Req/PO/Part/Task)│
                   └───────────────────────┘        └───────────────────┘

★ = SmartSOP 的 SOP 引擎在此取代 Atlas 的 Task/TaskBase/Checklist
```

**关键依赖边（建设顺序所需）**：
1. **平台**无前置依赖 → 必须最先（Phase 0）。
2. **位置** 无业务前置（只依赖平台）→ 早建。
3. **资产** 依赖 位置（可空）。
4. **工单** 依赖 资产 + 位置 + 用户/团队 + **SOP**（执行依据）。
5. **请求 / 预防性维护 / 触发器** 依赖 工单（产出 WO）。
6. **库存** 依赖 工单（消耗/成本）；**采购** 依赖 库存 + 供应商。
7. **分析** 依赖上述全部数据 + 审计历史 → 最后。
8. **工作流** 横切，挂钩 WO/Req/PO/Part/Task。

→ 此依赖顺序与路线图的 Phase 0→1→2→3→4 完全吻合。

---

## 7. 对净室重写的关键启示（差异与改进）

1. **SmartSOP 已具备的、可直接复用的基础设施**：AuditLog（≈Audit/Envers）、Attachment（≈File，但需加存储抽象与多租户）、**CustomFieldDef（比 Atlas 仅 Vendor 的 CustomField 强得多，可作为全实体自定义字段框架）**、SOP 版本/Word/PDF（远胜 Task/TaskBase）。
2. **必须新建的平台能力**：多租户 `company_id` + 租户上下文、JWT 认证接线（脚手架已存在）、Role/5 权限集 RBAC、Team、订阅/功能门控、Notification、存储抽象（本地/S3 兼容替代 GCP/MinIO）。
3. **架构改进**：消除 Atlas 的循环依赖（平台实体只被依赖；业务模块单向内向；去掉双向回指集合）。
4. **计费替换**：用 Stripe 替代 FastSpring；自托管授权用我们自己的 license 方案（不用 Keygen）。
5. **合规红线**：所有实体/枚举/权限/套餐均按本"功能规格"全新编写；不复制 Atlas 任何 Java/React/RN 代码、DDL、文案、图标、品牌；产品不含 "Atlas" 字样。

---

## 附录：建设优先级 → 路线图映射

| 依赖层级 | 模块 | 路线图阶段 |
|---|---|---|
| 0（无前置） | 平台（租户/认证/RBAC/团队/i18n/通知基础） | **Phase 0** |
| 1 | 位置、资产、工单、**SOP×工单执行** | **Phase 1 (MVP)** |
| 2 | 请求、预防性维护、仪表/读数/触发器、调度器 | **Phase 2** |
| 3 | 备件/库存、采购、供应商、客户 | **Phase 3** |
| 4 | 分析/报表（MTBF/MTTR/成本/合规/库存 KPI） | **Phase 4** |
| 横切 | 通知&文件存储生产化、工作流自动化 | **Phase 5** |
| 商业 | 订阅/套餐/座席&功能门控/Stripe/自定义字段 | **Phase 6** |
| 端 | 移动端（技师现场执行子集，可离线） | **Phase 7** |
