USE psd_agent;

START TRANSACTION;

DELETE FROM workflow_artifacts;
DELETE FROM workflow_logs;
DELETE FROM workflow_stages;
DELETE FROM workflow_assets;
DELETE FROM workflow_runs;
DELETE FROM products;
DELETE FROM brand_rules;
DELETE FROM brand_training_tasks;
DELETE FROM brand_assets;
DELETE FROM brands;
DELETE FROM app_settings;

INSERT INTO app_settings (`key`, value_json) VALUES
(
  'workflow_stages',
  JSON_ARRAY(
    JSON_OBJECT('id', 'product_understanding', 'title', '商品理解 Agent', 'icon', 'eye'),
    JSON_OBJECT('id', 'product_brief', 'title', 'Product Brief', 'icon', 'layers'),
    JSON_OBJECT('id', 'brand_knowledge', 'title', '品牌知识库 / 规则版本', 'icon', 'library'),
    JSON_OBJECT('id', 'page_planner', 'title', '页面规划 Agent', 'icon', 'palette'),
    JSON_OBJECT('id', 'layout_engine', 'title', 'Layout Engine', 'icon', 'grid'),
    JSON_OBJECT('id', 'copy', 'title', '文案 Agent', 'icon', 'type'),
    JSON_OBJECT('id', 'figma_psd', 'title', 'Figma / PSD 生成 Agent', 'icon', 'file-image'),
    JSON_OBJECT('id', 'design_score', 'title', 'Design Score', 'icon', 'check-circle'),
    JSON_OBJECT('id', 'output_review', 'title', '输出、审核与反馈', 'icon', 'check-circle')
  )
),
(
  'workflow_defaults',
  JSON_OBJECT(
    'project_name', 'BrandOS 商品详情页设计任务',
    'brand_name', 'AURORA 家居旗舰店',
    'product_name', '无线香薰机 Pro',
    'product_brief', '商品类型：香薰机\n核心卖点：静音运行、持久扩香、自然夜灯、一键定时、家居友好设计\n使用场景：卧室、客厅、睡前放松',
    'brand_guidelines', '整体视觉保持简洁、克制、居家质感。页面宽度 790 像素，标题强调留白和层级，颜色以深蓝、暖白和低饱和灰为主。',
    'reference_notes', '参考图作为 Asset Memory 进入品牌知识库，仅辅助生成，不直接覆盖 Core Rule。',
    'workflow_mode', 'smart_recommend',
    'output_types', JSON_ARRAY('detail_page', 'figma_page', 'psd_file'),
    'model_config', JSON_OBJECT(
      'provider', 'openai',
      'model', 'qwen-plus',
      'vision_model', 'qwen-vl-max',
      'api_key', '',
      'base_url', 'https://dashscope.aliyuncs.com/compatible-mode/v1',
      'temperature', 0.4,
      'max_tokens', 4096,
      'enable_deepagents', TRUE,
      'enable_vision', TRUE,
      'max_vision_images', 4
    ),
    'typography', JSON_OBJECT(
      'title_font', '方正兰亭特黑简体',
      'subtitle_font', '方正兰亭黑简体',
      'body_font', '方正兰亭黑简体',
      'english_font', 'AKR Sans',
      'title_size', 28,
      'subtitle_size', 18,
      'body_size', 10,
      'line_height', 1.5,
      'letter_spacing', 0,
      'font_weight', 'Medium',
      'text_color', '#1f2937',
      'lock_brand_typography', TRUE
    ),
    'layout', JSON_OBJECT(
      'canvas_width', 790,
      'module_count', 7,
      'hero_height', 1000,
      'module_height', 820,
      'visual_style', '简洁商务 / 浅色质感 / 接近参考图',
      'background_color', '#eef1f4',
      'accent_color', '#1f2937',
      'image_ratio', 0.62,
      'spacing_scale', 1.0
    ),
    'prompts', JSON_OBJECT(
      'system_prompt', '你是 BrandOS AI 电商设计平台的主控 Agent。你的目标不是直接出图，而是先沉淀品牌知识库与规则版本，再生成结构化页面中间结果，最后输出可继续编辑的 Figma 页面。',
      'vision_agent_prompt', '你是商品理解 Agent。请结合商品图、brief 和上传资料，提炼 Product Brief：商品类型、目标用户、核心卖点、材质参数、适用场景、页面表达重点。',
      'structured_agent_prompt', '你是 Product Brief 结构化 Agent。将商品理解结果与 brief 合并成后续页面规划可消费的结构。',
      'brand_rag_agent_prompt', '你是品牌知识库与规则版本 Agent。请根据品牌规范、参考案例、字体文件和界面配置，生成 Core Rule、Derived Rule、Asset Memory 三层规则。',
      'design_agent_prompt', '你是页面规划 Agent。基于 Product Brief 与 Brand Design System，输出受模板约束的页面信息架构。',
      'layout_agent_prompt', '你是 Layout Engine Agent。将页面结构转成可渲染、可映射到 Figma 的布局 JSON。',
      'copy_agent_prompt', '你是详情页文案 Agent。只基于 brief 和已知信息为每个模块生成文案。',
      'psd_agent_prompt', '你是 Figma / PSD 生成 Agent。将布局与文案转成设计稿生产说明，并保留 PSD 兼容图层树。'
    )
  )
),
(
  'dashboard_page',
  JSON_OBJECT(
    'title', '工作台',
    'subtitle', '查看当前品牌的训练进度、设计任务和常用操作入口',
    'currentBrandName', 'AURORA 家居旗舰店',
    'heroDescription', '当前品牌最近一次训练完成于 2 小时前，已沉淀 4 个规则版本，可直接用于商品详情页生成。',
    'heroTags', JSON_ARRAY('规则版本：V1.4', '最近训练成功率：96%'),
    'weeklyCompletionRate', 87,
    'weeklyStatus', '状态稳定',
    'weeklySummary', '过去 7 天共完成 26 个设计任务，其中 18 个已进入结果审核阶段。',
    'quickActions', JSON_ARRAY(
      JSON_OBJECT('title', '上传品牌资产', 'description', '导入官网、PSD、品牌规范和历史案例，用于品牌训练。', 'href', '/brand-assets'),
      JSON_OBJECT('title', '新建商品', 'description', '录入商品参数、卖点、素材与 Brief，作为任务输入。', 'href', '/products'),
      JSON_OBJECT('title', '发起设计任务', 'description', '选择品牌与商品，配置风格偏向和输出格式后提交。', 'href', '/create-task'),
      JSON_OBJECT('title', '查看设计任务', 'description', '在设计任务列表中查看执行进度、结果和失败原因。', 'href', '/design-tasks')
    )
  )
),
(
  'brand_assets_page',
  JSON_OBJECT(
    'title', '品牌资产',
    'subtitle', '按品牌统一管理设计规范、样例图、官网素材和详情页资产。',
    'folders', JSON_ARRAY(
      JSON_OBJECT('name', '品牌设计规范', 'description', '品牌手册、字体、色彩、版式和禁用规则', 'icon', 'FileText'),
      JSON_OBJECT('name', '样例图', 'description', '可训练的历史案例、风格参考和人工精选图', 'icon', 'FileImage'),
      JSON_OBJECT('name', '官网素材', 'description', '官网截图、活动页、品牌故事和页面源素材', 'icon', 'Globe2'),
      JSON_OBJECT('name', '详情页', 'description', '商品详情页源文件、导出图和历史投放版本', 'icon', 'Folder')
    ),
    'uploadForm', JSON_OBJECT('name', '2026 夏季新品详情页源文件', 'folder', '详情页', 'source', '设计团队交付')
  )
),
(
  'brand_rules_page',
  JSON_OBJECT(
    'title', '品牌规则',
    'subtitle', '查看 AI 提取出的品牌风格、结构和组件规则'
  )
),
(
  'products_page',
  JSON_OBJECT(
    'title', '商品管理',
    'subtitle', '维护商品基础信息、卖点和设计素材，作为生成任务的输入'
  )
),
(
  'design_tasks_page',
  JSON_OBJECT(
    'title', '设计任务',
    'subtitle', '查看所有设计任务的状态、进度和结果入口'
  )
);

