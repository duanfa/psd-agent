from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from . import database
from .llm import LLMClient, LLMUnavailable
from .models import StageResult, UploadedAsset, WorkflowRequest
from .runtime import append_log, append_stage_result, reset_run, set_run_state


class WorkflowCancelled(Exception):
    """用户主动中断工作流。"""


# ----------------------------- 素材归类 -----------------------------

IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp")
FONT_EXT = (".ttf", ".otf", ".woff", ".woff2")
VIDEO_EXT = (".mp4", ".mov", ".avi", ".mkv")
BRIEF_EXT = (".xlsx", ".xls", ".csv")


def classify_asset(name: str, content_type: str | None) -> str:
    lower = name.lower()
    ctype = (content_type or "").lower()
    if ctype.startswith("image/") or lower.endswith(IMAGE_EXT):
        return "image"
    if lower.endswith(BRIEF_EXT):
        return "brief"
    if lower.endswith(FONT_EXT):
        return "font"
    if ctype.startswith("video/") or lower.endswith(VIDEO_EXT):
        return "video"
    return "reference"


def summarize_assets(assets: list[UploadedAsset]) -> dict[str, list[str]]:
    buckets: dict[str, list[str]] = {
        "image": [],
        "brief": [],
        "reference_image": [],
        "font": [],
        "video": [],
        "reference": [],
    }
    for asset in assets:
        buckets.setdefault(asset.bucket, []).append(asset.name)
    return buckets


# ----------------------------- 流水线上下文 -----------------------------


@dataclass
class PipelineContext:
    request: WorkflowRequest
    assets: list[UploadedAsset]
    llm: LLMClient
    run_id: str = ""
    cancel_checker: Callable[[], bool] = lambda: False
    warnings: list[str] = field(default_factory=list)
    product_info: dict[str, Any] = field(default_factory=dict)
    structured_info: dict[str, Any] = field(default_factory=dict)
    brand_profile: dict[str, Any] = field(default_factory=dict)
    design_direction: dict[str, Any] = field(default_factory=dict)
    generated_images: list[dict[str, Any]] = field(default_factory=list)
    modules: list[dict[str, Any]] = field(default_factory=list)
    psd_layers: list[dict[str, Any]] = field(default_factory=list)
    design_score: dict[str, Any] = field(default_factory=dict)
    feedback_plan: dict[str, Any] = field(default_factory=dict)
    outputs: dict[str, Any] = field(default_factory=dict)
    report_parts: list[str] = field(default_factory=list)
    core_rule: dict[str, Any] = field(default_factory=dict)
    detail_page_rule: dict[str, Any] = field(default_factory=dict)
    layout_blueprint: list[dict[str, Any]] = field(default_factory=list)
    requirement_constraints: dict[str, Any] = field(default_factory=dict)
    feedback_constraints: dict[str, Any] = field(default_factory=dict)
    effective_constraints: dict[str, Any] = field(default_factory=dict)

    @property
    def images(self) -> list[str]:
        return [a.name for a in self.assets if a.bucket == "image"]

    @property
    def reference_images(self) -> list[str]:
        return [a.name for a in self.assets if a.bucket == "reference_image"]

    @property
    def reference_image_paths(self) -> list[str]:
        return [
            a.saved_path
            for a in self.assets
            if a.bucket == "reference_image" and a.saved_path
        ]

    @property
    def generated_image_names(self) -> list[str]:
        return [str(item.get("name") or "") for item in self.generated_images if item.get("name")]

    @property
    def image_paths(self) -> list[str]:
        return [
            a.saved_path
            for a in self.assets
            if a.bucket == "image" and a.saved_path
        ]

    @property
    def fonts(self) -> list[str]:
        return [a.name for a in self.assets if a.bucket == "font"]

    @property
    def strict_mode(self) -> bool:
        return self.request.workflow_mode.value == "strict_brand"

    def check_cancelled(self, checkpoint: str) -> None:
        if self.cancel_checker():
            append_log(self.run_id, "Workflow", f"用户已请求中断，停止于：{checkpoint}")
            set_run_state(self.run_id, "cancelled", None)
            raise WorkflowCancelled(f"用户已中断生成任务（{checkpoint}）")


def _workflow_log(run_id: str, message: str, payload: Any | None = None) -> None:
    append_log(run_id, "Workflow", message, payload)


_SKIP_LABELS = ("商品类型", "商品名称", "品牌", "品牌名称", "使用场景", "页面", "标题字体", "段落字体", "英文字体", "要求")


def _selling_points(ctx: PipelineContext) -> list[str]:
    brief = ctx.request.product_brief
    product = ctx.request.product_name.strip()
    points: list[str] = []
    if brief:
        for raw in brief.splitlines():
            line = raw.strip(" -·•\t")
            if not line or line.startswith("[Sheet]"):
                continue
            # 跳过明显的标签行（商品类型/使用场景/字体要求等）
            label = line.split("：")[0].split(":")[0].strip()
            if any(label.startswith(skip) for skip in _SKIP_LABELS):
                continue
            # "核心卖点：a、b、c" → 取冒号后并按顿号/逗号拆分
            if "：" in line or ":" in line:
                value = line.split("：")[-1].split(":")[-1].strip()
            else:
                value = line
            for part in value.replace(",", "、").replace("|", "、").split("、"):
                part = part.strip()
                if 2 <= len(part) <= 18 and part != product:
                    points.append(part)
    # 去重保序
    seen: set[str] = set()
    unique = [p for p in points if not (p in seen or seen.add(p))]
    if unique:
        return unique[:6]
    return ["轻量通勤", "多分区收纳", "防泼水面料", "简洁商务风格"]


