from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel as PydanticBaseModel
from pydantic import Field


class BaseModel(PydanticBaseModel):
    @classmethod
    def model_validate(cls, obj: Any):
        if hasattr(super(), "model_validate"):
            return super().model_validate(obj)
        return cls.parse_obj(obj)

    def model_dump(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        if hasattr(super(), "model_dump"):
            return super().model_dump(*args, **kwargs)
        return self.dict(*args, **kwargs)

    def model_dump_json(self, *args: Any, **kwargs: Any) -> str:
        if hasattr(super(), "model_dump_json"):
            return super().model_dump_json(*args, **kwargs)
        return self.json(*args, **kwargs)


class WorkflowMode(str, Enum):
    strict_brand = "strict_brand"
    smart_recommend = "smart_recommend"


class OutputType(str, Enum):
    detail_page = "detail_page"
    figma_page = "figma_page"
    psd_file = "psd_file"
    main_image = "main_image"
    banner = "banner"


class ModelConfig(BaseModel):
    provider: str = Field(default="openai", description="LangChain 模型 provider")
    model: str = Field(default="qwen-plus", description="文本模型名称")
    vision_model: str = Field(default="qwen-vl-max", description="多模态视觉模型名称")
    api_key: str | None = Field(default=None, description="可选，优先于环境变量")
    base_url: str | None = Field(default=None, description="OpenAI compatible base url")
    temperature: float = Field(default=0.4, ge=0, le=2)
    max_tokens: int = Field(default=4096, ge=512, le=32000)
    enable_deepagents: bool = Field(default=True)
    enable_vision: bool = Field(default=True, description="是否用多模态模型真正读取图片")
    max_vision_images: int = Field(default=4, ge=1, le=12)


class TypographyConfig(BaseModel):
    title_font: str = "方正兰亭特黑简体"
    subtitle_font: str = "方正兰亭黑简体"
    body_font: str = "方正兰亭黑简体"
    english_font: str = "AKR Sans"
    title_size: int = Field(default=28, ge=12, le=160)
    subtitle_size: int = Field(default=18, ge=10, le=96)
    body_size: int = Field(default=10, ge=8, le=64)
    line_height: float = Field(default=1.5, ge=0.8, le=3)
    letter_spacing: float = Field(default=0, ge=-5, le=20)
    font_weight: Literal["Regular", "Medium", "Bold"] = "Medium"
    text_color: str = "#1f2937"
    lock_brand_typography: bool = True


class LayoutConfig(BaseModel):
    canvas_width: int = Field(default=790, ge=320, le=3000)
    module_count: int = Field(default=6, ge=1, le=12)
    hero_height: int = Field(default=1000, ge=400, le=2400)
    module_height: int = Field(default=820, ge=300, le=1800)
    visual_style: str = "简洁商务 / 浅色质感 / 接近参考图"
    background_color: str = "#eef1f4"
    accent_color: str = "#1f2937"
    image_ratio: float = Field(default=0.62, ge=0.2, le=0.9)
    spacing_scale: float = Field(default=1.0, ge=0.5, le=2.0)


class AgentPrompts(BaseModel):
    """对应图一中各 Agent 的可调提示词。"""

    system_prompt: str
    vision_agent_prompt: str
    structured_agent_prompt: str
    brand_rag_agent_prompt: str
    design_agent_prompt: str
    layout_agent_prompt: str
    copy_agent_prompt: str
    psd_agent_prompt: str


class RequirementConstraints(BaseModel):
    preferred_module_order: list[str] = Field(default_factory=list)
    required_modules: list[str] = Field(default_factory=list)
    forbidden_modules: list[str] = Field(default_factory=list)
    layout_constraints: list[str] = Field(default_factory=list)
    visual_constraints: list[str] = Field(default_factory=list)
    copy_constraints: list[str] = Field(default_factory=list)
    asset_constraints: list[str] = Field(default_factory=list)
    negative_constraints: list[str] = Field(default_factory=list)
    reference_alignment: str = ""
    apply_feedback_constraints: bool = True
    feedback_scope: Literal["none", "same_product", "same_brand", "run"] = "same_product"
    feedback_run_id: str | None = None


def _to_int(value: Any, default: int) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _to_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "y", "required"}:
            return True
        if lowered in {"0", "false", "no", "n", "optional"}:
            return False
    return bool(value)


def _coalesce(*values: Any) -> Any:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value
    return None


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    items: list[str] = []
    for raw in value:
        text = str(raw).strip()
        if text and text not in items:
            items.append(text)
    return items


def _layout_token(value: Any) -> str:
    text = str(value or "").strip().lower()
    for token in ("-", " ", "/", "\\"):
        text = text.replace(token, "_")
    while "__" in text:
        text = text.replace("__", "_")
    return text.strip("_")


_HERO_SECTION_ALIASES = {
    "hero",
    "hero_section",
    "hero_banner",
    "hero_slider",
    "hero_carousel",
    "main_image_area",
    "main_visual",
    "main_visual_area",
    "primary_visual",
    "product_display",
    "product_hero",
    "kv",
}

_HEADER_SECTION_ALIASES = {
    "navigation",
    "navbar",
    "header",
    "header_nav",
    "topbar",
    "top_bar",
    "top_nav",
}

_HERO_SECTION_MARKERS = ("首屏", "主图", "头图", "主视觉", "kv", "hero", "banner")


