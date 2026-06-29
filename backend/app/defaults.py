from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .prompts import DEFAULT_PROMPTS

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = PROJECT_ROOT / "config"
DEFAULT_CONFIG_PATH = CONFIG_DIR / "workflow-defaults.json"
LOCAL_CONFIG_PATH = CONFIG_DIR / "workflow-defaults.local.json"
SYSTEM_MODEL_CONFIG_PATH = CONFIG_DIR / "workflow-gpt.json"


def default_workflow_payload() -> dict[str, Any]:
    return {
        "project_name": "BrandOS 商品详情页设计任务",
        "brand_name": "ANKORAU × ANAR FC",
        "product_name": "电脑包",
        "product_brief": (
            "商品类型：电脑包\n"
            "核心卖点：轻量通勤、多分区收纳、防泼水、简洁商务风格\n"
            "使用场景：办公、通勤、短途旅行"
        ),
        "brand_guidelines": (
            "整体视觉保持简洁、克制、商务质感。\n"
            "页面宽度 790 像素，高度不限。\n"
            "标题字体 方正兰亭特黑简体 28 号，段落字体 方正兰亭黑简体 10 号，英文字体 AKR Sans。\n"
            "颜色以品牌黑、灰、白和低饱和浅色背景为主。"
        ),
        "reference_notes": "参考图作为 Asset Memory 进入品牌知识库，仅辅助生成，不直接覆盖 Core Rule。",
        "workflow_mode": "smart_recommend",
        "output_types": ["detail_page", "figma_page", "psd_file"],
        "model_config": {
            "provider": "openai",
            "model": "qwen-plus",
            "vision_model": "qwen-vl-max",
            "api_key": "",
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "temperature": 0.4,
            "max_tokens": 4096,
            "enable_deepagents": True,
            "enable_vision": True,
            "max_vision_images": 4,
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
            "letter_spacing": 0,
            "font_weight": "Medium",
            "text_color": "#1f2937",
            "lock_brand_typography": True,
        },
        "layout": {
            "canvas_width": 790,
            "module_count": 7,
            "hero_height": 1000,
            "module_height": 820,
            "visual_style": "简洁商务 / 浅色质感 / 接近参考图",
            "background_color": "#eef1f4",
            "accent_color": "#1f2937",
            "image_ratio": 0.62,
            "spacing_scale": 1.0,
        },
        "prompts": DEFAULT_PROMPTS.model_dump(),
    }


def _deep_merge(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in patch.items():
        current = merged.get(key)
        if isinstance(current, dict) and isinstance(value, dict):
            merged[key] = _deep_merge(current, value)
        else:
            merged[key] = value
    return merged


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"配置文件不是合法 JSON: {path}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"配置文件必须是 JSON object: {path}")
    return data


def load_workflow_defaults() -> dict[str, Any]:
    defaults = default_workflow_payload()
    file_defaults = _read_json(DEFAULT_CONFIG_PATH)
    local_overrides = _read_json(LOCAL_CONFIG_PATH)
    merged = _deep_merge(_deep_merge(defaults, file_defaults), local_overrides)
    merged["model_config"] = load_system_model_config()
    return merged


def load_system_model_config() -> dict[str, Any]:
    defaults = default_workflow_payload()
    file_config = _read_json(SYSTEM_MODEL_CONFIG_PATH)
    model_config = file_config.get("model_config")
    if isinstance(model_config, dict):
        return _deep_merge(defaults.get("model_config", {}), model_config)
    return dict(defaults.get("model_config", {}))