def _normalize_text_items(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    items: list[str] = []
    for item in value:
        if isinstance(item, str):
            text = item.strip()
        elif isinstance(item, dict):
            text = str(
                item.get("title")
                or item.get("name")
                or item.get("point")
                or item.get("label")
                or item.get("description")
                or item
            ).strip()
        else:
            text = str(item).strip()
        if text:
            items.append(text)
    return items


def _clean_constraint_items(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    items: list[str] = []
    for raw in value:
        text = str(raw).strip()
        if text and text not in items:
            items.append(text)
    return items


def _merge_effective_constraints(
    requirement_constraints: dict[str, Any],
    feedback_constraints: dict[str, Any],
) -> dict[str, Any]:
    merged = {
        "preferred_module_order": _clean_constraint_items(
            requirement_constraints.get("preferred_module_order")
        ),
        "required_modules": _clean_constraint_items(
            requirement_constraints.get("required_modules")
        ),
        "forbidden_modules": _clean_constraint_items(
            requirement_constraints.get("forbidden_modules")
        ),
        "layout_constraints": _clean_constraint_items(
            requirement_constraints.get("layout_constraints")
        ),
        "visual_constraints": _clean_constraint_items(
            requirement_constraints.get("visual_constraints")
        ),
        "copy_constraints": _clean_constraint_items(
            requirement_constraints.get("copy_constraints")
        ),
        "asset_constraints": _clean_constraint_items(
            requirement_constraints.get("asset_constraints")
        ),
        "negative_constraints": _clean_constraint_items(
            requirement_constraints.get("negative_constraints")
        ),
        "reference_alignment": str(requirement_constraints.get("reference_alignment") or "").strip(),
        "feedback_constraints_applied": False,
        "feedback_source_run_ids": [],
    }
    if not requirement_constraints.get("apply_feedback_constraints", True):
        return merged
    for key in (
        "layout_constraints",
        "visual_constraints",
        "copy_constraints",
        "asset_constraints",
        "negative_constraints",
    ):
        for item in _clean_constraint_items(feedback_constraints.get(key)):
            if item not in merged[key]:
                merged[key].append(item)
    for item in _clean_constraint_items(feedback_constraints.get("general_notes")):
        if item not in merged["layout_constraints"]:
            merged["layout_constraints"].append(item)
    merged["feedback_constraints_applied"] = bool(feedback_constraints.get("applied"))
    merged["feedback_source_run_ids"] = _clean_constraint_items(
        feedback_constraints.get("source_run_ids")
    )
    return merged


def _constraint_prompt_payload(ctx: PipelineContext) -> dict[str, Any]:
    return {
        key: value
        for key, value in ctx.effective_constraints.items()
        if value not in (None, "", [], {})
    }


def _constraint_prompt_block(ctx: PipelineContext) -> str:
    payload = _constraint_prompt_payload(ctx)
    if not payload and not ctx.strict_mode:
        return ""
    lines: list[str] = []
    if payload:
        lines.append(f"结构化需求约束：{json.dumps(payload, ensure_ascii=False)}")
    if ctx.strict_mode:
        lines.append(
            "当前为 strict_brand 模式：优先满足命中的品牌规则、详情页规则和结构化需求约束，"
            "不要退回通用模板，不要擅自改写模块顺序。"
        )
    return "\n".join(lines) + "\n"


def _rule_list(rule: dict[str, Any], snake_key: str, camel_key: str) -> list[dict[str, Any]]:
    value = rule.get(snake_key)
    if value is None:
        value = rule.get(camel_key)
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _infer_module_role(text: str, index: int) -> str:
    normalized = text.lower()
    checks = [
        ("hero", ("hero", "首屏", "头图", "主视觉", "kv", "banner")),
        ("technology", ("technology", "工艺", "技术", "结构", "细节", "放大", "局部")),
        ("scenario", ("scenario", "场景", "通勤", "使用", "出行", "office", "scene")),
        ("parameter", ("parameter", "参数", "规格", "对比", "尺寸", "容量", "数据")),
        ("brand_story", ("brand", "品牌", "故事", "about", "理念")),
        ("cta", ("cta", "购买", "行动", "咨询", "下单", "转化")),
        ("feature", ("feature", "卖点", "亮点", "优势", "特点", "功能")),
    ]
    for role, keywords in checks:
        if any(keyword in normalized for keyword in keywords):
            return role
    return "hero" if index == 0 else "feature"


def _infer_layout_type(text: str, role: str) -> str:
    normalized = text.lower()
    if "右文左图" in text or "text right" in normalized:
        return "right_text_left_image"
    if "左文右图" in text or "text left" in normalized:
        return "left_text_right_image"
    if any(keyword in normalized for keyword in ("三列", "卡片", "cards", "grid")):
        return "three_column_cards"
    if any(keyword in normalized for keyword in ("全屏", "全宽", "大场景", "full", "bleed")):
        return "full_bleed_scene"
    if any(keyword in normalized for keyword in ("表格", "参数", "规格", "对比", "table")):
        return "spec_table"
    if any(keyword in normalized for keyword in ("细节", "局部", "放大", "zoom")):
        return "detail_zoom"
    if role == "hero":
        return "centered_hero" if any(keyword in normalized for keyword in ("居中", "center")) else "hero_split"
    if role == "scenario":
        return "full_bleed_scene"
    if role == "parameter":
        return "spec_table"
    if role == "technology":
        return "detail_zoom"
    return "left_text_right_image"


def _role_display_name(role: str) -> str:
    return {
        "hero": "首屏主视觉",
        "feature": "卖点模块",
        "technology": "工艺细节",
        "scenario": "场景展示",
        "parameter": "参数对比",
        "brand_story": "品牌故事",
        "cta": "行动转化",
    }.get(role, "内容模块")


def _normalize_module_token(value: str) -> str:
    text = value.strip()
    lowered = text.lower().replace("-", "_").replace(" ", "_")
    aliases = [
        ("hero", ("hero", "首屏", "头图", "主视觉", "banner", "kv")),
        ("feature", ("feature", "卖点", "亮点", "优势", "功能")),
        ("technology", ("technology", "工艺", "技术", "结构", "细节")),
        ("scenario", ("scenario", "场景", "使用场景", "scene")),
        ("parameter", ("parameter", "参数", "规格", "对比", "数据")),
        ("brand_story", ("brand_story", "brandstory", "品牌故事", "品牌")),
        ("cta", ("cta", "行动", "购买", "转化", "下单")),
    ]
    for role, keywords in aliases:
        if any(keyword in lowered or keyword in text for keyword in keywords):
            return role
    return lowered


def _default_layout_blueprint(count: int) -> list[dict[str, Any]]:
    templates = _FALLBACK_MODULE_TEMPLATES[:count]
    return [
        {
            "name": title,
            "layer_group": group,
            "layout": layout,
            "role": role,
            "image_role": "主视觉图" if role == "hero" else f"{title}用图",
        }
        for group, title, layout, role in templates
    ]


def _fallback_blueprint_item(role: str, index: int) -> dict[str, Any]:
    for _, title, layout, template_role in _FALLBACK_MODULE_TEMPLATES:
        if template_role == role:
            return {
                "name": title,
                "layer_group": f"{index:02d}_{role.title().replace('_', '')}",
                "layout": layout,
                "role": role,
                "image_role": "主视觉图" if role == "hero" else f"{title}参考图",
            }
    return {
        "name": _role_display_name(role),
        "layer_group": f"{index:02d}_{role.title().replace('_', '')}",
        "layout": "left_text_right_image",
        "role": role,
        "image_role": f"{_role_display_name(role)}参考图",
    }


def _renumber_blueprint(blueprint: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(blueprint, start=1):
        role = str(item.get("role") or _infer_module_role(str(item.get("name") or ""), index - 1))
        normalized.append(
            {
                **item,
                "role": role,
                "layer_group": f"{index:02d}_{role.title().replace('_', '')}",
                "name": str(item.get("name") or _role_display_name(role)),
                "image_role": str(
                    item.get("image_role") or ("主视觉图" if role == "hero" else f"{_role_display_name(role)}参考图")
                ),
            }
        )
    return normalized


def _apply_requirement_constraints_to_blueprint(
    blueprint: list[dict[str, Any]],
    count: int,
    constraints: dict[str, Any],
    strict_mode: bool,
) -> list[dict[str, Any]]:
    if not constraints:
        return _renumber_blueprint(blueprint[:count])

    preferred = [_normalize_module_token(item) for item in constraints.get("preferred_module_order") or []]
    required = [_normalize_module_token(item) for item in constraints.get("required_modules") or []]
    forbidden = {
        _normalize_module_token(item) for item in constraints.get("forbidden_modules") or []
    }
    remaining = [dict(item) for item in blueprint]
    selected: list[dict[str, Any]] = []

    def take_item(token: str) -> dict[str, Any] | None:
        for index, item in enumerate(remaining):
            role = _normalize_module_token(str(item.get("role") or item.get("name") or ""))
            name = _normalize_module_token(str(item.get("name") or ""))
            if token in {role, name}:
                return remaining.pop(index)
        if token in {"hero", "feature", "technology", "scenario", "parameter", "brand_story", "cta"}:
            return _fallback_blueprint_item(token, len(selected) + 1)
        return None

    for token in preferred:
        if token in forbidden:
            continue
        item = take_item(token)
        if item:
            selected.append(item)

    for token in required:
        if token in forbidden:
            continue
        if any(_normalize_module_token(str(item.get("role") or item.get("name") or "")) == token for item in selected):
            continue
        item = take_item(token)
        if item:
            selected.append(item)

    for item in list(remaining):
        role = _normalize_module_token(str(item.get("role") or item.get("name") or ""))
        if role in forbidden:
            continue
        selected.append(item)

    if strict_mode and preferred:
        missing_preferred = [
            token
            for token in preferred
            if token not in {
                _normalize_module_token(str(item.get("role") or item.get("name") or ""))
                for item in selected
            }
        ]
        if missing_preferred:
            raise ValueError(
                "strict_brand 模式下，当前规则无法命中需求指定的模块顺序："
                + "、".join(missing_preferred)
            )

    if strict_mode and len(selected) < count:
        raise ValueError(
            f"strict_brand 模式下，当前规则与需求约束仅能生成 {len(selected)} 个模块，"
            f"少于要求的 {count} 个，请调整规则版本或需求约束"
        )

    if not strict_mode and len(selected) < count:
        defaults = _default_layout_blueprint(count)
        for item in defaults:
            role = _normalize_module_token(str(item.get("role") or item.get("name") or ""))
            if role in forbidden:
                continue
            selected.append(item)
            if len(selected) >= count:
                break

    selected = selected[:count]
    if strict_mode and not any(str(item.get("role") or "") == "hero" for item in selected):
        raise ValueError("strict_brand 模式下必须保留首屏 Hero 模块，当前需求约束移除了该模块")
    return _renumber_blueprint(selected)


def _build_layout_blueprint(
    detail_page_rule: dict[str, Any],
    count: int,
    constraints: dict[str, Any] | None = None,
    strict_mode: bool = False,
) -> list[dict[str, Any]]:
    if not detail_page_rule:
        if strict_mode:
            raise ValueError("strict_brand 模式要求命中详情页 Derived Rule，不能回退到默认模板")
        return _apply_requirement_constraints_to_blueprint(
            _default_layout_blueprint(count), count, constraints or {}, strict_mode
        )

    items = _rule_list(detail_page_rule, "layout_rules", "layoutRules") or _rule_list(
        detail_page_rule, "components", "components"
    )
    blueprint: list[dict[str, Any]] = []
    for index, item in enumerate(items):
        title = str(item.get("title") or "").strip()
        description = str(item.get("description") or "").strip()
        text = " ".join(part for part in [title, description] if part)
        if not text:
            continue
        role = _infer_module_role(text, index)
        layout = _infer_layout_type(text, role)
        layer_group = f"{index + 1:02d}_{role.title().replace('_', '')}"
        blueprint.append(
            {
                "name": title or _role_display_name(role),
                "layer_group": layer_group,
                "layout": layout,
                "role": role,
                "image_role": "主视觉图" if role == "hero" else f"{title or _role_display_name(role)}参考图",
            }
        )

    if not blueprint:
        if strict_mode:
            raise ValueError("strict_brand 模式下，命中的详情页规则未提取出可执行的布局蓝图")
        blueprint = _default_layout_blueprint(count)

    hero_index = next((i for i, item in enumerate(blueprint) if item["role"] == "hero"), None)
    if hero_index is None:
        blueprint.insert(
            0,
            {
                "name": "首屏主视觉",
                "layer_group": "01_Hero",
                "layout": "hero_split",
                "role": "hero",
                "image_role": "主视觉图",
            },
        )
    elif hero_index != 0:
        blueprint.insert(0, blueprint.pop(hero_index))

    if len(blueprint) < count:
        defaults = _default_layout_blueprint(count)
        for item in defaults:
            if len(blueprint) >= count:
                break
            blueprint.append(item)

    return _apply_requirement_constraints_to_blueprint(
        blueprint[:count], count, constraints or {}, strict_mode
    )


def _merge_modules_with_blueprint(
    modules: list[dict[str, Any]], blueprint: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    if not blueprint:
        return modules
    merged: list[dict[str, Any]] = []
    total = max(len(modules), len(blueprint))
    for index in range(total):
        raw = modules[index] if index < len(modules) else {}
        hint = blueprint[index] if index < len(blueprint) else {}
        merged.append(
            {
                **hint,
                **raw,
                "name": hint.get("name") or raw.get("name"),
                "layer_group": hint.get("layer_group") or raw.get("layer_group"),
                "layout": hint.get("layout") or raw.get("layout"),
                "role": hint.get("role") or raw.get("role"),
                "image_role": hint.get("image_role") or raw.get("image_role"),
            }
        )
    return merged


# ----------------------------- 各阶段实现 -----------------------------


def _run_stage(
    stage_id: str,
    title: str,
    icon: str,
    ctx: PipelineContext,
    model_fn: Callable[[], dict[str, Any]],
    fallback_fn: Callable[[], dict[str, Any]],
    summarize: Callable[[dict[str, Any], bool], str],
) -> StageResult:
    ctx.check_cancelled(f"{stage_id}:before")
    started = time.perf_counter()
    used_model = False
    status = "completed"
    set_run_state(ctx.run_id, "running", stage_id, title, icon)
    _workflow_log(ctx.run_id, f"开始阶段：{title} ({stage_id})")
    try:
        data = model_fn()
        used_model = True
        _workflow_log(ctx.run_id, f"模型阶段完成：{title} ({stage_id})", data)
    except LLMUnavailable as exc:
        ctx.warnings.append(f"[{stage_id}] {exc}")
        _workflow_log(ctx.run_id, f"阶段降级：{title} ({stage_id})，原因：{exc}")
        data = fallback_fn()
        status = "fallback"
    except Exception as exc:  # pragma: no cover - 阶段级兜底
        ctx.warnings.append(f"[{stage_id}] 未知异常已降级：{exc}")
        _workflow_log(ctx.run_id, f"阶段异常降级：{title} ({stage_id})，原因：{exc}")
        data = fallback_fn()
        status = "fallback"

    summary = summarize(data, used_model)
    ctx.report_parts.append(f"## {title}\n{summary}")
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    _workflow_log(
        ctx.run_id,
        f"结束阶段：{title} ({stage_id})，status={status}，used_model={used_model}，elapsed_ms={elapsed_ms}，summary={summary}",
    )
    result = StageResult(
        id=stage_id,
        title=title,
        icon=icon,
        status=status,  # type: ignore[arg-type]
        summary=summary,
        detail=json.dumps(data, ensure_ascii=False, indent=2),
        data=data,
        used_model=used_model,
        elapsed_ms=elapsed_ms,
    )
    append_stage_result(ctx.run_id, result)
    ctx.check_cancelled(f"{stage_id}:after")
    return result


def stage_vision(ctx: PipelineContext) -> StageResult:
    req = ctx.request

    settings = req.model_settings

    def model_fn() -> dict[str, Any]:
        image_names = ctx.images
        prompt = (
            f"商品名称：{req.product_name}\n"
            f"品牌：{req.brand_name}\n"
            f"商品图文件名：{image_names}\n"
            f"brief 文本：\n{req.product_brief}\n\n"
            f"{_constraint_prompt_block(ctx)}"
            "请输出 Product Brief 基础信息，字段："
            "product_type, target_audience, main_color, material, key_features(数组), "
            "scenarios(数组), usable_images(对象，含 hero_image、detail_images 数组、scene_images 数组)。"
        )
        image_paths = ctx.image_paths[: settings.max_vision_images]
        if image_paths and settings.enable_vision:
            try:
                data = ctx.llm.invoke_vision_json(
                    req.prompts.vision_agent_prompt, prompt, image_paths
                )
                data["_vision"] = {
                    "mode": "multimodal",
                    "model": settings.vision_model,
                    "images": [Path(p).name for p in image_paths],
                }
                data["key_features"] = _normalize_text_items(data.get("key_features")) or _selling_points(ctx)
                ctx.product_info = data
                return data
            except LLMUnavailable as exc:
                ctx.warnings.append(f"[product_understanding] 多模态识别不可用，转文本推断：{exc}")

        data = ctx.llm.invoke_json(req.prompts.vision_agent_prompt, prompt)
        data["_vision"] = {"mode": "text", "model": settings.model}
        data["key_features"] = _normalize_text_items(data.get("key_features")) or _selling_points(ctx)
        ctx.product_info = data
        return data

    def fallback_fn() -> dict[str, Any]:
        images = ctx.images
        data = {
            "product_type": req.product_name,
            "target_audience": "注重品质、效率与品牌一致性的电商消费者（待人工确认）",
            "main_color": "以参考图为准（浅蓝 / 低饱和）",
            "material": "尼龙 / 防泼水面料（待人工确认）",
            "key_features": _selling_points(ctx),
            "scenarios": ["办公", "通勤", "短途旅行"],
            "usable_images": {
                "hero_image": images[0] if images else "（待上传主视觉图）",
                "detail_images": images[1:4],
                "scene_images": images[4:7],
            },
        }
        ctx.product_info = data
        return data

    def summarize(data: dict[str, Any], used: bool) -> str:
        feats = "、".join(_normalize_text_items(data.get("key_features"))[:4])
        mode = (data.get("_vision") or {}).get("mode")
        if not used:
            prefix = "按文件名/brief 规则推断"
        elif mode == "multimodal":
            count = len((data.get("_vision") or {}).get("images", []))
            prefix = f"多模态识别（读取 {count} 张图片）"
        else:
            prefix = "文本模型推断"
        return f"{prefix}：{data.get('product_type', req.product_name)}，主色 {data.get('main_color', '-')}，关键特征：{feats}。"

    return _run_stage(
        "product_understanding",
        "商品理解 Agent",
        "eye",
        ctx,
        model_fn,
        fallback_fn,
        summarize,
    )


def stage_structured(ctx: PipelineContext) -> StageResult:
    req = ctx.request

    def model_fn() -> dict[str, Any]:
        prompt = (
            f"商品视觉信息：{json.dumps(ctx.product_info, ensure_ascii=False)}\n"
            f"brief 文本：\n{req.product_brief}\n\n"
            f"{_constraint_prompt_block(ctx)}"
            "请合并视觉信息与 brief，输出 Product Brief："
            "brand, product, audience, selling_points(数组), specifications(对象), scenarios(数组), design_focus。"
        )
        data = ctx.llm.invoke_json(req.prompts.structured_agent_prompt, prompt)
        data["selling_points"] = _normalize_text_items(data.get("selling_points")) or _selling_points(ctx)
        ctx.structured_info = data
        return data

    def fallback_fn() -> dict[str, Any]:
        data = {
            "brand": req.brand_name,
            "product": req.product_name,
            "audience": ctx.product_info.get("target_audience", "品牌目标消费者"),
            "selling_points": _selling_points(ctx),
            "specifications": {
                "size": "根据 brief 提取",
                "weight": "根据 brief 提取",
                "material": ctx.product_info.get("material", "根据 brief 提取"),
            },
            "scenarios": ctx.product_info.get("scenarios", ["办公", "通勤", "短途旅行"]),
            "design_focus": "将商品卖点转译为标准详情页模块，保持品牌一致性与可编辑性。",
        }
        ctx.structured_info = data
        return data

    def summarize(data: dict[str, Any], used: bool) -> str:
        points = "、".join(_normalize_text_items(data.get("selling_points"))[:4])
        return f"统一商品结构已生成，核心卖点：{points}。"

    return _run_stage(
        "product_brief",
        "Product Brief",
        "layers",
        ctx,
        model_fn,
        fallback_fn,
        summarize,
    )


def stage_brand_rag(ctx: PipelineContext) -> StageResult:
    req = ctx.request
    settings = req.model_settings
    selected_core_rule = ctx.core_rule or {}
    selected_detail_rule = ctx.detail_page_rule or {}

    def model_fn() -> dict[str, Any]:
        prompt = (
            f"品牌：{req.brand_name}\n"
            f"品牌规范：\n{req.brand_guidelines}\n"
            f"参考图说明：\n{req.reference_notes}\n"
            f"参考案例图片：{ctx.reference_images}\n"
            f"可用字体文件：{ctx.fonts}\n"
            f"选中的 Core Rule：{json.dumps(selected_core_rule, ensure_ascii=False)}\n"
            f"选中的详情页 Derived Rule：{json.dumps(selected_detail_rule, ensure_ascii=False)}\n"
            f"强布局蓝图：{json.dumps(ctx.layout_blueprint, ensure_ascii=False)}\n"
            f"界面字体配置：{req.typography.model_dump_json()}\n\n"
            f"{_constraint_prompt_block(ctx)}"
            "请生成 Brand Design System 摘要，输出："
            "version, rule_status, core_rule(对象), derived_rule(对象), asset_memory(对象), "
            "rule_weights(对象), drift_risks(数组), brand_style, primary_color, secondary_colors(数组), "
            "fonts(对象，含 title、body、english), layout_rules(数组), component_patterns(数组), prompt_templates(数组), module_order(数组)。"
        )
        reference_image_paths = ctx.reference_image_paths[: settings.max_vision_images]
        if reference_image_paths and settings.enable_vision:
            data = ctx.llm.invoke_vision_json(
                req.prompts.brand_rag_agent_prompt,
                prompt,
                reference_image_paths,
            )
            data["_reference_vision"] = {
                "mode": "multimodal",
                "model": settings.vision_model,
                "images": [Path(path).name for path in reference_image_paths],
            }
        else:
            data = ctx.llm.invoke_json(req.prompts.brand_rag_agent_prompt, prompt)
            data["_reference_vision"] = {
                "mode": "text",
                "images": ctx.reference_images,
            }
        if ctx.layout_blueprint:
            data["module_order"] = [item["name"] for item in ctx.layout_blueprint]
            data["selected_core_rule"] = selected_core_rule
            data["selected_detail_page_rule"] = selected_detail_rule
        ctx.brand_profile = data
        return data

    def fallback_fn() -> dict[str, Any]:
        data = {
            "version": "Brand Rule V1.1",
            "rule_status": "draft_pending_approval",
            "core_rule": {
                "brand_name": req.brand_name,
                "positioning": "企业级品牌设计操作系统中的当前品牌空间",
                "tone": req.layout.visual_style,
                "primary_color": req.layout.accent_color,
                "typography_locked": req.typography.lock_brand_typography,
            },
            "derived_rule": {
                "page_type": "商品详情页",
                "module_template": [item["name"] for item in ctx.layout_blueprint],
                "editable_scope": "允许页面层模块、文案和图片策略随任务调整，但受 Core Rule 约束。",
                "requirement_constraints": ctx.effective_constraints,
            },
            "asset_memory": {
                "role": "仅作为参考案例，不直接修改核心品牌规则",
                "reference_notes": req.reference_notes,
                "reference_images": ctx.reference_images,
                "asset_names": [asset.name for asset in ctx.assets],
            },
            "selected_core_rule": selected_core_rule,
            "selected_detail_page_rule": selected_detail_rule,
            "rule_weights": {"core_rule": 0.55, "derived_rule": 0.35, "asset_memory": 0.1},
            "drift_risks": ["新上传资产默认进入训练池，不自动覆盖当前生效规则"],
            "brand_style": req.layout.visual_style,
            "primary_color": req.layout.accent_color,
            "secondary_colors": [req.layout.background_color, "#ffffff"],
            "fonts": {
                "title": req.typography.title_font,
                "body": req.typography.body_font,
                "english": req.typography.english_font,
            },
            "layout_rules": [
                f"页面宽度 {req.layout.canvas_width}px，高度不限",
                f"标题 {req.typography.title_font} {req.typography.title_size}号",
                f"正文 {req.typography.body_font} {req.typography.body_size}号",
                f"英文 {req.typography.english_font}",
                "详情页模块顺序与图文分区优先遵守选中的 Derived Rule",
                "先生成结构化页面 Layout JSON，再映射到 Figma / PSD 输出",
            ],
            "component_patterns": [item["layout"] for item in ctx.layout_blueprint],
            "prompt_templates": ["详情页页面规划", "场景图生成", "局部模块重生成", "设计评分"],
            "module_order": [item["name"] for item in ctx.layout_blueprint],
        }
        ctx.brand_profile = data
        return data

    def summarize(data: dict[str, Any], used: bool) -> str:
        fonts = data.get("fonts", {})
        return (
            f"规则版本：{data.get('version', '-')}；"
            f"Core/Derived/Asset 权重 {data.get('rule_weights', {})}；"
            f"主色 {data.get('primary_color', '-')}；字体 标题/{fonts.get('title', '-')} 正文/{fonts.get('body', '-')}。"
        )

    return _run_stage(
        "brand_knowledge",
        "品牌知识库 / 规则版本",
        "library",
        ctx,
        model_fn,
        fallback_fn,
        summarize,
    )


def stage_design(ctx: PipelineContext) -> StageResult:
    req = ctx.request
    detail_rule = ctx.detail_page_rule or {}

    def model_fn() -> dict[str, Any]:
        prompt = (
            f"商品结构：{json.dumps(ctx.structured_info, ensure_ascii=False)}\n"
            f"品牌风格：{json.dumps(ctx.brand_profile, ensure_ascii=False)}\n"
            f"选中的 Core Rule：{json.dumps(ctx.core_rule, ensure_ascii=False)}\n"
            f"选中的详情页 Derived Rule：{json.dumps(detail_rule, ensure_ascii=False)}\n"
            f"强布局蓝图：{json.dumps(ctx.layout_blueprint, ensure_ascii=False)}\n"
            f"工作流模式：{req.workflow_mode.value}\n"
            f"参考图说明：{req.reference_notes}\n\n"
            f"参考案例图片：{ctx.reference_images}\n\n"
            f"{_constraint_prompt_block(ctx)}"
            "请输出页面规划策略，字段："
            "direction(整体视觉方向，字符串), page_template(数组), information_architecture(数组), "
            "tone(色调与节奏), image_strategy(图片资产需求), brand_constraints(数组), risks(数组)。"
            "如果已提供详情页 Derived Rule，page_template 与 information_architecture 必须优先服从该规则，不要退回默认模块顺序。"
        )
        data = ctx.llm.invoke_json(req.prompts.design_agent_prompt, prompt)
        if ctx.layout_blueprint:
            data["page_template"] = [item["name"] for item in ctx.layout_blueprint]
        ctx.design_direction = data
        return data

    def fallback_fn() -> dict[str, Any]:
        page_template = [item["name"] for item in ctx.layout_blueprint]
        data = {
            "direction": "优先贴合选中的详情页规则与参考图：保留模块节奏、图文占比和主视觉位置，再补足商品卖点表达。",
            "page_template": page_template,
            "information_architecture": [
                f"{name}：优先沿用参考页同类型信息区块与图文分区"
                for name in page_template[: max(4, len(page_template))]
            ],
            "tone": "低饱和、冷静、商务；节奏优先复用参考页的大图、细节、参数与收尾顺序。",
            "image_strategy": "Image Studio 需补齐主视觉、卖点图、场景图与参数说明图；素材不足时以占位图进入设计师审核。",
            "brand_constraints": [
                "严格遵守品牌字体与字号" if req.typography.lock_brand_typography else "字体可在品牌库内微调",
                f"主色锁定 {req.layout.accent_color}",
                "页面结构必须优先遵守选中的详情页布局规则与模块顺序",
                *[f"布局约束：{item}" for item in ctx.effective_constraints.get("layout_constraints", [])[:4]],
                *[f"视觉约束：{item}" for item in ctx.effective_constraints.get("visual_constraints", [])[:4]],
            ],
            "risks": ["实拍素材需人工抠图调色", "文案避免绝对化与平台风险词"],
        }
        ctx.design_direction = data
        return data

    def summarize(data: dict[str, Any], used: bool) -> str:
        return str(data.get("direction", "已生成设计方向。"))

    return _run_stage(
        "page_planner", "页面规划 Agent", "palette", ctx, model_fn, fallback_fn, summarize
    )


_FALLBACK_MODULE_TEMPLATES = [
    ("01_Hero", "Hero", "hero_split", "hero"),
    ("02_Feature", "Feature", "three_column_cards", "feature"),
    ("03_Technology", "Technology", "detail_zoom", "technology"),
    ("04_Scenario", "Scenario", "full_bleed_scene", "scenario"),
    ("05_Parameter", "Parameter", "spec_table", "parameter"),
    ("06_BrandStory", "Brand Story", "minimal_logo", "brand_story"),
    ("07_CTA", "CTA", "cta_panel", "cta"),
]


def stage_layout(ctx: PipelineContext) -> StageResult:
    req = ctx.request
    count = req.layout.module_count

    def model_fn() -> dict[str, Any]:
        prompt = (
            f"设计方向：{json.dumps(ctx.design_direction, ensure_ascii=False)}\n"
            f"品牌模块顺序：{ctx.brand_profile.get('module_order')}\n"
            f"选中的详情页 Derived Rule：{json.dumps(ctx.detail_page_rule, ensure_ascii=False)}\n"
            f"强布局蓝图：{json.dumps(ctx.layout_blueprint, ensure_ascii=False)}\n"
            f"参考案例图片：{ctx.reference_images}\n"
            f"已生成图片素材：{ctx.generated_image_names}\n"
            f"画布宽度：{req.layout.canvas_width}px，模块数量：{count}\n"
            f"主视觉高度：{req.layout.hero_height}，普通模块高度：{req.layout.module_height}\n"
            f"可用商品图：{ctx.images}\n\n"
            f"{_constraint_prompt_block(ctx)}"
            "请输出版式规划，字段 modules 为数组，每个元素含："
            "name(模块中文名), layer_group(英文图层组名), layout(布局类型), "
            "height(整数像素), role(hero/feature/technology/scenario/parameter/brand_story/cta), "
            "image_role(该模块主要用什么图), elements(图层元素数组)。"
            f"模块数量必须是 {count} 个。"
            "如果已提供强布局蓝图，必须优先保持相同模块顺序、主次层级、图文左右关系和大图区位置。"
        )
        data = ctx.llm.invoke_json(req.prompts.layout_agent_prompt, prompt)
        modules = data.get("modules")
        if not isinstance(modules, list) or not modules:
            raise LLMUnavailable("版式 Agent 未返回 modules 数组")
        ctx.modules = _normalize_modules(_merge_modules_with_blueprint(modules, ctx.layout_blueprint), ctx)
        return {"modules": ctx.modules}

    def fallback_fn() -> dict[str, Any]:
        modules = [
            {
                **item,
                "elements": ["BG_背景", "IMG_图片", "TXT_标题", "TXT_说明"],
            }
            for item in ctx.layout_blueprint[:count]
        ]
        ctx.modules = _normalize_modules(modules, ctx)
        return {"modules": ctx.modules}

    def summarize(data: dict[str, Any], used: bool) -> str:
        names = "、".join(m["name"] for m in data.get("modules", []))
        return f"已规划 {len(data.get('modules', []))} 个模块：{names}。"

    return _run_stage(
        "layout_engine", "Layout Engine", "grid", ctx, model_fn, fallback_fn, summarize
    )


def _normalize_modules(
    modules: list[dict[str, Any]], ctx: PipelineContext
) -> list[dict[str, Any]]:
    req = ctx.request
    images = ctx.images
    generated_images = ctx.generated_image_names
    normalized: list[dict[str, Any]] = []
    for index, raw in enumerate(modules):
        role = str(raw.get("role") or ("hero" if index == 0 else "feature"))
        is_hero = role == "hero" or index == 0
        height = raw.get("height")
        try:
            height = int(height)
        except (TypeError, ValueError):
            height = req.layout.hero_height if is_hero else req.layout.module_height
        normalized.append(
            {
                "index": index + 1,
                "name": str(raw.get("name") or f"模块{index + 1}"),
                "layer_group": str(raw.get("layer_group") or f"{index + 1:02d}_Module"),
                "layout": str(raw.get("layout") or "image_text"),
                "role": role,
                "height": max(300, min(height, 2400)),
                "image_role": str(raw.get("image_role") or ""),
                "elements": raw.get("elements") or ["BG_背景", "IMG_图片", "TXT_标题"],
                "image_candidates": (
                    generated_images[index : index + 1]
                    + images[index : index + 1]
                    + generated_images[:1]
                    + images[:1]
                ),
            }
        )
    return normalized


def stage_image_generation(ctx: PipelineContext) -> StageResult:
    req = ctx.request

    def default_images() -> list[dict[str, Any]]:
        generated: list[dict[str, Any]] = []
        for index, item in enumerate(ctx.layout_blueprint, start=1):
            if item.get("role") in ("brand_story", "cta"):
                continue
            generated.append(
                {
                    "name": f"generated_{index:02d}_{item.get('role') or 'module'}.svg",
                    "module_index": index,
                    "module_name": item.get("name"),
                    "role": item.get("role"),
                    "image_role": item.get("image_role") or "模块配图",
                    "source": "generated_placeholder",
                    "prompt": f"{req.brand_name} {req.product_name} {item.get('name')} {item.get('image_role') or '配图'}",
                }
            )
        return generated

    def model_fn() -> dict[str, Any]:
        prompt = (
            f"品牌：{req.brand_name}\n"
            f"商品：{req.product_name}\n"
            f"页面规划：{json.dumps(ctx.design_direction, ensure_ascii=False)}\n"
            f"模块蓝图：{json.dumps(ctx.layout_blueprint, ensure_ascii=False)}\n"
            f"已有商品图：{ctx.images}\n"
            f"参考图：{ctx.reference_images}\n\n"
            f"{_constraint_prompt_block(ctx)}"
            "请输出 images 数组，每个元素包含："
            "name, module_index, module_name, role, image_role, source, prompt。"
            "source 取值建议为 ai_generated 或 reference_derived。"
        )
        data = ctx.llm.invoke_json(req.prompts.design_agent_prompt, prompt)
        images = data.get("images")
        if not isinstance(images, list) or not images:
            raise LLMUnavailable("图片生成阶段未返回 images 数组")
        ctx.generated_images = [
            {
                "name": str(item.get("name") or f"generated_{idx + 1:02d}.svg"),
                "module_index": int(item.get("module_index") or idx + 1),
                "module_name": str(item.get("module_name") or ""),
                "role": str(item.get("role") or ""),
                "image_role": str(item.get("image_role") or "模块配图"),
                "source": str(item.get("source") or "ai_generated"),
                "prompt": str(item.get("prompt") or ""),
            }
            for idx, item in enumerate(images)
            if isinstance(item, dict)
        ] or default_images()
        return {"images": ctx.generated_images}

    def fallback_fn() -> dict[str, Any]:
        ctx.generated_images = default_images()
        return {"images": ctx.generated_images}

    def summarize(data: dict[str, Any], used: bool) -> str:
        images = data.get("images", [])
        return f"已规划 {len(images)} 张模块配图，供后续 Layout 与导出阶段消费。"

    return _run_stage(
        "image_generation",
        "图片生成 Agent",
        "image",
        ctx,
        model_fn,
        fallback_fn,
        summarize,
    )


def stage_copy(ctx: PipelineContext) -> StageResult:
    req = ctx.request
    module_names = [m["name"] for m in ctx.modules]

    def model_fn() -> dict[str, Any]:
        prompt = (
            f"品牌：{req.brand_name}，商品：{req.product_name}\n"
            f"卖点：{ctx.structured_info.get('selling_points')}\n"
            f"brief：\n{req.product_brief}\n"
            f"模块列表：{module_names}\n\n"
            f"{_constraint_prompt_block(ctx)}"
            "请为每个模块生成文案，输出 blocks 为数组，"
            "顺序与模块列表一致，每个元素含："
            "headline(主标题), subtitle(副标题), body(短说明), points(要点数组)。"
            "文案必须基于 brief，不夸大、不使用绝对化或平台风险词。"
        )
        data = ctx.llm.invoke_json(req.prompts.copy_agent_prompt, prompt)
        blocks = data.get("blocks")
        if not isinstance(blocks, list) or not blocks:
            raise LLMUnavailable("文案 Agent 未返回 blocks 数组")
        _apply_copy(ctx, blocks)
        return {"blocks": [m["copy"] for m in ctx.modules]}

    def fallback_fn() -> dict[str, Any]:
        points = _selling_points(ctx)
        blocks = []
        for index, module in enumerate(ctx.modules):
            if module["role"] == "hero":
                blocks.append(
                    {
                        "headline": req.product_name,
                        "subtitle": req.brand_name,
                        "body": "为日常办公与通勤设计的多功能" + req.product_name,
                        "points": points[:3],
                    }
                )
            elif module["role"] in ("brand_story", "cta"):
                blocks.append(
                    {
                        "headline": req.brand_name if module["role"] == "brand_story" else "延续品牌一致的设计表达",
                        "subtitle": "品牌规则驱动的页面收尾" if module["role"] == "brand_story" else "进入审核与导出",
                        "body": "",
                        "points": [],
                    }
                )
            else:
                point = points[index % len(points)]
                blocks.append(
                    {
                        "headline": point,
                        "subtitle": module["name"],
                        "body": f"{point}，贴合真实使用场景。",
                        "points": [],
                    }
                )
        _apply_copy(ctx, blocks)
        return {"blocks": [m["copy"] for m in ctx.modules]}

    def summarize(data: dict[str, Any], used: bool) -> str:
        first = data.get("blocks", [{}])[0]
        return f"已生成 {len(data.get('blocks', []))} 段模块文案，主标题示例：{first.get('headline', '-')}。"

    return _run_stage(
        "copy", "文案 Agent", "type", ctx, model_fn, fallback_fn, summarize
    )


def _apply_copy(ctx: PipelineContext, blocks: list[dict[str, Any]]) -> None:
    for index, module in enumerate(ctx.modules):
        block = blocks[index] if index < len(blocks) else {}
        module["copy"] = {
            "headline": str(block.get("headline") or module["name"]),
            "subtitle": str(block.get("subtitle") or ""),
            "body": str(block.get("body") or ""),
            "points": list(block.get("points") or []),
        }


def stage_psd(ctx: PipelineContext) -> StageResult:
    req = ctx.request

    def build_layers() -> list[dict[str, Any]]:
        layers = []
        for module in ctx.modules:
            children = ["BG_背景"]
            if module["role"] not in ("brand_story", "cta"):
                children.append(f"IMG_{module['image_role'] or '图片'}")
            children.append("TXT_主标题")
            if module["copy"].get("subtitle"):
                children.append("TXT_副标题")
            if module["copy"].get("body"):
                children.append("TXT_正文")
            for i, _ in enumerate(module["copy"].get("points", []), start=1):
                children.append(f"TXT_要点{i}")
            if module["role"] in ("hero", "brand_story", "cta"):
                children.append("LOGO_品牌")
            layers.append({"group": module["layer_group"], "layers": children})
        return layers

    def model_fn() -> dict[str, Any]:
        # 设计稿阶段以确定性结构为主，模型只补充命名建议与注意事项。
        prompt = (
            f"模块与文案：{json.dumps([{'name': m['name'], 'copy': m['copy']} for m in ctx.modules], ensure_ascii=False)}\n\n"
            f"{_constraint_prompt_block(ctx)}"
            "请输出 Figma / PSD 生产说明，字段 notes(数组，图层命名、组件映射与可编辑性注意事项)。"
        )
        data = ctx.llm.invoke_json(req.prompts.psd_agent_prompt, prompt)
        ctx.psd_layers = build_layers()
        return {"layer_tree": ctx.psd_layers, "notes": data.get("notes", [])}

    def fallback_fn() -> dict[str, Any]:
        ctx.psd_layers = build_layers()
        return {
            "layer_tree": ctx.psd_layers,
            "notes": [
                "所有文字保留为可编辑文字图层",
                "图片独立成层，命名以 IMG_ 前缀",
                "每个模块独立分组，分组名带序号",
            ],
        }

    def summarize(data: dict[str, Any], used: bool) -> str:
        return f"已规划 {len(data.get('layer_tree', []))} 个 Figma Frame / PSD 图层分组，文字层全部可编辑。"

    return _run_stage(
        "figma_psd", "Figma / PSD 生成 Agent", "file-image", ctx, model_fn, fallback_fn, summarize
    )


def stage_design_score(ctx: PipelineContext) -> StageResult:
    ctx.check_cancelled("design_score:before")
    req = ctx.request
    started = time.perf_counter()
    set_run_state(ctx.run_id, "running", "design_score", "Design Score", "check-circle")
    _workflow_log(ctx.run_id, "开始阶段：Design Score (design_score)")
    module_count = len(ctx.modules)
    brand_constraints = len(ctx.design_direction.get("brand_constraints", []))
    asset_penalty = 0 if ctx.images else 6
    score = {
        "brand_match": min(96, 84 + brand_constraints * 3),
        "layout_quality": min(94, 82 + module_count),
        "visual_consistency": min(95, 88 + (2 if req.typography.lock_brand_typography else 0)),
        "readability": 88,
        "conversion_score": 86,
    }
    score = {key: max(60, value - asset_penalty) for key, value in score.items()}
    overall = round(sum(score.values()) / len(score), 1)
    ctx.design_score = {
        **score,
        "overall": overall,
        "explain": [
            "评分用于给设计负责人提供可解释审核依据，不替代人工判断。",
            "品牌匹配优先参考 Core Rule、Derived Rule 与当前页面模板。",
            "缺少商品实拍或场景素材时，视觉一致性和转化评分会被扣分。",
        ],
        "blocking_issues": [] if overall >= 85 else ["建议补充高质量商品图后再导出正式设计稿"],
    }
    summary = f"综合评分 {overall}，品牌匹配 {ctx.design_score['brand_match']}，布局质量 {ctx.design_score['layout_quality']}。"
    ctx.report_parts.append(f"## Design Score\n{summary}")
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    _workflow_log(
        ctx.run_id,
        f"结束阶段：Design Score (design_score)，status=completed，used_model=False，elapsed_ms={elapsed_ms}，summary={summary}",
        ctx.design_score,
    )
    result = StageResult(
        id="design_score",
        title="Design Score",
        icon="check-circle",
        status="completed",
        summary=summary,
        detail=json.dumps(ctx.design_score, ensure_ascii=False, indent=2),
        data=ctx.design_score,
        used_model=False,
        elapsed_ms=elapsed_ms,
    )
    append_stage_result(ctx.run_id, result)
    ctx.check_cancelled("design_score:after")
    return result


def stage_outputs(ctx: PipelineContext) -> StageResult:
    ctx.check_cancelled("output_review:before")
    req = ctx.request
    started = time.perf_counter()
    set_run_state(ctx.run_id, "running", "output_review", "输出、审核与反馈", "check-circle")
    _workflow_log(ctx.run_id, "开始阶段：输出、审核与反馈 (output_review)")
    output_labels = {
        "detail_page": "商品详情页结构化方案",
        "figma_page": "Figma 页面",
        "psd_file": "PSD 兼容文件",
        "main_image": "主图设计稿",
        "banner": "广告 Banner",
    }
    produced = [output_labels.get(o.value, o.value) for o in req.output_types]
    review_checklist = [
        "品牌一致性：是否符合品牌视觉规范",
        "字体字号：是否使用指定字体和允许字号",
        "图片质量：抠图、清晰度、色彩是否达标",
        "版式质量：是否接近参考图风格、是否美观",
        "文案准确性：是否与 brief 一致、是否有夸大",
        "Figma/PSD 可编辑性：图层是否清晰、文字是否可编辑",
    ]
    ctx.outputs = {
        "produced": produced,
        "review_checklist": review_checklist,
        "feedback_capture": {
            "tracked_changes": ["模块隐藏/删除", "字体字号调整", "颜色调整", "文案修改", "图片替换"],
            "learning_policy": "本阶段只记录设计师修改，不自动强化学习、不自动覆盖品牌规则。",
            "effective_constraints": ctx.effective_constraints,
            "feedback_constraints": ctx.feedback_constraints,
        },
        "next_step": "进入人工审核：设计师初审 → 运营/品牌方审核 → 记录反馈 → 交付上线。",
    }
    summary = f"已产出：{'、'.join(produced)}；下一步进入人工审核并记录设计反馈。"
    ctx.report_parts.append(f"## 输出、审核与反馈\n{summary}")
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    _workflow_log(
        ctx.run_id,
        f"结束阶段：输出、审核与反馈 (output_review)，status=completed，used_model=False，elapsed_ms={elapsed_ms}，summary={summary}",
        ctx.outputs,
    )
    result = StageResult(
        id="output_review",
        title="输出、审核与反馈",
        icon="check-circle",
        status="completed",
        summary=summary,
        detail=json.dumps(ctx.outputs, ensure_ascii=False, indent=2),
        data=ctx.outputs,
        used_model=False,
        elapsed_ms=elapsed_ms,
    )
    append_stage_result(ctx.run_id, result)
    ctx.check_cancelled("output_review:after")
    return result


PIPELINE_STAGES: list[Callable[[PipelineContext], StageResult]] = [
    stage_vision,
    stage_structured,
    stage_brand_rag,
    stage_design,
    stage_image_generation,
    stage_layout,
    stage_copy,
    stage_psd,
    stage_design_score,
    stage_outputs,
]


def run_pipeline(
    request: WorkflowRequest,
    assets: list[UploadedAsset],
    run_id: str = "",
    cancel_checker: Callable[[], bool] | None = None,
    selected_rule_context: dict[str, Any] | None = None,
    feedback_constraints: dict[str, Any] | None = None,
) -> tuple[list[StageResult], PipelineContext]:
    reset_run(run_id or "local")
    try:
        database.persist_run_started(run_id or "local", request, assets)
    except Exception as exc:
        print(f"[DB] persist_run_started failed: {exc}", flush=True)
    ctx = PipelineContext(
        request=request,
        assets=assets,
        llm=LLMClient(request.model_settings, run_id=run_id or "local"),
        run_id=run_id or "local",
        cancel_checker=cancel_checker or (lambda: False),
        core_rule=dict((selected_rule_context or {}).get("coreRule") or {}),
        detail_page_rule=dict((selected_rule_context or {}).get("detailPageRule") or {}),
        requirement_constraints=request.requirement_constraints.model_dump(),
        feedback_constraints=dict(feedback_constraints or {}),
    )
    ctx.effective_constraints = _merge_effective_constraints(
        ctx.requirement_constraints,
        ctx.feedback_constraints,
    )
    ctx.layout_blueprint = _build_layout_blueprint(
        ctx.detail_page_rule,
        request.layout.module_count,
        ctx.effective_constraints,
        ctx.strict_mode,
    )
    set_run_state(ctx.run_id, "running", None)
    _workflow_log(
        ctx.run_id,
        "工作流启动",
        {
            "project_name": request.project_name,
            "brand_name": request.brand_name,
            "product_name": request.product_name,
            "assets": [asset.model_dump() for asset in assets],
            "selected_rules": selected_rule_context or {},
            "requirement_constraints": ctx.requirement_constraints,
            "feedback_constraints": ctx.feedback_constraints,
            "effective_constraints": ctx.effective_constraints,
        },
    )
    stages = [stage(ctx) for stage in PIPELINE_STAGES]
    set_run_state(ctx.run_id, "completed", None)
    _workflow_log(ctx.run_id, "工作流完成", {"stage_count": len(stages)})
    return stages, ctx