def _contains_layout_marker(value: Any, markers: tuple[str, ...]) -> bool:
    text = str(value or "").strip().lower()
    normalized = _layout_token(value)
    return any(marker in text or marker in normalized for marker in markers)


def _normalize_section_role(raw: dict[str, Any], index: int) -> str:
    role = str(raw.get("role") or "").strip()
    component_type = str(raw.get("component_type") or raw.get("componentType") or "").strip()
    section_id = str(raw.get("id") or "").strip()
    name = str(raw.get("name") or raw.get("title") or "").strip()
    candidates = [_layout_token(item) for item in (role, component_type, section_id, name) if str(item).strip()]
    if any(candidate in _HERO_SECTION_ALIASES for candidate in candidates):
        return "hero"
    if _contains_layout_marker(name, _HERO_SECTION_MARKERS) or _contains_layout_marker(
        section_id, _HERO_SECTION_MARKERS
    ):
        return "hero"
    if role:
        return role
    if component_type:
        return component_type
    return "hero" if index == 1 else "feature"


def _is_header_like_section(section: dict[str, Any]) -> bool:
    candidates = [
        _layout_token(section.get("role")),
        _layout_token(section.get("component_type")),
        _layout_token(section.get("id")),
        _layout_token(section.get("name")),
    ]
    return any(candidate in _HEADER_SECTION_ALIASES for candidate in candidates if candidate)


class LayoutImageSlot(BaseModel):
    id: str
    section_id: str
    role: str = "detail"
    asset_type: str = "detail"
    x: int = 0
    y: int = 0
    w: int = 1
    h: int = 1
    fit: str = "cover"
    crop: str = "center"
    priority: Literal["high", "medium", "low"] = "medium"
    required: bool = True
    semantic_tags: list[str] = Field(default_factory=list)

    class Config:
        extra = "allow"


class LayoutTextLayer(BaseModel):
    id: str
    section_id: str
    role: str = "body"
    text: str = ""
    x: int = 0
    y: int = 0
    w: int = 160
    h: int = 28
    font: str = ""
    font_size: int | None = None

    class Config:
        extra = "allow"


class LayoutSection(BaseModel):
    id: str
    name: str
    role: str = "feature"
    component_type: str = "feature"
    order: int = 1
    x: int = 0
    y: int = 0
    w: int = 790
    h: int = 820
    min_height: int | None = None
    max_height: int | None = None
    background: dict[str, Any] = Field(default_factory=dict)
    required_text_fields: list[str] = Field(default_factory=list)
    optional_text_fields: list[str] = Field(default_factory=list)
    required_image_slots: list[str] = Field(default_factory=list)
    optional_image_slots: list[str] = Field(default_factory=list)

    class Config:
        extra = "allow"


class LayoutSchema(BaseModel):
    schema_version: str = "brandos_layout_schema.v1"
    page_type: str = "detail_page"
    canvas: dict[str, Any] = Field(default_factory=lambda: {"width": 790, "height_mode": "auto"})
    sections: list[LayoutSection] = Field(default_factory=list)
    image_slots: list[LayoutImageSlot] = Field(default_factory=list)
    text_layers: list[LayoutTextLayer] = Field(default_factory=list)
    component_templates: list[dict[str, Any]] = Field(default_factory=list)
    global_constraints: dict[str, Any] = Field(default_factory=dict)
    source_rule_id: int | None = None
    source_version: str | None = None

    class Config:
        extra = "allow"


