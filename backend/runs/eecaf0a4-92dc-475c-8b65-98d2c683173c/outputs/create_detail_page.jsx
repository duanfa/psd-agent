// Photoshop JSX：运行后生成可编辑详情页图层初稿。
// 用法：Photoshop -> 文件 -> 脚本 -> 浏览，选择本文件。
#target photoshop
var spec = {
  "project": {
    "name": "BrandOS 商品详情页设计任务",
    "brand": "ANKORAU × ANAR FC",
    "brand_id": "brand_default",
    "product": "电脑包",
    "workflow_mode": "smart_recommend",
    "output_types": [
      "detail_page",
      "figma_page",
      "psd_file"
    ],
    "rule_version_id": "rule_8c40fce30d21"
  },
  "canvas": {
    "width": 790,
    "height": 5920,
    "background_color": "#eef1f4",
    "accent_color": "#1f2937"
  },
  "typography": {
    "title_font": "方正兰亭特黑简体",
    "subtitle_font": "方正兰亭黑简体",
    "body_font": "方正兰亭黑简体",
    "english_font": "AKR Sans",
    "title_size": 28,
    "subtitle_size": 18,
    "body_size": 10,
    "line_height": 1.5,
    "letter_spacing": 0.0,
    "font_weight": "Medium",
    "text_color": "#1f2937",
    "lock_brand_typography": true
  },
  "layout_settings": {
    "canvas_width": 790,
    "module_count": 7,
    "hero_height": 1000,
    "module_height": 820,
    "visual_style": "简洁商务 / 浅色质感 / 接近参考图",
    "background_color": "#eef1f4",
    "accent_color": "#1f2937",
    "image_ratio": 0.62,
    "spacing_scale": 1.0
  },
  "asset_summary": {
    "image": [],
    "brief": [],
    "reference_image": [],
    "font": [],
    "video": [],
    "reference": []
  },
  "referenced_asset_ids": [],
  "product_info": {
    "product_type": "电脑包",
    "target_audience": "注重品质、效率与品牌一致性的电商消费者（待人工确认）",
    "main_color": "以参考图为准（浅蓝 / 低饱和）",
    "material": "尼龙 / 防泼水面料（待人工确认）",
    "key_features": [
      "轻量通勤",
      "多分区收纳",
      "防泼水",
      "简洁商务风格"
    ],
    "scenarios": [
      "办公",
      "通勤",
      "短途旅行"
    ],
    "usable_images": {
      "hero_image": "（待上传主视觉图）",
      "detail_images": [],
      "scene_images": []
    }
  },
  "structured_info": {
    "brand": "ANKORAU × ANAR FC",
    "product": "电脑包",
    "audience": "注重品质、效率与品牌一致性的电商消费者（待人工确认）",
    "selling_points": [
      "轻量通勤",
      "多分区收纳",
      "防泼水",
      "简洁商务风格"
    ],
    "specifications": {
      "size": "根据 brief 提取",
      "weight": "根据 brief 提取",
      "material": "尼龙 / 防泼水面料（待人工确认）"
    },
    "scenarios": [
      "办公",
      "通勤",
      "短途旅行"
    ],
    "design_focus": "将商品卖点转译为标准详情页模块，保持品牌一致性与可编辑性。"
  },
  "brand_profile": {
    "core_rule": {
      "brand_name": "ANKORAU × ANAR FC",
      "positioning": "企业级品牌设计操作系统中的当前品牌空间",
      "tone": "简洁商务 / 浅色质感 / 接近参考图",
      "primary_color": "#1f2937",
      "typography_locked": true
    },
    "derived_rule": {
      "page_type": "商品详情页",
      "module_template": [
        "Hero",
        "Feature",
        "Scenario",
        "Parameter",
        "Brand Story",
        "CTA"
      ],
      "editable_scope": "允许页面层模块、文案和图片策略随任务调整，但受 Core Rule 约束。"
    },
    "asset_memory": {
      "role": "仅作为参考案例，不直接修改核心品牌规则",
      "reference_notes": "参考图作为 Asset Memory 进入品牌知识库，仅辅助生成，不直接覆盖 Core Rule。",
      "reference_images": [],
      "asset_names": []
    },
    "rule_weights": {
      "core_rule": 0.7,
      "derived_rule": 0.2,
      "asset_memory": 0.1
    },
    "drift_risks": [
      "新上传资产默认进入训练池，不自动覆盖当前生效规则"
    ],
    "version": "Brand Rule V4.0",
    "rule_status": "draft_pending_approval",
    "brand_style": "简洁商务 / 浅色质感 / 接近参考图",
    "primary_color": "#1f2937",
    "secondary_colors": [
      "#eef1f4",
      "#ffffff"
    ],
    "fonts": {
      "title": "方正兰亭特黑简体",
      "body": "方正兰亭黑简体",
      "english": "AKR Sans"
    },
    "layout_rules": [
      "页面宽度 790px，高度不限",
      "标题 方正兰亭特黑简体 28号",
      "正文 方正兰亭黑简体 10号",
      "英文 AKR Sans",
      "先生成结构化页面 Layout JSON，再映射到 Figma / PSD 输出"
    ],
    "component_patterns": [
      "Hero",
      "Feature",
      "Technology",
      "Scenario",
      "Parameter",
      "Brand Story",
      "CTA"
    ],
    "prompt_templates": [
      "详情页页面规划",
      "场景图生成",
      "局部模块重生成",
      "设计评分"
    ],
    "module_order": [
      "Hero",
      "Feature",
      "Scenario",
      "Parameter",
      "Brand Story",
      "CTA"
    ]
  },
  "design_direction": {
    "direction": "对齐参考图：浅色背景 + 大图展示 + 简洁文字层级，突出商品质感与通勤属性。",
    "page_template": [
      "Hero",
      "Feature",
      "Scenario",
      "Parameter",
      "Brand Story",
      "CTA"
    ],
    "information_architecture": [
      "首屏建立品牌和商品心智",
      "核心卖点用卡片或分段模块展开",
      "场景模块承接用户使用想象",
      "参数与品牌收尾提供决策依据"
    ],
    "tone": "低饱和、冷静、商务；节奏为大图 → 局部细节 → 功能说明。",
    "image_strategy": "Image Studio 需补齐主视觉、卖点图、场景图与参数说明图；素材不足时以占位图进入设计师审核。",
    "brand_constraints": [
      "严格遵守品牌字体与字号",
      "主色锁定 #1f2937",
      "页面结构必须基于标准模块模板，不自由扩写模块体系"
    ],
    "risks": [
      "实拍素材需人工抠图调色",
      "文案避免绝对化与平台风险词"
    ]
  },
  "modules": [
    {
      "index": 1,
      "name": "Hero",
      "layer_group": "01_Hero",
      "layout": "hero_split",
      "role": "hero",
      "height": 1000,
      "image_role": "主视觉图",
      "elements": [
        "BG_背景",
        "IMG_图片",
        "TXT_标题",
        "TXT_说明"
      ],
      "image_candidates": [],
      "copy": {
        "headline": "电脑包",
        "subtitle": "ANKORAU × ANAR FC",
        "body": "为日常办公与通勤设计的多功能电脑包",
        "points": [
          "轻量通勤",
          "多分区收纳",
          "防泼水"
        ]
      }
    },
    {
      "index": 2,
      "name": "Feature",
      "layer_group": "02_Feature",
      "layout": "three_column_cards",
      "role": "feature",
      "height": 820,
      "image_role": "Feature用图",
      "elements": [
        "BG_背景",
        "IMG_图片",
        "TXT_标题",
        "TXT_说明"
      ],
      "image_candidates": [],
      "copy": {
        "headline": "多分区收纳",
        "subtitle": "Feature",
        "body": "多分区收纳，贴合真实使用场景。",
        "points": []
      }
    },
    {
      "index": 3,
      "name": "Technology",
      "layer_group": "03_Technology",
      "layout": "detail_zoom",
      "role": "technology",
      "height": 820,
      "image_role": "Technology用图",
      "elements": [
        "BG_背景",
        "IMG_图片",
        "TXT_标题",
        "TXT_说明"
      ],
      "image_candidates": [],
      "copy": {
        "headline": "防泼水",
        "subtitle": "Technology",
        "body": "防泼水，贴合真实使用场景。",
        "points": []
      }
    },
    {
      "index": 4,
      "name": "Scenario",
      "layer_group": "04_Scenario",
      "layout": "full_bleed_scene",
      "role": "scenario",
      "height": 820,
      "image_role": "Scenario用图",
      "elements": [
        "BG_背景",
        "IMG_图片",
        "TXT_标题",
        "TXT_说明"
      ],
      "image_candidates": [],
      "copy": {
        "headline": "简洁商务风格",
        "subtitle": "Scenario",
        "body": "简洁商务风格，贴合真实使用场景。",
        "points": []
      }
    },
    {
      "index": 5,
      "name": "Parameter",
      "layer_group": "05_Parameter",
      "layout": "spec_table",
      "role": "parameter",
      "height": 820,
      "image_role": "Parameter用图",
      "elements": [
        "BG_背景",
        "IMG_图片",
        "TXT_标题",
        "TXT_说明"
      ],
      "image_candidates": [],
      "copy": {
        "headline": "轻量通勤",
        "subtitle": "Parameter",
        "body": "轻量通勤，贴合真实使用场景。",
        "points": []
      }
    },
    {
      "index": 6,
      "name": "Brand Story",
      "layer_group": "06_BrandStory",
      "layout": "minimal_logo",
      "role": "brand_story",
      "height": 820,
      "image_role": "Brand Story用图",
      "elements": [
        "BG_背景",
        "IMG_图片",
        "TXT_标题",
        "TXT_说明"
      ],
      "image_candidates": [],
      "copy": {
        "headline": "ANKORAU × ANAR FC",
        "subtitle": "品牌规则驱动的页面收尾",
        "body": "",
        "points": []
      }
    },
    {
      "index": 7,
      "name": "CTA",
      "layer_group": "07_CTA",
      "layout": "cta_panel",
      "role": "cta",
      "height": 820,
      "image_role": "CTA用图",
      "elements": [
        "BG_背景",
        "IMG_图片",
        "TXT_标题",
        "TXT_说明"
      ],
      "image_candidates": [],
      "copy": {
        "headline": "延续品牌一致的设计表达",
        "subtitle": "进入审核与导出",
        "body": "",
        "points": []
      }
    }
  ],
  "psd_layers": [
    {
      "group": "01_Hero",
      "layers": [
        "BG_背景",
        "IMG_主视觉图",
        "TXT_主标题",
        "TXT_副标题",
        "TXT_正文",
        "TXT_要点1",
        "TXT_要点2",
        "TXT_要点3",
        "LOGO_品牌"
      ]
    },
    {
      "group": "02_Feature",
      "layers": [
        "BG_背景",
        "IMG_Feature用图",
        "TXT_主标题",
        "TXT_副标题",
        "TXT_正文"
      ]
    },
    {
      "group": "03_Technology",
      "layers": [
        "BG_背景",
        "IMG_Technology用图",
        "TXT_主标题",
        "TXT_副标题",
        "TXT_正文"
      ]
    },
    {
      "group": "04_Scenario",
      "layers": [
        "BG_背景",
        "IMG_Scenario用图",
        "TXT_主标题",
        "TXT_副标题",
        "TXT_正文"
      ]
    },
    {
      "group": "05_Parameter",
      "layers": [
        "BG_背景",
        "IMG_Parameter用图",
        "TXT_主标题",
        "TXT_副标题",
        "TXT_正文"
      ]
    },
    {
      "group": "06_BrandStory",
      "layers": [
        "BG_背景",
        "TXT_主标题",
        "TXT_副标题",
        "LOGO_品牌"
      ]
    },
    {
      "group": "07_CTA",
      "layers": [
        "BG_背景",
        "TXT_主标题",
        "TXT_副标题",
        "LOGO_品牌"
      ]
    }
  ],
  "design_score": {
    "brand_match": 87,
    "layout_quality": 83,
    "visual_consistency": 84,
    "readability": 82,
    "conversion_score": 80,
    "overall": 83.2,
    "explain": [
      "评分用于给设计负责人提供可解释审核依据，不替代人工判断。",
      "品牌匹配优先参考 Core Rule、Derived Rule 与当前页面模板。",
      "缺少商品实拍或场景素材时，视觉一致性和转化评分会被扣分。"
    ],
    "blocking_issues": [
      "建议补充高质量商品图后再导出正式设计稿"
    ]
  },
  "outputs": {
    "produced": [
      "商品详情页结构化方案",
      "Figma 页面",
      "PSD 兼容文件"
    ],
    "review_checklist": [
      "品牌一致性：是否符合品牌视觉规范",
      "字体字号：是否使用指定字体和允许字号",
      "图片质量：抠图、清晰度、色彩是否达标",
      "版式质量：是否接近参考图风格、是否美观",
      "文案准确性：是否与 brief 一致、是否有夸大",
      "Figma/PSD 可编辑性：图层是否清晰、文字是否可编辑"
    ],
    "feedback_capture": {
      "tracked_changes": [
        "模块隐藏/删除",
        "字体字号调整",
        "颜色调整",
        "文案修改",
        "图片替换"
      ],
      "learning_policy": "本阶段只记录设计师修改，不自动强化学习、不自动覆盖品牌规则。"
    },
    "next_step": "进入人工审核：设计师初审 → 运营/品牌方审核 → 记录反馈 → 交付上线。"
  },
  "review_checklist": [
    "品牌一致性：是否符合品牌视觉规范",
    "字体字号：是否使用指定字体和允许字号",
    "图片质量：抠图、清晰度、色彩是否达标",
    "版式质量：是否接近参考图风格、是否美观",
    "文案准确性：是否与 brief 一致、是否有夸大",
    "Figma/PSD 可编辑性：图层是否清晰、文字是否可编辑"
  ],
  "feedback_capture": {
    "tracked_changes": [
      "模块隐藏/删除",
      "字体字号调整",
      "颜色调整",
      "文案修改",
      "图片替换"
    ],
    "learning_policy": "本阶段只记录设计师修改，不自动强化学习、不自动覆盖品牌规则。"
  }
};

