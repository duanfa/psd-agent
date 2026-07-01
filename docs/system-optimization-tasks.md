# BrandOS 系统优化任务清单

本文档将 `docs/system-optimization-roadmap.md` 中的系统优化方向进一步拆解为可执行任务，适合作为排期、Issue 拆分和开发验收的基础清单。

## 使用方式

- `Epic` 对应一组高相关改造，可以拆成一个里程碑或一个项目阶段。
- `Issue` 对应单个可执行任务，建议一条 Issue 对应一次开发闭环。
- `验收标准` 用于定义“完成”的边界，避免只做一半就进入下游联调。

## Epic 1：建立可执行布局协议

目标：让品牌规则、页面规划和布局引擎使用同一套结构化协议，消除“描述正确但无法执行”的问题。

### Issue 1.1 定义 `LayoutSchema` 数据结构

交付内容：

- 在后端定义 `LayoutSchema` 类型
- 在后端定义 `LayoutSection` 类型
- 明确字段含义、可选项和默认值

建议字段：

- `page_type`
- `sections`
- `global_constraints`
- `source_rule_id`
- `source_version`

`LayoutSection` 至少包含：

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

验收标准：

- 可以在 Python 类型系统中表达并序列化 `LayoutSchema`
- 关键字段缺失时会触发显式校验错误
- 项目内至少有一处 demo 数据或测试样例可验证结构正确性

### Issue 1.2 改造 `Derived Rule` 产出协议

交付内容：

- 让 `Derived Rule` 除设计意图外，必须产出 `layout_schema`
- 无法产出时明确标记为“不可执行规则”

验收标准：

- 新生成的 `detail_page` 规则包含 `layout_schema`
- 缺失 `layout_schema` 的规则不会被 Layout Engine 当作可执行规则使用
- 日志中可清楚区分“命中规则但规则不可执行”和“未命中规则”

### Issue 1.3 新增 `layout_compiler`

交付内容：

- 新增编译层，输入 `brand_rule + page_plan + wireframe_summary`
- 输出标准化 `layout_schema`
- 统一 role、section id、layout 名称和 section 顺序

验收标准：

- 编译器输出结构与 `LayoutSchema` 完全兼容
- 遇到模糊模块名时能稳定归一化到预定义 role
- 编译失败时会输出清晰原因，而不是静默返回空结构

### Issue 1.4 改造 `Layout Engine`

交付内容：

- `Layout Engine` 只消费 `layout_schema`
- 去掉隐式猜测式模块生成逻辑
- 输出模块时保留 section 到 module 的映射关系

验收标准：

- 无 `layout_schema` 时不再伪造完整布局成功结果
- 有 `layout_schema` 时，模块顺序和 section 顺序一致
- 布局结果中能追溯每个 module 对应的 source section

## Epic 2：建立图片槽位和素材匹配链路

目标：让图片分配进入“先定义槽位，再匹配素材”的稳定模式。

### Issue 2.1 定义 `ImageSlot` 数据结构

交付内容：

- 在后端定义 `ImageSlot` 类型
- 明确槽位角色、比例、优先级和语义标签

建议字段：

- `slot_id`
- `section_id`
- `image_role`
- `semantic_tags`
- `aspect_ratio`
- `priority`
- `required`

验收标准：

- 每个高优先级 section 都可以定义至少一个 `ImageSlot`
- `ImageSlot` 可序列化并写入最终设计规格
- 前端或评分模块可以消费该结构

### Issue 2.2 新增 `slot_compiler`

交付内容：

- 从 `layout_schema.sections` 推导 `image_slots`
- 对 hero、feature、scene、spec 等模块生成标准槽位

验收标准：

- 对同一类 layout 输出稳定的槽位集合
- 槽位数量、角色和 section 绑定关系可追踪
- 无图片槽位时能明确说明原因

### Issue 2.3 新增素材打标签器

交付内容：

- 为上传素材建立基础语义标签
- 提取比例、场景类型、产品类型、细节图等属性

验收标准：

- 上传图片至少能被打上角色、比例和语义标签
- 标签结果可在日志或数据结构中查看
- 后续匹配器可直接复用这些标签

### Issue 2.4 新增素材匹配器

交付内容：

- 读取 `image_slots`
- 基于素材标签进行槽位匹配
- 输出结构化匹配报告

匹配报告至少包含：

- 已匹配槽位
- 未匹配槽位
- 候选素材
- 缺失素材类型
- 匹配理由

验收标准：

- 每个 `required` 槽位都有明确的匹配状态
- `asset_match_report` 不再在有槽位时被整体跳过
- 评分模块能直接读取 `match_count`、`slot_count` 和缺口信息

## Epic 3：建立强 schema 校验和守门机制

目标：阻止错误结构进入下游，减少 JSON 修复、无效 fallback 和伪完成结果。

### Issue 3.1 统一关键阶段输出 schema

覆盖阶段：

- `page_planner`
- `image_generation`
- `layout_engine`
- 必要时补充 `copy`

交付内容：

- 为每个阶段定义严格 schema
- 补充结构校验和类型校验

验收标准：

- 关键阶段输出都能通过统一校验入口检查
- schema 不通过时，不进入下游阶段
- 错误信息中能指出具体字段或结构问题

### Issue 3.2 建立阶段内重试机制

交付内容：

- schema 校验失败时触发同阶段重试
- 重试提示只反馈结构问题，不重复注入全部上下文
- 允许配置最大重试次数

验收标准：

- 日志中可看到 retry 次数和原因
- 超过重试次数后再 fallback
- 不再直接依赖下游修复非法 JSON 作为主路径