def normalize_layout_schema_payload(
    payload: Any,
    detached_image_slots: Any | None = None,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}

    raw_sections = payload.get("sections")
    raw_slots = payload.get("image_slots") or payload.get("imageSlots")
    raw_text_layers = payload.get("text_layers") or payload.get("textLayers")
    if not isinstance(raw_sections, list):
        raw_sections = []
    if not isinstance(raw_slots, list):
        raw_slots = detached_image_slots if isinstance(detached_image_slots, list) else []
    elif not raw_slots and isinstance(detached_image_slots, list):
        raw_slots = detached_image_slots
    if not isinstance(raw_text_layers, list):
        raw_text_layers = []

    normalized_sections: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_sections, start=1):
        if not isinstance(raw, dict):
            continue
        role = _normalize_section_role(raw, index)
        section_id = str(raw.get("id") or f"section_{index:02d}_{role}").strip()
        section_payload = {
            **raw,
            "id": section_id,
            "name": str(raw.get("name") or raw.get("title") or section_id).strip(),
            "role": role,
            "component_type": str(raw.get("component_type") or raw.get("componentType") or role).strip() or role,
            "order": _to_int(_coalesce(raw.get("order"), raw.get("index")), index),
            "x": _to_int(raw.get("x"), 0),
            "y": _to_int(raw.get("y"), 0),
            "w": max(1, _to_int(raw.get("w") or raw.get("width"), 790)),
            "h": max(1, _to_int(raw.get("h") or raw.get("height"), 820)),
            "min_height": _to_int(raw.get("min_height") or raw.get("minHeight"), 0) or None,
            "max_height": _to_int(raw.get("max_height") or raw.get("maxHeight"), 0) or None,
            "background": raw.get("background") if isinstance(raw.get("background"), dict) else {},
            "required_text_fields": _string_list(raw.get("required_text_fields") or raw.get("requiredTextFields")),
            "optional_text_fields": _string_list(raw.get("optional_text_fields") or raw.get("optionalTextFields")),
            "required_image_slots": _string_list(raw.get("required_image_slots") or raw.get("requiredImageSlots")),
            "optional_image_slots": _string_list(raw.get("optional_image_slots") or raw.get("optionalImageSlots")),
        }
        normalized_sections.append(section_payload)

    normalized_slots: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_slots, start=1):
        if not isinstance(raw, dict):
            continue
        role = str(raw.get("role") or raw.get("asset_type") or raw.get("assetType") or "detail").strip() or "detail"
        slot_payload = {
            **raw,
            "id": str(raw.get("id") or raw.get("slot_id") or f"slot_{index:02d}_{role}").strip(),
            "section_id": str(raw.get("section_id") or raw.get("sectionId") or "").strip(),
            "role": role,
            "asset_type": str(raw.get("asset_type") or raw.get("assetType") or role).strip() or role,
            "x": _to_int(raw.get("x"), 0),
            "y": _to_int(raw.get("y"), 0),
            "w": max(1, _to_int(raw.get("w") or raw.get("width"), 1)),
            "h": max(1, _to_int(raw.get("h") or raw.get("height"), 1)),
            "fit": str(raw.get("fit") or "cover").strip() or "cover",
            "crop": str(raw.get("crop") or "center").strip() or "center",
            "priority": (
                str(raw.get("priority") or ("high" if role in {"hero", "product_gallery"} else "medium")).strip().lower()
            ),
            "required": _to_bool(raw.get("required"), True),
            "semantic_tags": _string_list(raw.get("semantic_tags") or raw.get("semanticTags")),
        }
        if slot_payload["priority"] not in {"high", "medium", "low"}:
            slot_payload["priority"] = "medium"
        normalized_slots.append(slot_payload)

    normalized_text_layers: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_text_layers, start=1):
        if not isinstance(raw, dict):
            continue
        normalized_text_layers.append(
            {
                **raw,
                "id": str(raw.get("id") or f"text_{index:02d}").strip(),
                "section_id": str(raw.get("section_id") or raw.get("sectionId") or "").strip(),
                "role": str(raw.get("role") or "body").strip() or "body",
                "text": str(raw.get("text") or "").strip(),
                "x": _to_int(raw.get("x"), 0),
                "y": _to_int(raw.get("y"), 0),
                "w": max(1, _to_int(raw.get("w") or raw.get("width"), 160)),
                "h": max(1, _to_int(raw.get("h") or raw.get("height"), 28)),
                "font": str(raw.get("font") or "").strip(),
                "font_size": (_to_int(raw.get("font_size") or raw.get("fontSize"), 0) or None),
            }
        )

    slot_ids_by_section: dict[str, list[str]] = {}
    optional_slot_ids_by_section: dict[str, list[str]] = {}
    for slot in normalized_slots:
        section_id = str(slot.get("section_id") or "")
        if not section_id:
            continue
        target = slot_ids_by_section if bool(slot.get("required", True)) else optional_slot_ids_by_section
        target.setdefault(section_id, []).append(str(slot.get("id") or ""))

    for section in normalized_sections:
        section_id = str(section.get("id") or "")
        if not section["required_image_slots"] and section_id in slot_ids_by_section:
            section["required_image_slots"] = slot_ids_by_section[section_id]
        if not section["optional_image_slots"] and section_id in optional_slot_ids_by_section:
            section["optional_image_slots"] = optional_slot_ids_by_section[section_id]

    normalized_sections.sort(key=lambda item: (int(item.get("order") or 0), str(item.get("id") or "")))

    model = LayoutSchema.model_validate(
        {
            **payload,
            "schema_version": str(payload.get("schema_version") or payload.get("schemaVersion") or "brandos_layout_schema.v1"),
            "page_type": str(payload.get("page_type") or payload.get("pageType") or "detail_page"),
            "canvas": payload.get("canvas") if isinstance(payload.get("canvas"), dict) else {"width": 790, "height_mode": "auto"},
            "sections": normalized_sections,
            "image_slots": normalized_slots,
            "text_layers": normalized_text_layers,
            "component_templates": payload.get("component_templates") if isinstance(payload.get("component_templates"), list) else payload.get("componentTemplates") or [],
            "global_constraints": payload.get("global_constraints") if isinstance(payload.get("global_constraints"), dict) else payload.get("globalConstraints") or {},
            "source_rule_id": payload.get("source_rule_id") or payload.get("sourceRuleId"),
            "source_version": payload.get("source_version") or payload.get("sourceVersion"),
        }
    )
    return model.model_dump()