INSERT INTO brands (name, status) VALUES
  ('AURORA 家居旗舰店', '已初始化'),
  ('Nordic Living 官方店', '待补充'),
  ('Mellow Sleep', '已初始化');

INSERT INTO brand_assets (brand_id, name, folder, content_type, size, saved_path, source, status, extracted_text, metadata_json) VALUES
  ((SELECT id FROM brands WHERE name = 'AURORA 家居旗舰店'), '品牌视觉规范手册 V1.4', '品牌设计规范', 'application/pdf', 2048000, '/seed/aurora/brand-guide-v1.4.pdf', '品牌方上传', '已解析', NULL, JSON_OBJECT('ext', 'pdf')),
  ((SELECT id FROM brands WHERE name = 'AURORA 家居旗舰店'), '2025 双十一详情页合集', '详情页', 'application/psd', 7340032, '/seed/aurora/d11-detail-pages.psd', '历史案例', '可训练', NULL, JSON_OBJECT('ext', 'psd')),
  ((SELECT id FROM brands WHERE name = 'AURORA 家居旗舰店'), '官网首页截图集', '官网素材', 'image/png', 1258291, '/seed/aurora/homepage-shots.zip', '官网采集', '可训练', NULL, JSON_OBJECT('ext', 'png')),
  ((SELECT id FROM brands WHERE name = 'AURORA 家居旗舰店'), '北欧卧室场景参考图', '样例图', 'image/jpeg', 824312, '/seed/aurora/bedroom-scene.jpg', '设计团队', '待校验', NULL, JSON_OBJECT('ext', 'jpg')),
  ((SELECT id FROM brands WHERE name = 'Nordic Living 官方店'), '北欧风品牌规范草案', '品牌设计规范', 'application/pdf', 1024000, '/seed/nordic/rules-draft.pdf', '品牌方上传', '已解析', NULL, JSON_OBJECT('ext', 'pdf')),
  ((SELECT id FROM brands WHERE name = 'Mellow Sleep'), '睡眠氛围场景图集', '样例图', 'image/jpeg', 952320, '/seed/mellow/scene-pack.jpg', '设计团队', '可训练', NULL, JSON_OBJECT('ext', 'jpg'));