### Issue 3.3 引入 `Layout Guard`

交付内容：

- 在布局执行前增加 Guard
- 校验是否存在：
  - `layout_schema.sections`
  - `hero`
  - section 顺序
  - 高优先级图片槽位

验收标准：

- Guard 失败时不会继续产出“成功布局”
- Guard 失败原因会进入最终日志和结果摘要
- 前端可以感知 `blocked` / `fallback` 的真实原因

### Issue 3.4 引入 `Asset Guard`

交付内容：

- 在 Figma / PSD 生成前检查关键槽位是否有图
- 缺少关键图时标记为“素材不足”

验收标准：

- 缺少主视觉图、场景图、细节图等关键素材时有明确告警
- 最终结果会显示缺少哪些类型的素材
- 导出阶段能根据 Guard 结果调整结果等级

## Epic 4：重构 Excel / wireframe 输入链路

目标：减少噪声，让模型读取的是真正有用的结构摘要。

### Issue 4.1 设计分层摘要协议

交付内容：

- 定义 `brief_summary`
- 定义 `layout_reference`
- 定义 `raw_wireframe_dump`

验收标准：

- 三层结构用途清晰，不重复堆叠
- 主流程只使用前两层
- 原始对象级信息仅做存档

### Issue 4.2 实现 wireframe 摘要提取器

交付内容：

- 从 Excel / wireframe 中提取：
  - 模块顺序
  - 替图要求
  - 显式注释
  - 比例和尺寸要求
  - 关键图片区和文字区关系

验收标准：

- 摘要长度显著低于原始 dump
- 保留关键模块语义，不丢主指令
- 页面规划阶段可直接消费摘要

### Issue 4.3 重构 prompt 注入策略

交付内容：

- 页面规划阶段只注入 `brief_summary`
- 布局阶段注入 `layout_reference`
- 原始 dump 默认不进入关键阶段 prompt

验收标准：

- prompt 长度可观测下降
- 页面规划和布局阶段的结构输出更稳定
- 日志中可以看见不同阶段实际消费的摘要版本

## Epic 5：修正评分和结果态表达

目标：让评分和前端状态真实反映系统执行质量，而不是只反映“有没有生成出东西”。

### Issue 5.1 调整评分输入指标

新增指标建议：

- `layout_schema_hit`
- `fallback_used`
- `layout_validation_status`
- `image_slot_count`
- `slot_match_rate`

验收标准：

- 评分结果能区分“品牌方向正确但结构未执行”和“结构已执行”
- 使用 fallback 时，`layout_quality` 和 `golden_case_alignment` 会合理下降
- 评分 explain 中明确引用结构执行情况

### Issue 5.2 新增结果等级

建议等级：

- `方向稿`
- `低保真草稿`
- `可执行设计稿`

验收标准：

- 每次运行最终结果都映射到一个明确等级
- fallback 或关键 Guard 失败时不会显示为可执行设计稿
- 前端和日志展示同一套等级定义

### Issue 5.3 前端结果页增强

交付内容：

- 展示 `layout_schema` 是否命中
- 展示 `layout_validation` 状态
- 展示 `image_slot_count`
- 展示 `asset_match_rate`
- 展示是否使用 fallback

验收标准：

- 用户能一眼识别当前结果是不是低保真草稿
- 用户能看到失败原因和建议补充项
- 前端不再只给总分，不解释结构原因

## Epic 6：增强可观测性

目标：让问题定位变成“看日志就知道卡在哪里”，而不是靠人工猜。

### Issue 6.1 新增阶段级监控字段

建议增加：

- 输入 token 规模
- schema 校验结果
- retry 次数
- fallback 原因分类
- `layout_schema` 命中状态
- `image_slots` 数量
- `slot_match_rate`

验收标准：

- 关键阶段日志中都可查看这些字段
- 发生 fallback 时能快速定位根因类别
- 结果页或调试页可读取部分摘要指标

### Issue 6.2 标准化错误分类

建议分类：

- `schema_invalid`
- `rule_not_executable`
- `layout_guard_failed`
- `asset_guard_failed`
- `slot_match_insufficient`
- `model_output_unstable`

验收标准：

- 常见失败路径都能落到稳定错误码或错误类别
- 日志、评分和前端结果态可以共享同一套错误分类

## 建议执行顺序

### 第一阶段：先打通执行骨架

建议先做：

1. `LayoutSchema`
2. `Derived Rule` 产出改造
3. `layout_compiler`
4. `Layout Engine` 消费链路改造

完成标志：

- 系统第一次具备“规则可执行”的闭环能力

### 第二阶段：再打通图片槽位闭环

建议再做：

1. `ImageSlot`
2. `slot_compiler`
3. 素材打标签器
4. 素材匹配器

完成标志：

- `asset_match_report` 可以真实工作，不再频繁 skipped

### 第三阶段：补齐守门和结果态

建议再做：

1. 强 schema 校验
2. 阶段重试
3. `Layout Guard`
4. `Asset Guard`
5. 评分和前端状态升级

完成标志：

- 用户可以明确区分“方向稿”和“可执行稿”

## 最小可上线清单

如果要先做一版最小可上线版本，建议优先完成以下 8 项：

1. 定义 `LayoutSchema`
2. 改造 `Derived Rule` 输出 `layout_schema`
3. 新增 `layout_compiler`
4. 改造 `Layout Engine` 只消费 `layout_schema`
5. 定义 `ImageSlot`
6. 新增 `slot_compiler`
7. 引入 `Layout Guard`
8. 前端展示 `fallback` 和结果等级

完成以上内容后，系统会从“可以生成结果”升级为“可以判断结果是否可信”。