def _raw_list_payload(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _missing_raw_fields(
    items: list[dict[str, Any]],
    field_groups: list[tuple[str, tuple[str, ...]]],
) -> list[str]:
    def has_value(item: dict[str, Any], key: str) -> bool:
        value = item.get(key)
        if value is None:
            return False
        if isinstance(value, str):
            return bool(value.strip())
        return True

    missing: list[str] = []
    for index, item in enumerate(items, start=1):
        absent = [
            label
            for label, keys in field_groups
            if not any(has_value(item, key) for key in keys)
        ]
        if absent:
            missing.append(f"{index}:{','.join(absent)}")
    return missing


def validate_layout_schema_payload(
    payload: Any,
    detached_image_slots: Any | None = None,
    require_explicit_training_fields: bool = False,
) -> dict[str, Any]:
    issues: list[str] = []
    warnings: list[str] = []
    if not isinstance(payload, dict):
        return {
            "status": "failed",
            "issues": ["layout_schema 必须是 JSON 对象"],
            "warnings": [],
            "section_count": 0,
            "image_slot_count": 0,
            "high_priority_slot_count": 0,
            "required_slot_count": 0,
            "hero_section_count": 0,
            "normalized_schema": {},
        }

    raw_sections = _raw_list_payload(payload.get("sections"))
    inline_raw_slots = _raw_list_payload(payload.get("image_slots") or payload.get("imageSlots"))
    detached_raw_slots = _raw_list_payload(detached_image_slots)
    raw_slots = inline_raw_slots or detached_raw_slots
    raw_text_layers = _raw_list_payload(payload.get("text_layers") or payload.get("textLayers"))

    if require_explicit_training_fields:
        if not raw_sections:
            issues.append("训练结果缺少显式 sections 数组")
        if not raw_slots:
            issues.append("训练结果缺少显式 image_slots 数组")
        section_missing = _missing_raw_fields(
            raw_sections,
            [
                ("id", ("id",)),
                ("name", ("name", "title")),
                ("role", ("role", "component_type", "componentType")),
                ("order", ("order", "index")),
                ("x", ("x",)),
                ("y", ("y",)),
                ("w", ("w", "width")),
                ("h", ("h", "height")),
            ],
        )
        if section_missing:
            issues.append(
                "sections 存在缺失关键字段的项："
                + "；".join(section_missing[:6])
            )
        slot_missing = _missing_raw_fields(
            raw_slots,
            [
                ("id", ("id", "slot_id")),
                ("section_id", ("section_id", "sectionId")),
                ("role", ("role", "asset_type", "assetType")),
                ("x", ("x",)),
                ("y", ("y",)),
                ("w", ("w", "width")),
                ("h", ("h", "height")),
            ],
        )
        if slot_missing:
            issues.append(
                "image_slots 存在缺失关键字段的项："
                + "；".join(slot_missing[:6])
            )

    if inline_raw_slots and detached_raw_slots:
        inline_ids = {str(item.get("id") or item.get("slot_id") or "").strip() for item in inline_raw_slots}
        detached_ids = {str(item.get("id") or item.get("slot_id") or "").strip() for item in detached_raw_slots}
        if inline_ids != detached_ids:
            warnings.append("layout_schema.image_slots 与独立 image_slots 字段不一致，已以 schema 内结果为准")

    normalized_schema = normalize_layout_schema_payload(payload, detached_image_slots=detached_image_slots)
    sections = [item for item in normalized_schema.get("sections", []) if isinstance(item, dict)]
    slots = [item for item in normalized_schema.get("image_slots", []) if isinstance(item, dict)]
    text_layers = [item for item in normalized_schema.get("text_layers", []) if isinstance(item, dict)]

    if not sections:
        issues.append("layout_schema 归一化后缺少 sections")
    if not slots:
        issues.append("layout_schema 归一化后缺少 image_slots")

    canvas = normalized_schema.get("canvas")
    if not isinstance(canvas, dict):
        issues.append("layout_schema 缺少 canvas 配置")
    else:
        try:
            if int(canvas.get("width") or 0) <= 0:
                issues.append("layout_schema.canvas.width 必须大于 0")
        except (TypeError, ValueError):
            issues.append("layout_schema.canvas.width 必须是数字")

    section_ids = [str(item.get("id") or "").strip() for item in sections]
    valid_section_ids = {item for item in section_ids if item}
    if len(valid_section_ids) != len(sections):
        issues.append("sections 存在重复或空的 section id")

    section_orders: list[int] = []
    for section in sections:
        try:
            section_orders.append(int(section.get("order") or 0))
        except (TypeError, ValueError):
            section_orders.append(0)
    if sections and (sorted(section_orders) != section_orders or len(set(section_orders)) != len(section_orders)):
        issues.append("sections.order 必须稳定递增且不可重复")

    hero_sections = [
        section
        for section in sections
        if str(section.get("role") or section.get("component_type") or "").strip() == "hero"
    ]
    if not hero_sections:
        issues.append("layout_schema 缺少 Hero section")
    else:
        content_sections = list(sections)
        while content_sections and _is_header_like_section(content_sections[0]):
            content_sections.pop(0)
        if (
            content_sections
            and str(content_sections[0].get("role") or content_sections[0].get("component_type") or "").strip()
            != "hero"
        ):
            issues.append("Hero section 必须位于首个 section")

    slot_ids = [str(item.get("id") or "").strip() for item in slots]
    valid_slot_ids = {item for item in slot_ids if item}
    if len(valid_slot_ids) != len(slots):
        issues.append("image_slots 存在重复或空的 slot id")

    invalid_slot_refs = [
        str(slot.get("id") or f"slot_{index}")
        for index, slot in enumerate(slots, start=1)
        if str(slot.get("section_id") or "").strip() not in valid_section_ids
    ]
    if invalid_slot_refs:
        issues.append("image_slots 引用了不存在的 section：" + "、".join(invalid_slot_refs[:6]))

    required_slots = [
        slot
        for slot in slots
        if bool(slot.get("required", True)) or str(slot.get("priority") or "").lower() == "high"
    ]
    if not required_slots:
        issues.append("layout_schema 缺少 required / high priority 图片槽")

    slots_by_section: dict[str, set[str]] = {}
    for slot in slots:
        section_id = str(slot.get("section_id") or "").strip()
        slot_id = str(slot.get("id") or "").strip()
        if section_id and slot_id:
            slots_by_section.setdefault(section_id, set()).add(slot_id)

    for index, section in enumerate(sections, start=1):
        section_id = str(section.get("id") or "").strip()
        section_role = str(section.get("role") or section.get("component_type") or "").strip()
        required_image_slots = _string_list(section.get("required_image_slots"))
        missing_refs = [slot_id for slot_id in required_image_slots if slot_id not in valid_slot_ids]
        if missing_refs:
            issues.append(
                f"section[{index}] required_image_slots 引用了不存在的槽位："
                + "、".join(missing_refs[:6])
            )
        foreign_refs = [
            slot_id
            for slot_id in required_image_slots
            if slot_id in valid_slot_ids and slot_id not in slots_by_section.get(section_id, set())
        ]
        if foreign_refs:
            issues.append(
                f"section[{index}] required_image_slots 存在跨 section 槽位引用："
                + "、".join(foreign_refs[:6])
            )
        if section_role not in {"cta"} and not _is_header_like_section(section) and not slots_by_section.get(section_id):
            warnings.append(f"section[{index}] 未绑定任何 image_slot")

    for index, layer in enumerate(text_layers, start=1):
        section_id = str(layer.get("section_id") or "").strip()
        if section_id and section_id not in valid_section_ids:
            issues.append(f"text_layers[{index}] 引用了不存在的 section_id={section_id}")

    status = "failed" if issues else ("warning" if warnings else "passed")
    return {
        "status": status,
        "issues": issues,
        "warnings": warnings,
        "section_count": len(sections),
        "image_slot_count": len(slots),
        "high_priority_slot_count": len(
            [slot for slot in slots if str(slot.get("priority") or "").lower() == "high"]
        ),
        "required_slot_count": len([slot for slot in slots if bool(slot.get("required", True))]),
        "hero_section_count": len(hero_sections),
        "normalized_schema": normalized_schema,
    }


def _stage_text(value: Any) -> str:
    return str(value or "").strip()


def _stage_text_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    items: list[str] = []
    for raw in value:
        if isinstance(raw, str):
            text = raw.strip()
        elif isinstance(raw, dict):
            text = str(
                raw.get("title")
                or raw.get("name")
                or raw.get("label")
                or raw.get("description")
                or raw.get("text")
                or ""
            ).strip()
        else:
            text = str(raw).strip()
        if text and text not in items:
            items.append(text)
    return items


def _stage_positive_int(value: Any, default: int) -> int:
    try:
        parsed = int(float(value))
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _stage_contract_items(value: Any, key: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _default_generated_name(index: int, role: str) -> str:
    suffix = Path(str(role or "detail")).stem.replace(" ", "_").replace("-", "_") or "detail"
    return f"generated_{index:02d}_{suffix}.svg"


_STAGE_CONTRACT_CONTROL_KEYS = {
    "_expected_block_count",
    "_expected_image_count",
    "_module_contracts",
    "_slot_plan",
    "_require_slot_bindings",
}


_STAGE_CONTRACT_ERROR_CATALOG: dict[str, dict[str, str]] = {
    "invalid_payload_type": {
        "error_category": "schema",
        "error_family": "type",
    },
    "invalid_field_type": {
        "error_category": "schema",
        "error_family": "type",
    },
    "missing_required_array": {
        "error_category": "schema",
        "error_family": "missing",
    },
    "missing_required_fields": {
        "error_category": "contract",
        "error_family": "missing",
    },
    "count_mismatch": {
        "error_category": "contract",
        "error_family": "count",
    },
    "invalid_reference": {
        "error_category": "reference",
        "error_family": "invalid",
    },
    "duplicate_identifier": {
        "error_category": "schema",
        "error_family": "identifier",
    },
    "contract_violation": {
        "error_category": "contract",
        "error_family": "generic",
    },
    "unknown_stage": {
        "error_category": "unknown",
        "error_family": "unsupported_stage",
    },
}


def get_stage_contract_error_info(error_code: str) -> dict[str, str]:
    normalized_code = str(error_code or "contract_violation").strip() or "contract_violation"
    base = _STAGE_CONTRACT_ERROR_CATALOG.get(
        normalized_code,
        {
            "error_category": "unknown",
            "error_family": "generic",
        },
    )
    return {
        "error_code": normalized_code,
        "error_category": str(base.get("error_category") or "unknown"),
        "error_family": str(base.get("error_family") or "generic"),
    }


class StagePayloadValidationError(ValueError):
    """阶段 contract 校验失败，携带可供重试策略消费的错误码。"""

    def __init__(
        self,
        message: str,
        *,
        error_code: str = "contract_violation",
        issues: list[str] | None = None,
        error_category: str | None = None,
        error_family: str | None = None,
    ) -> None:
        super().__init__(message)
        info = get_stage_contract_error_info(error_code)
        self.error_code = info["error_code"]
        self.error_category = (
            str(error_category or "").strip() or info["error_category"]
        )
        self.error_family = str(error_family or "").strip() or info["error_family"]
        self.issues = list(issues or [])


def _classify_stage_contract_error_code(issues: list[str]) -> str:
    if any(
        ("不是对象" in issue)
        or ("类型错误" in issue)
        or ("必须是数字" in issue)
        or ("必须是字符串" in issue)
        for issue in issues
    ):
        return "invalid_field_type"
    if any("数量" in issue for issue in issues):
        return "count_mismatch"
    if any(
        ("不存在" in issue) or ("跨 section" in issue) or ("引用" in issue)
        for issue in issues
    ):
        return "invalid_reference"
    if any("重复" in issue for issue in issues):
        return "duplicate_identifier"
    if any(
        ("缺少" in issue)
        or ("为空" in issue)
        or ("必填字段" in issue)
        or ("至少需要" in issue)
        for issue in issues
    ):
        return "missing_required_fields"
    return "contract_violation"


def validate_stage_contract_payload(stage_id: str, payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise StagePayloadValidationError(
            f"{stage_id} 输出必须是 JSON 对象",
            error_code="invalid_payload_type",
            issues=[f"{stage_id} 输出必须是 JSON 对象"],
        )

    normalized = dict(payload)
    issues: list[str] = []

    if stage_id == "product_brief":
        normalized["brand"] = _stage_text(payload.get("brand"))
        normalized["product"] = _stage_text(payload.get("product"))
        normalized["audience"] = _stage_text(payload.get("audience"))
        normalized["selling_points"] = _stage_text_list(payload.get("selling_points"))
        normalized["specifications"] = (
            dict(payload.get("specifications"))
            if isinstance(payload.get("specifications"), dict)
            else {}
        )
        normalized["scenarios"] = _stage_text_list(payload.get("scenarios"))
        normalized["design_focus"] = _stage_text(payload.get("design_focus"))
        if not normalized["brand"]:
            issues.append("缺少 brand")
        if not normalized["product"]:
            issues.append("缺少 product")
        if not normalized["audience"]:
            issues.append("缺少 audience")
        if not normalized["selling_points"]:
            issues.append("缺少 selling_points")
        if not normalized["design_focus"]:
            issues.append("缺少 design_focus")
    elif stage_id == "brand_knowledge":
        fonts = payload.get("fonts") if isinstance(payload.get("fonts"), dict) else {}
        normalized["version"] = _stage_text(payload.get("version"))
        normalized["rule_status"] = _stage_text(payload.get("rule_status"))
        normalized["core_rule"] = (
            dict(payload.get("core_rule"))
            if isinstance(payload.get("core_rule"), dict)
            else {}
        )
        normalized["derived_rule"] = (
            dict(payload.get("derived_rule"))
            if isinstance(payload.get("derived_rule"), dict)
            else {}
        )
        normalized["asset_memory"] = (
            dict(payload.get("asset_memory"))
            if isinstance(payload.get("asset_memory"), dict)
            else {}
        )
        normalized["rule_weights"] = (
            dict(payload.get("rule_weights"))
            if isinstance(payload.get("rule_weights"), dict)
            else {}
        )
        normalized["drift_risks"] = _stage_text_list(payload.get("drift_risks"))
        normalized["brand_style"] = _stage_text(payload.get("brand_style"))
        normalized["primary_color"] = _stage_text(payload.get("primary_color"))
        normalized["secondary_colors"] = _stage_text_list(payload.get("secondary_colors"))
        normalized["fonts"] = {
            "title": _stage_text(fonts.get("title")),
            "body": _stage_text(fonts.get("body")),
            "english": _stage_text(fonts.get("english")),
        }
        normalized["layout_rules"] = _stage_text_list(payload.get("layout_rules"))
        normalized["component_patterns"] = _stage_text_list(
            payload.get("component_patterns")
        )
        normalized["prompt_templates"] = _stage_text_list(
            payload.get("prompt_templates")
        )
        normalized["module_order"] = _stage_text_list(payload.get("module_order"))
        if not normalized["version"]:
            issues.append("缺少 version")
        if not normalized["core_rule"]:
            issues.append("缺少 core_rule")
        if not normalized["derived_rule"]:
            issues.append("缺少 derived_rule")
        if not normalized["brand_style"]:
            issues.append("缺少 brand_style")
        if not normalized["primary_color"]:
            issues.append("缺少 primary_color")
        if not normalized["fonts"]["title"] or not normalized["fonts"]["body"]:
            issues.append("fonts 至少需要 title/body")
        if not normalized["module_order"]:
            issues.append("缺少 module_order")
    elif stage_id == "page_planner":
        normalized["direction"] = _stage_text(payload.get("direction"))
        normalized["page_template"] = _stage_text_list(payload.get("page_template"))
        normalized["information_architecture"] = _stage_text_list(
            payload.get("information_architecture")
        )
        normalized["tone"] = _stage_text(payload.get("tone"))
        normalized["image_strategy"] = _stage_text(payload.get("image_strategy"))
        normalized["brand_constraints"] = _stage_text_list(
            payload.get("brand_constraints")
        )
        normalized["risks"] = _stage_text_list(payload.get("risks"))
        if not normalized["direction"]:
            issues.append("缺少 direction")
        if not normalized["page_template"]:
            issues.append("缺少 page_template")
        if not normalized["information_architecture"]:
            issues.append("缺少 information_architecture")
        if not normalized["tone"]:
            issues.append("缺少 tone")
        if not normalized["image_strategy"]:
            issues.append("缺少 image_strategy")
    elif stage_id == "layout_engine":
        raw_modules = payload.get("modules")
        if not isinstance(raw_modules, list) or not raw_modules:
            raise StagePayloadValidationError(
                "缺少 modules 数组",
                error_code="missing_required_array",
                issues=["缺少 modules 数组"],
            )
        normalized_modules: list[dict[str, Any]] = []
        for index, raw in enumerate(raw_modules, start=1):
            if not isinstance(raw, dict):
                issues.append(f"modules[{index}] 不是对象")
                continue
            role = _stage_text(raw.get("role")) or ("hero" if index == 1 else "feature")
            name = _stage_text(raw.get("name")) or f"模块{index}"
            layer_group = _stage_text(raw.get("layer_group")) or f"{index:02d}_{role}"
            layout = _stage_text(raw.get("layout")) or "image_text"
            elements = _stage_text_list(raw.get("elements")) or [
                "BG_背景",
                "IMG_图片",
                "TXT_标题",
            ]
            height = _to_int(raw.get("height"), 1000 if index == 1 else 820)
            normalized_modules.append(
                {
                    **raw,
                    "name": name,
                    "layer_group": layer_group,
                    "layout": layout,
                    "height": max(220, min(height, 5000)),
                    "role": role,
                    "image_role": _stage_text(raw.get("image_role")) or role,
                    "elements": elements,
                }
            )
        normalized["modules"] = normalized_modules
        if not normalized_modules:
            issues.append("modules 归一化后为空")
    elif stage_id == "image_generation":
        raw_images = payload.get("images")
        if not isinstance(raw_images, list) or not raw_images:
            raise StagePayloadValidationError(
                "缺少 images 数组",
                error_code="missing_required_array",
                issues=["缺少 images 数组"],
            )
        slot_plan = _stage_contract_items(payload.get("_slot_plan"), "_slot_plan")
        require_slot_bindings = bool(payload.get("_require_slot_bindings"))
        expected_image_count = _stage_positive_int(payload.get("_expected_image_count"), 0)
        normalized_images: list[dict[str, Any]] = []
        seen_names: set[str] = set()
        for index, raw in enumerate(raw_images, start=1):
            if not isinstance(raw, dict):
                issues.append(f"images[{index}] 不是对象")
                continue
            role = _stage_text(raw.get("role") or raw.get("image_role"))
            image_role = _stage_text(raw.get("image_role") or role)
            name = _stage_text(raw.get("name"))
            if not name:
                name = _default_generated_name(index, role or image_role or "detail")
            elif not Path(name).suffix:
                name = f"{name}.svg"
            module_name = _stage_text(raw.get("module_name"))
            prompt = _stage_text(raw.get("prompt"))
            slot_id = _stage_text(raw.get("slot_id"))
            section_id = _stage_text(raw.get("section_id"))
            normalized_images.append(
                {
                    **raw,
                    "name": name,
                    "slot_id": slot_id,
                    "section_id": section_id,
                    "module_index": _stage_positive_int(raw.get("module_index"), index),
                    "module_name": module_name,
                    "role": role,
                    "image_role": image_role or role,
                    "source": _stage_text(raw.get("source")) or "ai_generated",
                    "prompt": prompt,
                }
            )
            if not role:
                issues.append(f"images[{index}] 缺少 role")
            if not module_name:
                issues.append(f"images[{index}] 缺少 module_name")
            if not prompt:
                issues.append(f"images[{index}] 缺少 prompt")
            if name in seen_names:
                issues.append(f"images[{index}] name 重复：{name}")
            seen_names.add(name)
            if require_slot_bindings and not slot_id:
                issues.append(f"images[{index}] 缺少 slot_id")
            if require_slot_bindings and not section_id:
                issues.append(f"images[{index}] 缺少 section_id")
        if expected_image_count and len(normalized_images) < expected_image_count:
            issues.append(
                f"images 数量不足，期望至少 {expected_image_count} 条，实际 {len(normalized_images)} 条"
            )
        if slot_plan:
            expected_required_slot_ids = {
                _stage_text(item.get("slot_id"))
                for item in slot_plan
                if (
                    (_stage_text(item.get("role")) not in {"brand_story", "cta", "interaction"})
                    and (
                        bool(item.get("required"))
                        or _stage_text(item.get("priority")).lower() == "high"
                    )
                    and _stage_text(item.get("slot_id"))
                )
            }
            produced_slot_ids = {
                str(item.get("slot_id") or "").strip()
                for item in normalized_images
                if str(item.get("slot_id") or "").strip()
            }
            missing_slot_ids = sorted(expected_required_slot_ids - produced_slot_ids)
            if missing_slot_ids:
                issues.append(
                    "images 未覆盖关键 slot_id："
                    + "、".join(missing_slot_ids[:8])
                )
        normalized["images"] = normalized_images
    elif stage_id == "copy":
        raw_blocks = payload.get("blocks")
        if not isinstance(raw_blocks, list) or not raw_blocks:
            raise StagePayloadValidationError(
                "缺少 blocks 数组",
                error_code="missing_required_array",
                issues=["缺少 blocks 数组"],
            )
        expected_block_count = _stage_positive_int(payload.get("_expected_block_count"), 0)
        module_contracts = _stage_contract_items(payload.get("_module_contracts"), "_module_contracts")
        normalized_blocks: list[dict[str, Any]] = []
        for index, raw in enumerate(raw_blocks, start=1):
            if not isinstance(raw, dict):
                issues.append(f"blocks[{index}] 不是对象")
                continue
            normalized_block = {
                **raw,
                "headline": _stage_text(raw.get("headline")),
                "subtitle": _stage_text(raw.get("subtitle")),
                "body": _stage_text(raw.get("body")),
                "points": _stage_text_list(raw.get("points")),
            }
            normalized_blocks.append(normalized_block)
            if not normalized_block["headline"]:
                issues.append(f"blocks[{index}] 缺少 headline")
        if expected_block_count and len(normalized_blocks) != expected_block_count:
            issues.append(
                f"blocks 数量必须与模块数一致，期望 {expected_block_count} 条，实际 {len(normalized_blocks)} 条"
            )
        for index, contract in enumerate(module_contracts, start=1):
            if index > len(normalized_blocks):
                break
            block = normalized_blocks[index - 1]
            required_fields = _stage_text_list(contract.get("required_text_fields"))
            missing_fields = [
                field_name
                for field_name in required_fields
                if (
                    (field_name == "points" and not _stage_text_list(block.get("points")))
                    or (
                        field_name != "points"
                        and not _stage_text(block.get(field_name))
                    )
                )
            ]
            if missing_fields:
                module_name = _stage_text(contract.get("name")) or f"module[{index}]"
                issues.append(
                    f"blocks[{index}] 缺少 {module_name} 必填字段："
                    + "、".join(missing_fields)
                )
        normalized["blocks"] = normalized_blocks
    else:
        raise StagePayloadValidationError(
            f"未知阶段结构校验：{stage_id}",
            error_code="unknown_stage",
            issues=[f"未知阶段结构校验：{stage_id}"],
        )

    for key in _STAGE_CONTRACT_CONTROL_KEYS:
        normalized.pop(key, None)
    if issues:
        normalized_issues = issues[:8]
        raise StagePayloadValidationError(
            "；".join(normalized_issues),
            error_code=_classify_stage_contract_error_code(normalized_issues),
            issues=normalized_issues,
        )
    return normalized


class WorkflowRequest(BaseModel):
    project_name: str = "详情页自动生成"
    brand_name: str = "ANKORAU × ANAR FC"
    product_name: str = "电脑包"
    product_brief: str = ""
    brand_guidelines: str = ""
    reference_notes: str = ""
    selected_core_rule_id: int | None = None
    selected_detail_page_rule_id: int | None = None
    workflow_mode: WorkflowMode = WorkflowMode.smart_recommend
    output_types: list[OutputType] = Field(
        default_factory=lambda: [OutputType.detail_page]
    )
    model_settings: ModelConfig = Field(
        default_factory=ModelConfig,
        alias="model_config",
    )
    typography: TypographyConfig = Field(default_factory=TypographyConfig)
    layout: LayoutConfig = Field(default_factory=LayoutConfig)
    requirement_constraints: RequirementConstraints = Field(
        default_factory=RequirementConstraints
    )
    prompts: AgentPrompts

    class Config:
        allow_population_by_field_name = True


class UploadedAsset(BaseModel):
    name: str
    content_type: str | None = None
    size: int = 0
    saved_path: str | None = None
    extracted_text: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    bucket: str = "reference"


StageStatus = Literal["completed", "fallback", "skipped", "failed"]


class StageResult(BaseModel):
    """图一中每个节点对应的一次执行结果。"""

    id: str
    title: str
    icon: str = "sparkles"
    status: StageStatus
    summary: str = ""
    detail: str = ""
    data: dict[str, Any] = Field(default_factory=dict)
    used_model: bool = False
    elapsed_ms: int = 0
    started_at: str | None = None
    completed_at: str | None = None
    duration_ms: int = 0
    error_code: str = ""
    retry: dict[str, Any] = Field(default_factory=dict)


class WorkflowArtifacts(BaseModel):
    run_id: str
    output_dir: str
    preview_svg: str
    design_spec: str
    photoshop_jsx: str
    figma_plugin: str
    figma_url: str | None = None
    export_status: str | None = None
    export_mode: str | None = None
    export_error: str | None = None
    output_metadata: str | None = None
    result_tier: str | None = None
    tier_code: str | None = None
    delivery_status: str | None = None
    error_code: str | None = None
    reason_codes: list[str] = Field(default_factory=list)
    warning_codes: list[str] = Field(default_factory=list)
    export_preflight: dict[str, Any] = Field(default_factory=dict)
    export_review: dict[str, Any] = Field(default_factory=dict)
    result_state: dict[str, Any] = Field(default_factory=dict)
    editable_html: str
    readme: str


class WorkflowResult(BaseModel):
    run_id: str
    status: Literal["completed", "fallback_completed", "failed"]
    summary: str
    used_deepagents: bool
    stages: list[StageResult]
    agent_report: str
    design_spec: dict[str, Any]
    artifacts: WorkflowArtifacts
    result_state: dict[str, Any] = Field(default_factory=dict)
    export_review: dict[str, Any] = Field(default_factory=dict)
    assets: list[UploadedAsset]
    warnings: list[str] = Field(default_factory=list)