INSERT INTO brand_training_tasks (brand_id, task_code, title, status, summary, created_at, completed_at) VALUES
  ((SELECT id FROM brands WHERE name = 'AURORA 家居旗舰店'), 'TR-240625-01', '品牌资产训练 #TR-240625-01', '生成成功', '输入 36 份品牌资产，输出 design.md / layout.json / component_library.json', '2026-06-25 09:12:00', '2026-06-25 09:26:00'),
  ((SELECT id FROM brands WHERE name = 'AURORA 家居旗舰店'), 'TR-240624-03', '品牌规则重训练 #TR-240624-03', '处理中', '当前进行组件模式归纳，预计 6 分钟完成。', '2026-06-24 19:18:00', NULL),
  ((SELECT id FROM brands WHERE name = 'AURORA 家居旗舰店'), 'TR-240623-02', '品牌素材补录训练 #TR-240623-02', '生成失败', '失败原因：部分 PSD 素材解析异常，建议重新上传后发起训练。', '2026-06-23 15:10:00', '2026-06-23 15:14:00');

INSERT INTO brand_rules (brand_id, version, status, rule_count, layout_count, prompt_count, design_rules, layout_rules, components, prompt_templates) VALUES
(
  (SELECT id FROM brands WHERE name = 'AURORA 家居旗舰店'),
  'V1.4',
  'active',
  42,
  12,
  18,
  JSON_ARRAY(
    JSON_OBJECT('title', '品牌调性', 'description', '简洁、克制、带有科技家居感，强调自然光感与空间呼吸感。'),
    JSON_OBJECT('title', '主色体系', 'description', '主色以深蓝与暖白为核心，辅助色使用低饱和浅灰与淡金。'),
    JSON_OBJECT('title', '字体规则', 'description', '标题偏中黑，正文偏常规，强调信息层级与留白节奏。'),
    JSON_OBJECT('title', '文案风格', 'description', '标题短句、卖点拆分清晰，功能信息与场景利益点并行表达。')
  ),
  JSON_ARRAY(
    JSON_OBJECT('title', 'Hero 模块', 'description', '左文案右大图，首屏突出核心卖点与场景视觉。'),
    JSON_OBJECT('title', 'Feature 模块', 'description', '三列卡片结构，统一图文比例，适合功能点平铺表达。'),
    JSON_OBJECT('title', 'Parameter 模块', 'description', '参数表横向排布，支持图标化表达和重点参数高亮。')
  ),
  JSON_ARRAY(
    JSON_OBJECT('title', '标题区组件', 'description', '支持品牌标题、副标题与简短卖点组合。'),
    JSON_OBJECT('title', '卖点区组件', 'description', '适合 3 到 4 个卖点并列展示。'),
    JSON_OBJECT('title', 'CTA 组件', 'description', '强调行动按钮、利益点和促销信息的组合。')
  ),
  JSON_ARRAY(
    JSON_OBJECT('title', '详情页生成模板', 'description', '适用于新品首发和常规详情页，默认输出 Hero / Feature / Scenario / CTA。'),
    JSON_OBJECT('title', '场景图生成模板', 'description', '强调家居氛围、自然光环境、产品主角突出、减少过度商业感。'),
    JSON_OBJECT('title', '模块重生成模板', 'description', '在保留品牌语言的前提下，对单个模块进行局部变体生成。')
  )
);