var doc = app.documents.add(
  spec.canvas.width,
  spec.canvas.height,
  72,
  spec.project.name,
  NewDocumentMode.RGB,
  DocumentFill.WHITE
);

function hexColor(hex) {
  var c = new SolidColor();
  c.rgb.hexValue = String(hex).replace("#", "");
  return c;
}

function addText(group, name, text, x, y, size, hex) {
  if (!text) { return; }
  var layer = doc.artLayers.add();
  layer.kind = LayerKind.TEXT;
  layer.name = name;
  layer.textItem.contents = text;
  layer.textItem.position = [x, y];
  layer.textItem.size = size;
  layer.textItem.color = hexColor(hex);
  layer.move(group, ElementPlacement.INSIDE);
}

var y = 0;
var titleSize = spec.typography.title_size;
var bodySize = Math.max(12, spec.typography.body_size + 2);

for (var i = 0; i < spec.modules.length; i++) {
  var m = spec.modules[i];
  var copy = m.copy || {};
  var group = doc.layerSets.add();
  group.name = m.layer_group;

  addText(group, "TXT_主标题", copy.headline, 40, y + 60, titleSize + 6, spec.typography.text_color);
  addText(group, "TXT_副标题", copy.subtitle, 40, y + 110, spec.typography.subtitle_size, spec.canvas.accent_color);
  addText(group, "TXT_正文", copy.body, 40, y + 150, bodySize, "#4b5563");

  var points = copy.points || [];
  for (var p = 0; p < points.length; p++) {
    addText(group, "TXT_要点" + (p + 1), "· " + points[p], 40, y + 190 + p * 28, bodySize, "#374151");
  }

  if (m.image_file) {
    var scriptFile = new File($.fileName);
    var imageFile = new File(scriptFile.parent.fsName + "/" + m.image_file);
    if (imageFile.exists) {
      var imgDoc = app.open(imageFile);
      try {
        var imgLayer = imgDoc.activeLayer.duplicate(group, ElementPlacement.INSIDE);
        imgLayer.name = "IMG_" + (m.image_role || "图片");
        var imgX = Math.round(spec.canvas.width * 0.40);
        var imgTop = y + 150;
        var imgW = spec.canvas.width - imgX - 40;
        var imgH = m.height - 190;
        if (imgH > 80) {
          var bounds = imgLayer.bounds;
          var layerW = bounds[2].as("px") - bounds[0].as("px");
          var layerH = bounds[3].as("px") - bounds[1].as("px");
          if (layerW > 0 && layerH > 0) {
            var scale = Math.min(imgW / layerW, imgH / layerH) * 100;
            imgLayer.resize(scale, scale, AnchorPosition.MIDDLECENTER);
            bounds = imgLayer.bounds;
            imgLayer.translate(imgX - bounds[0].as("px"), imgTop - bounds[1].as("px"));
          }
        }
      } finally {
        imgDoc.close(SaveOptions.DONOTSAVECHANGES);
      }
    } else {
      var missing = doc.artLayers.add();
      missing.name = "IMG_MISSING_" + (m.image_role || "图片");
      missing.move(group, ElementPlacement.INSIDE);
    }
  } else {
    var placeholder = doc.artLayers.add();
    placeholder.name = "IMG_" + (m.image_role || "图片占位");
    placeholder.move(group, ElementPlacement.INSIDE);
  }

  y += m.height;
}
