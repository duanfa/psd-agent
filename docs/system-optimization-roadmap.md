# BrandOS 系统优化路线图

本文档基于一次 VEJA 详情页工作流日志复盘整理，目标是把当前系统从“能跑通的方向稿”升级为“稳定输出可执行品牌稿”的生产链路。

配套任务拆分见：`docs/system-optimization-tasks.md`

## 问题定义

当前链路在前半段已经具备较好的理解能力：

- 商品理解 Agent 能稳定提取商品类型、主色、材质和卖点。
- Product Brief 能把图片、商品信息和表格内容合并成统一结构。
- 品牌知识库 / 规则版本能提取 Core Rule、Derived Rule 和 Asset Memory。
- 页面规划、图片规划、文案和 Figma / PSD 结构化输出已经基本可用。

但是决定最终效果的“结构化执行层”仍然偏弱，主要体现在：

- `Derived Rule` 没有稳定落成可执行的 `layout_schema`。
- `Layout Engine` 在规则不可执行时回退通用模板，导致品牌布局约束失效。
- `image_slots` 未形成标准协议，图片匹配经常被跳过。
- 多阶段仍依赖“模型尽量输出合法 JSON”，结构校验和重试机制偏弱。
- Excel / wireframe 原始输入噪声较高，容易稀释页面规划和布局阶段的重点。

系统现阶段更像“品牌方向正确的低保真草稿生成器”，而不是“可执行品牌设计系统”。

## 优化目标

本轮优化聚焦 4 个目标：

1. 让品牌规则输出可执行，而不是停留在描述层。
2. 让页面布局和素材分配具备可验证、可追踪的结构化协议。
3. 让每个关键阶段具备严格 schema 校验和阶段内重试能力。
4. 让前端明确区分方向稿、低保真草稿和可执行设计稿。

## 核心原则

### 从“描述性规则”升级为“可执行规则”

`Derived Rule` 不能只描述“应该有哪些模块”和“风格应该怎样”，还必须输出可以直接被 `Layout Engine` 消费的结构，例如：

- section 顺序
- section role
- section layout
- 必需文案字段
- 必需图片槽位
- 高度约束
- 禁用模块和硬性约束

### 从“修 JSON”升级为“强 schema 门控”

关键阶段不应依赖下游兜底修复，而应采用：

- schema 校验
- 业务校验
- 校验失败后同阶段重试
- 超过重试阈值再 fallback

### 从“候选图片驱动”升级为“槽位驱动”

先定义每个页面模块需要什么图片，再决定用哪张素材，而不是先收集候选图再尝试往模块里塞。

### 从“整包喂上下文”升级为“分层摘要”

Excel / wireframe 原始信息应该先被压缩成面向不同阶段的结构化摘要，再按阶段注入模型，而不是把对象级原始数据直接灌进主 prompt。

## 目标架构

建议将当前线性工作流：

```text
商品理解 -> 品牌规则 -> 页面规划 -> 图片规划 -> Layout -> 文案 -> 导出 -> 评分
```

升级为：

```text
商品理解
-> 品牌规则解析
-> 页面规划
-> 布局编译
-> 布局验证
-> 图片槽位编译
-> 素材匹配
-> 文案生成
-> Figma / PSD 导出
-> 评分
-> 审核与反馈
```

其中新增两个关键编译层：

- `layout_compiler`：把品牌规则、页面规划和 wireframe 摘要编译成统一的 `layout_schema`
- `slot_compiler`：从可执行 section 结构中生成 `image_slots`

## P0 任务

### 1. 统一 `layout_schema`

目标：让 `Derived Rule`、页面规划、Layout Engine 使用同一套可执行协议。

要求：

- 定义统一的 `layout_schema`
- 至少包含 `sections / role / layout / order / required_text_fields / required_image_slots / min_height / max_height`
- `Derived Rule` 必须返回该结构
- `Layout Engine` 只消费该结构，不再依赖松散自然语言

### 2. 统一 `image_slots`

目标：让图片分配从“猜测性选图”变成“槽位驱动匹配”。

要求：

- 定义统一的 `image_slots`
- 每个槽位至少包含 `slot_id / section_id / image_role / aspect_ratio / semantic_tags / priority / required`
- 页面规划或布局编译阶段产生 `image_slots`
- 图片匹配和评分阶段读取 `image_slots`

### 3. 阶段输出强校验

目标：降低 JSON 修复、结构漂移和脏数据向下游传播的概率。

要求：

- 为 `page_planner`、`layout_engine`、`image_generation` 定义严格 schema
- 每阶段增加 schema 校验、业务校验和阶段内重试
- 校验失败时不进入下游阶段
- 重试次数耗尽后再 fallback

### 4. 引入 `Layout Guard`

目标：阻止缺失核心结构时继续产出“伪完成布局”。

建议校验规则：

- 必须存在 `layout_schema.sections`
- 必须存在至少一个 `hero`
- 必须有明确的 section 顺序
- 必须存在高优先级图片槽位

失败时不直接产出成功结果，而应进入 `blocked`、`retry` 或 `fallback` 分支。

## P1 任务

### 1. Excel / wireframe 分层摘要