INSERT INTO products (brand_id, name, category, summary, brief, design_direction, selling_points, materials, selling_point_count, asset_count, updated_at) VALUES
(
  (SELECT id FROM brands WHERE name = 'AURORA 家居旗舰店'),
  '无线香薰机 Pro',
  '家居电器',
  '支持超声波细腻雾化、低噪运行、夜灯氛围和定时功能，适用于卧室与客厅。',
  '目标人群为 25-40 岁注重居家氛围和睡眠体验的城市人群，页面要突出静谧感和高颜值场景。',
  '暖光、自然材质、留白充足，重点体现家居融合度和夜间使用场景。',
  JSON_ARRAY('静音运行', '持久扩香', '自然夜灯', '一键定时', '家居友好设计', '易清洁水箱'),
  JSON_ARRAY('商品主图', '商品场景图', '补充氛围图'),
  6,
  14,
  '2026-06-24 21:08:00'
),
(
  (SELECT id FROM brands WHERE name = 'AURORA 家居旗舰店'),
  '凉感床品四件套',
  '家纺',
  '面料凉感顺滑，适合夏季卧室场景，强调舒适睡眠与亲肤体验。',
  '页面需要兼顾产品细节特写与卧室大场景展示，突出面料触感和降温卖点。',
  '使用浅灰蓝和暖白，布局舒展，强调清凉和舒适感。',
  JSON_ARRAY('凉感面料', '亲肤触感', '易打理', '适合夏季', '多尺寸可选'),
  JSON_ARRAY('主图', '床品细节图', '卧室场景图'),
  5,
  9,
  '2026-06-24 18:40:00'
),
(
  (SELECT id FROM brands WHERE name = 'AURORA 家居旗舰店'),
  '北欧风收纳架',
  '收纳用品',
  '强调多层收纳、稳定承重与简洁外观，适合客厅与卧室。',
  '需要表现收纳前后对比、层板细节和家居搭配氛围。',
  '轻木纹、浅灰白、透气留白，突出收纳效率和空间整洁感。',
  JSON_ARRAY('多层收纳', '稳定承重', '安装便捷', '百搭家居风'),
  JSON_ARRAY('白底图', '收纳演示图', '空间搭配图'),
  4,
  7,
  '2026-06-23 16:55:00'
);

INSERT INTO workflow_runs (
  run_id, status, current_stage, current_stage_title, current_stage_icon, task_code, task_type,
  project_name, brand_name, product_name, workflow_mode, request_payload, summary, used_deepagents,
  agent_report, design_spec, warnings, created_at, updated_at, completed_at
) VALUES
(
  'run-seed-240625-019',
  'completed',
  NULL,
  NULL,
  NULL,
  'DS-240625-019',
  '商品详情页',
  'BrandOS 商品详情页设计任务',
  'AURORA 家居旗舰店',
  '无线香薰机 Pro',
  'smart_recommend',
  JSON_OBJECT('brand_name', 'AURORA 家居旗舰店', 'product_name', '无线香薰机 Pro'),
  '已输出 Figma 页面，等待设计师审核。',
  TRUE,
  '阶段执行完成，建议进入人工审核。',
  JSON_OBJECT('module_count', 7, 'outputs', JSON_ARRAY('Figma 页面', 'PSD 兼容文件')),
  JSON_ARRAY(),
  '2026-06-25 00:36:00',
  '2026-06-25 00:41:00',
  '2026-06-25 00:41:00'
),
(
  'run-seed-240625-018',
  'running',
  'layout_engine',
  'Layout Engine',
  'grid',
  'DS-240625-018',
  '商品详情页',
  'BrandOS 商品详情页设计任务',
  'AURORA 家居旗舰店',
  '北欧风收纳架',
  'smart_recommend',
  JSON_OBJECT('brand_name', 'AURORA 家居旗舰店', 'product_name', '北欧风收纳架'),
  '当前执行到布局生成阶段，已完成 72%。',
  TRUE,
  NULL,
  NULL,
  JSON_ARRAY(),
  '2026-06-25 00:28:00',
  '2026-06-25 00:28:00',
  NULL
),
(
  'run-seed-240624-014',
  'failed',
  NULL,
  NULL,
  NULL,
  'DS-240624-014',
  '商品详情页',
  'BrandOS 商品详情页设计任务',
  'AURORA 家居旗舰店',
  '凉感床品四件套',
  'smart_recommend',
  JSON_OBJECT('brand_name', 'AURORA 家居旗舰店', 'product_name', '凉感床品四件套'),
  '失败原因：参考素材质量不足，建议补充高质量场景图后重试。',
  FALSE,
  NULL,
  NULL,
  JSON_ARRAY('参考素材质量不足'),
  '2026-06-24 20:15:00',
  '2026-06-24 20:17:00',
  '2026-06-24 20:17:00'
);

COMMIT;