目标：减少 prompt 噪声，提高页面规划和布局阶段的聚焦程度。

建议拆成三层：

- `brief_summary`：给页面规划阶段使用，保留模块顺序、替图要求、显式说明和尺寸约束
- `layout_reference`：给布局阶段使用，保留 section 结构、比例、图片区域和文字区域约束
- `raw_wireframe_dump`：只做存档，不直接进入主 prompt

### 2. 新增 `layout_compiler`

目标：在模型结果和执行引擎之间增加稳定的结构编译层。

职责：

- 统一 section id
- 归一化 role
- 规范 layout 命名
- 合并品牌硬约束
- 生成标准化 `layout_schema`

### 3. 新增素材匹配器

目标：明确“哪张图为什么进这个模块”。

要求：

- 对素材建立语义标签和比例标签
- 按 `image_slots` 进行匹配
- 输出匹配报告，包括：
  - 已匹配槽位
  - 未匹配槽位
  - 候选素材
  - 缺失素材类型
  - 匹配理由

### 4. 修正评分体系

目标：让评分真实反映“是否为可执行品牌稿”。

建议新增扣分项：

- 使用 fallback blueprint
- 缺失 `layout_schema`
- `layout_validation.failed`
- `asset_match_report.skipped`
- 关键图片槽位未命中

## P2 任务

### 1. 提示词瘦身和分层注入

目标：减少无效上下文，提高关键阶段结构输出稳定性。

建议：

- 不再将完整 raw wireframe 直接注入关键阶段 prompt
- 品牌规则只注入当前页面类型相关片段
- 文案阶段只注入最终模块结构和必要商品信息

### 2. 可观测性增强

目标：让 fallback、结构失败和质量波动更容易定位。

建议新增日志指标：

- 每阶段输入 token 规模
- schema 校验结果
- retry 次数
- fallback 原因分类
- layout_schema 命中状态
- image_slots 数量
- slot match rate

### 3. 前端结果态升级

目标：让用户明确知道当前结果的可信度和下一步动作。

前端建议展示：

- `layout_schema` 是否命中
- `layout_validation` 是否通过
- `image_slot_count`
- `asset_match_rate`
- `fallback_used`
- 当前结果等级：
  - 方向稿
  - 低保真草稿
  - 可执行设计稿

## 数据结构建议

### `LayoutSchema`

建议字段：

- `page_type`
- `sections`
- `global_constraints`
- `source_rule_id`
- `source_version`

### `LayoutSection`

建议字段：

- `id`
- `name`
- `role`
- `layout`
- `order`
- `required_text_fields`
- `optional_text_fields`
- `required_image_slots`
- `optional_image_slots`
- `min_height`
- `max_height`

### `ImageSlot`

建议字段：

- `slot_id`
- `section_id`
- `image_role`
- `semantic_tags`
- `aspect_ratio`
- `priority`
- `required`

### `LayoutValidationReport`

建议字段：

- `status`
- `issues`
- `warnings`
- `section_count`
- `image_slot_count`
- `required_asset_roles`
- `missing_asset_roles`

## 后端实施拆分

### 品牌规则模块

- 让 `Derived Rule` 强制返回 `layout_schema`
- 若缺失 `layout_schema`，将规则标记为“不可执行”

### 页面规划模块

- 输出 section 级信息架构，不直接承担最终布局坐标职责
- 与品牌规则解耦，聚焦内容和模块意图

### 布局编译模块

- 合并品牌规则、页面规划和 wireframe 摘要
- 输出标准化 `layout_schema`

### Layout Engine

- 只消费 `layout_schema`
- 去掉隐式猜测式模块生成逻辑

### 素材匹配模块

- 基于 `image_slots` 做素材分配
- 输出结构化匹配报告

### 评分模块

- 引入 `layout_schema hit`、`slot match rate`、`fallback used` 等指标

## 前端实施拆分

### 结果页增强

- 展示 `layout_schema` 是否命中
- 展示 `layout_validation` 状态
- 展示图片槽位数量和匹配率
- 展示是否使用 fallback

### 结果等级标识

建议增加：

- `方向稿`
- `低保真草稿`
- `可执行设计稿`

### 回退解释

当进入 fallback 或 blocked 状态时，明确展示：

- 为什么回退
- 缺什么结构或素材
- 下一步建议补什么

## 建议排期

### 第 1 周

- 定义 `layout_schema`
- 定义 `image_slots`
- 给关键阶段加 schema 校验
- 引入 `Layout Guard`

### 第 2 周

- 改造 `Derived Rule` 产出
- 新增 `layout_compiler`
- 改造 `Layout Engine` 消费链路

### 第 3 周

- 做 wireframe 分层摘要
- 做素材匹配器
- 调整评分和前端结果态

## 最小上线版本

如果只做一版最小但有效的改造，建议优先落地以下 5 项：

1. 定义并落地 `layout_schema`
2. 让 `Derived Rule` 必须产出 `layout_schema`
3. 让 `Layout Engine` 只消费 `layout_schema`
4. 引入 `image_slots`
5. 在前端展示 `fallback` 与“低保真草稿”状态

完成以上 5 项后，系统产出会从“能跑通的方向稿”提升到“开始可信的可执行草稿”。
