from __future__ import annotations

import base64
import html
import json
import mimetypes
import shutil
import textwrap
from pathlib import Path
from typing import Any

from .pipeline import PipelineContext, summarize_assets

IMAGE_BUCKETS = {"image", "reference_image"}


def _layout_variant(module: dict[str, Any]) -> str:
    layout = str(module.get("layout") or "").lower()
    role = str(module.get("role") or "")
    if "right_text_left_image" in layout:
        return "right_text_left_image"
    if "left_text_right_image" in layout:
        return "left_text_right_image"
    if "full_bleed_scene" in layout:
        return "full_bleed_scene"
    if "detail_zoom" in layout:
        return "detail_zoom"
    if "three_column_cards" in layout:
        return "three_column_cards"
    if "spec_table" in layout:
        return "spec_table"
    if "centered_hero" in layout:
        return "centered_hero"
    if "hero" in layout and "split" in layout:
        return "hero_split"
    if role == "scenario":
        return "full_bleed_scene"
    if role == "parameter":
        return "spec_table"
    if role == "technology":
        return "detail_zoom"
    if role == "hero":
        return "hero_split"
    return "left_text_right_image"


def _module_render_plan(module: dict[str, Any], canvas_width: int) -> dict[str, Any]:
    variant = _layout_variant(module)
    height = int(module.get("height") or 820)
    pad = 40
    text = {"x": pad, "y": 48, "w": canvas_width - pad * 2, "align": "left"}
    image = {"enabled": module.get("role") not in ("brand_story", "cta"), "x": 0, "y": 0, "w": 0, "h": 0}
    point_style = "list"
    bg_style = "card"

    if variant == "centered_hero":
        text = {"x": 80, "y": 64, "w": canvas_width - 160, "align": "center"}
        image = {
            "enabled": image["enabled"],
            "x": 60,
            "y": max(180, int(height * 0.22)),
            "w": canvas_width - 120,
            "h": max(220, int(height * 0.58)),
        }
    elif variant in ("hero_split", "left_text_right_image", "detail_zoom"):
        text_width = int(canvas_width * (0.34 if variant == "detail_zoom" else 0.36))
        text = {"x": pad, "y": 56, "w": text_width, "align": "left"}
        image = {
            "enabled": image["enabled"],
            "x": pad + text_width + 28,
            "y": 54 if variant == "hero_split" else 92,
            "w": canvas_width - (pad + text_width + 28) - pad,
            "h": height - (110 if variant == "hero_split" else 140),
        }
    elif variant == "right_text_left_image":
        text_width = int(canvas_width * 0.36)
        image_width = canvas_width - pad * 2 - text_width - 28
        image = {
            "enabled": image["enabled"],
            "x": pad,
            "y": 92,
            "w": image_width,
            "h": height - 140,
        }
        text = {"x": pad + image_width + 28, "y": 56, "w": text_width, "align": "left"}
    elif variant == "full_bleed_scene":
        text = {"x": 56, "y": max(72, height - 210), "w": int(canvas_width * 0.42), "align": "left"}
        image = {
            "enabled": image["enabled"],
            "x": 0,
            "y": 0,
            "w": canvas_width,
            "h": height,
        }
        bg_style = "scene"
    elif variant == "three_column_cards":
        text = {"x": pad, "y": 52, "w": canvas_width - pad * 2, "align": "left"}
        image = {
            "enabled": image["enabled"],
            "x": pad,
            "y": 126,
            "w": canvas_width - pad * 2,
            "h": max(180, int(height * 0.34)),
        }
        point_style = "cards"
    elif variant == "spec_table":
        text = {"x": pad, "y": 52, "w": int(canvas_width * 0.4), "align": "left"}
        image = {
            "enabled": image["enabled"],
            "x": canvas_width - pad - int(canvas_width * 0.28),
            "y": 70,
            "w": int(canvas_width * 0.28),
            "h": max(180, int(height * 0.34)),
        }
        point_style = "table"

    return {
        "variant": variant,
        "background": bg_style,
        "text": text,
        "image": image,
        "point_style": point_style,
        "padding": pad,
    }


def build_design_spec(ctx: PipelineContext) -> dict[str, Any]:
    req = ctx.request
    modules = []
    for module in ctx.modules:
        enriched = dict(module)
        enriched["render_plan"] = _module_render_plan(enriched, req.layout.canvas_width)
        modules.append(enriched)
    total_height = sum(int(m["height"]) for m in modules) or req.layout.hero_height
    return {
        "project": {
            "name": req.project_name,
            "brand": req.brand_name,
            "product": req.product_name,
            "workflow_mode": req.workflow_mode.value,
            "output_types": [item.value for item in req.output_types],
        },
        "canvas": {
            "width": req.layout.canvas_width,
            "height": total_height,
            "background_color": req.layout.background_color,
            "accent_color": req.layout.accent_color,
        },
        "typography": req.typography.model_dump(),
        "layout_settings": req.layout.model_dump(),
        "asset_summary": summarize_assets(ctx.assets),
        "product_info": ctx.product_info,
        "structured_info": ctx.structured_info,
        "brand_profile": ctx.brand_profile,
        "selected_rules": {
            "core_rule": ctx.core_rule,
            "detail_page_rule": ctx.detail_page_rule,
        },
        "design_direction": ctx.design_direction,
        "modules": modules,
        "psd_layers": ctx.psd_layers,
        "design_score": ctx.design_score,
        "outputs": ctx.outputs,
        "review_checklist": ctx.outputs.get("review_checklist", []),
        "feedback_capture": ctx.outputs.get("feedback_capture", {}),
    }


def _esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _wrap(text: str, width: int) -> list[str]:
    if not text:
        return []
    return textwrap.wrap(text, width=width) or [text]


def _asset_name_map(ctx: PipelineContext) -> dict[str, Path]:
    mapping: dict[str, Path] = {}
    for asset in ctx.assets:
        if asset.bucket not in IMAGE_BUCKETS or not asset.saved_path:
            continue
        path = Path(asset.saved_path)
        if path.is_file():
            mapping[asset.name] = path
    return mapping


def _copy_assets_to_output(output_dir: Path, ctx: PipelineContext) -> dict[str, str]:
    """复制图片资产到 outputs/assets，返回文件名 -> 相对路径。"""
    assets_dir = output_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    rel_paths: dict[str, str] = {}
    for name, src in _asset_name_map(ctx).items():
        dest = assets_dir / name
        if not dest.exists() or dest.stat().st_size != src.stat().st_size:
            shutil.copy2(src, dest)
        rel_paths[name] = f"assets/{name}"
    return rel_paths


def _resolve_module_images(
    modules: list[dict[str, Any]], rel_paths: dict[str, str]
) -> None:
    """为每个模块绑定 image_file（相对 outputs 目录）。"""
    available = list(rel_paths.keys())
    if not available:
        return

    for index, module in enumerate(modules):
        if module.get("role") in ("brand_story", "cta"):
            continue

        chosen: str | None = None
        for candidate in module.get("image_candidates") or []:
            if candidate in rel_paths:
                chosen = rel_paths[candidate]
                break

        if not chosen and available:
            chosen = rel_paths[available[index % len(available)]]

        if chosen:
            module["image_file"] = chosen


def _image_data_url(output_dir: Path, relative_path: str) -> str | None:
    path = output_dir / relative_path
    if not path.is_file():
        return None
    mime, _ = mimetypes.guess_type(path.name)
    if not mime or not mime.startswith("image/"):
        mime = "image/jpeg"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def render_preview_svg(spec: dict[str, Any], output_dir: Path | None = None) -> str:
    width = int(spec["canvas"]["width"])
    height = int(spec["canvas"]["height"])
    bg = spec["canvas"]["background_color"]
    accent = spec["canvas"]["accent_color"]
    typo = spec["typography"]
    title_color = typo.get("text_color", "#1f2937")
    title_size = int(typo.get("title_size", 28)) + 6
    body_size = max(13, int(typo.get("body_size", 10)) + 4)

    blocks: list[str] = [
        f'<rect x="0" y="0" width="{width}" height="{height}" fill="{bg}" />'
    ]
    y = 0
    for module in spec["modules"]:
        h = int(module["height"])
        copy = module.get("copy", {})
        plan = module.get("render_plan") or {}
        text_plan = plan.get("text") or {"x": 40, "y": 48, "w": width - 80, "align": "left"}
        image_plan = plan.get("image") or {"enabled": False, "x": 0, "y": 0, "w": 0, "h": 0}
        point_style = str(plan.get("point_style") or "list")
        bg_style = str(plan.get("background") or "card")
        align = str(text_plan.get("align") or "left")
        text_anchor = "middle" if align == "center" else "start"

        if bg_style == "scene":
            blocks.append(f'<rect x="0" y="{y}" width="{width}" height="{h}" fill="#dbe3ea" />')
            blocks.append(
                f'<rect x="0" y="{y}" width="{width}" height="{h}" fill="url(#sceneShade-{module["index"]})" opacity="0.55" />'
            )
            blocks.append(
                f'<defs><linearGradient id="sceneShade-{module["index"]}" x1="0" y1="0" x2="0" y2="1">'
                f'<stop offset="0%" stop-color="#0f172a" stop-opacity="0.04" />'
                f'<stop offset="100%" stop-color="#0f172a" stop-opacity="0.45" />'
                f"</linearGradient></defs>"
            )
        else:
            card_bg = "#ffffff" if module["index"] % 2 else "#f4f6f8"
            blocks.append(f'<rect x="0" y="{y}" width="{width}" height="{h}" fill="{card_bg}" />')

        accent_x = int(text_plan.get("x", 40)) - 16
        accent_y = y + max(26, int(text_plan.get("y", 48)) - 28)
        blocks.append(
            f'<rect x="{accent_x}" y="{accent_y}" width="6" height="40" rx="3" fill="{accent}" />'
        )

        title_x = int(text_plan.get("x", 40)) if align != "center" else int(text_plan.get("x", 40)) + int(text_plan.get("w", width - 80)) // 2
        title_y = y + int(text_plan.get("y", 48))
        blocks.append(
            f'<text x="{title_x}" y="{title_y}" text-anchor="{text_anchor}" '
            f'font-size="{title_size}" font-weight="700" '
            f'font-family="PingFang SC, Microsoft YaHei, sans-serif" fill="{title_color}">'
            f"{_esc(copy.get('headline', module['name']))}</text>"
        )
        cursor = title_y + 30
        if copy.get("subtitle"):
            blocks.append(
                f'<text x="{title_x}" y="{cursor}" text-anchor="{text_anchor}" font-size="{body_size + 3}" '
                f'font-family="PingFang SC, sans-serif" fill="{accent}">{_esc(copy["subtitle"])}</text>'
            )
            cursor += 30

        if image_plan.get("enabled") and int(image_plan.get("w", 0)) > 80 and int(image_plan.get("h", 0)) > 80:
            img_x = int(image_plan.get("x", 0))
            img_y = y + int(image_plan.get("y", 0))
            img_w = int(image_plan.get("w", 0))
            img_h = int(image_plan.get("h", 0))
            image_file = module.get("image_file")
            data_url = _image_data_url(output_dir, image_file) if output_dir and image_file else None
            if data_url:
                blocks.append(
                    f'<clipPath id="clip-{module["index"]}">'
                    f'<rect x="{img_x}" y="{img_y}" width="{img_w}" height="{img_h}" rx="18" />'
                    f"</clipPath>"
                )
                blocks.append(
                    f'<image x="{img_x}" y="{img_y}" width="{img_w}" height="{img_h}" '
                    f'href="{data_url}" preserveAspectRatio="xMidYMid slice" '
                    f'clip-path="url(#clip-{module["index"]})" />'
                )
                if bg_style == "scene":
                    blocks.append(
                        f'<rect x="{img_x}" y="{img_y}" width="{img_w}" height="{img_h}" '
                        f'rx="18" fill="#0f172a" opacity="0.18" />'
                    )
                else:
                    blocks.append(
                        f'<rect x="{img_x}" y="{img_y}" width="{img_w}" height="{img_h}" '
                        f'rx="18" fill="none" stroke="#cbd5e1" />'
                    )
            else:
                placeholder_fill = bg if bg_style != "scene" else "#cbd5e1"
                blocks.append(
                    f'<rect x="{img_x}" y="{img_y}" width="{img_w}" height="{img_h}" '
                    f'rx="18" fill="{placeholder_fill}" stroke="#cbd5e1" stroke-dasharray="9 7" />'
                )
                label = module.get("image_role") or "图片 / 素材占位"
                blocks.append(
                    f'<text x="{img_x + 22}" y="{img_y + 34}" font-size="14" '
                    f'font-family="sans-serif" fill="#94a3b8">{_esc(label)}</text>'
                )

        char_w = max(8, int(body_size * 0.62))
        wrap_chars = max(10, int(text_plan.get("w", width - 80)) // char_w)
        body_lines = _wrap(copy.get("body", ""), wrap_chars)
        body_color = "#e2e8f0" if bg_style == "scene" else "#4b5563"
        point_color = "#f8fafc" if bg_style == "scene" else "#374151"
        for line in body_lines:
            blocks.append(
                f'<text x="{title_x}" y="{cursor + 24}" text-anchor="{text_anchor}" font-size="{body_size}" '
                f'font-family="PingFang SC, sans-serif" fill="{body_color}">{_esc(line)}</text>'
            )
            cursor += int(body_size * 1.7)

        points = copy.get("points", [])[:5]
        if point_style == "cards":
            card_y = y + h - 120
            gap = 16
            card_w = max(100, (width - 80 - gap * (max(1, len(points)) - 1)) // max(1, len(points)))
            card_x = 40
            for point in points:
                blocks.append(
                    f'<rect x="{card_x}" y="{card_y}" width="{card_w}" height="72" rx="14" fill="#ffffff" stroke="#dbe3ea" />'
                )
                wrapped = _wrap(str(point), max(6, (card_w - 24) // char_w))[:2]
                for line_index, line in enumerate(wrapped):
                    blocks.append(
                        f'<text x="{card_x + 16}" y="{card_y + 28 + line_index * 18}" font-size="{body_size - 1}" '
                        f'font-family="PingFang SC, sans-serif" fill="#334155">{_esc(line)}</text>'
                    )
                card_x += card_w + gap
        elif point_style == "table":
            table_x = int(text_plan.get("x", 40))
            table_y = max(cursor + 20, y + 156)
            row_h = 34
            table_w = int(text_plan.get("w", width * 0.4))
            for row_index, point in enumerate(points):
                row_y = table_y + row_index * row_h
                row_fill = "#ffffff" if row_index % 2 == 0 else "#f8fafc"
                blocks.append(
                    f'<rect x="{table_x}" y="{row_y}" width="{table_w}" height="{row_h - 2}" '
                    f'rx="8" fill="{row_fill}" stroke="#dbe3ea" />'
                )
                blocks.append(
                    f'<text x="{table_x + 14}" y="{row_y + 22}" font-size="{body_size}" '
                    f'font-family="PingFang SC, sans-serif" fill="#334155">{_esc(point)}</text>'
                )
        else:
            for point in points:
                blocks.append(
                    f'<circle cx="{int(text_plan.get("x", 40)) + 4}" cy="{cursor + 14}" r="3" fill="{accent}" />'
                )
                blocks.append(
                    f'<text x="{int(text_plan.get("x", 40)) + 16}" y="{cursor + 19}" font-size="{body_size}" '
                    f'font-family="PingFang SC, sans-serif" fill="{point_color}">{_esc(point)}</text>'
                )
                cursor += int(body_size * 1.9)

        y += h

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">\n' + "\n".join(blocks) + "\n</svg>"
    )


def render_photoshop_jsx(spec: dict[str, Any]) -> str:
    payload = json.dumps(spec, ensure_ascii=False, indent=2)
    return """// Photoshop JSX：运行后生成可编辑详情页图层初稿。
// 用法：Photoshop -> 文件 -> 脚本 -> 浏览，选择本文件。
#target photoshop
var spec = %s;

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
  var plan = m.render_plan || {};
  var textPlan = plan.text || { x: 40, y: 60, w: spec.canvas.width - 80 };
  var imagePlan = plan.image || { enabled: false, x: 0, y: 0, w: 0, h: 0 };
  var group = doc.layerSets.add();
  group.name = m.layer_group;

  addText(group, "TXT_主标题", copy.headline, textPlan.x, y + textPlan.y, titleSize + 6, spec.typography.text_color);
  addText(group, "TXT_副标题", copy.subtitle, textPlan.x, y + textPlan.y + 50, spec.typography.subtitle_size, spec.canvas.accent_color);
  addText(group, "TXT_正文", copy.body, textPlan.x, y + textPlan.y + 92, bodySize, "#4b5563");

  var points = copy.points || [];
  for (var p = 0; p < points.length; p++) {
    if ((plan.point_style || "list") === "cards") {
      addText(group, "TXT_要点" + (p + 1), points[p], 40 + p * 180, y + m.height - 60, bodySize, "#374151");
    } else if ((plan.point_style || "list") === "table") {
      addText(group, "TXT_要点" + (p + 1), points[p], textPlan.x, y + 180 + p * 34, bodySize, "#374151");
    } else {
      addText(group, "TXT_要点" + (p + 1), "· " + points[p], textPlan.x, y + textPlan.y + 132 + p * 28, bodySize, "#374151");
    }
  }

  if (imagePlan.enabled && m.image_file) {
    var scriptFile = new File($.fileName);
    var imageFile = new File(scriptFile.parent.fsName + "/" + m.image_file);
    if (imageFile.exists) {
      var imgDoc = app.open(imageFile);
      try {
        var imgLayer = imgDoc.activeLayer.duplicate(group, ElementPlacement.INSIDE);
        imgLayer.name = "IMG_" + (m.image_role || "图片");
        var imgX = imagePlan.x;
        var imgTop = y + imagePlan.y;
        var imgW = imagePlan.w;
        var imgH = imagePlan.h;
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
  } else if (imagePlan.enabled) {
    var placeholder = doc.artLayers.add();
    placeholder.name = "IMG_" + (m.image_role || "图片占位");
    placeholder.move(group, ElementPlacement.INSIDE);
  }

  y += m.height;
}

var outFile = new File((new File($.fileName)).parent.fsName + "/editable_detail_page.psd");
var psdOptions = new PhotoshopSaveOptions();
psdOptions.layers = true;
doc.saveAs(outFile, psdOptions, true, Extension.LOWERCASE);
""" % payload


def render_figma_plugin_ts(spec: dict[str, Any]) -> str:
    payload = json.dumps(spec, ensure_ascii=False, indent=2)
    return """// Figma Plugin 脚本：在 Figma 插件中运行后生成可编辑详情页 Frame。
// 用法：创建一个空插件，将本文件内容粘贴到 code.ts，运行插件。
const spec = %s;

async function main() {
  await figma.loadFontAsync({ family: "Inter", style: "Regular" });
  await figma.loadFontAsync({ family: "Inter", style: "Bold" });

  const frame = figma.createFrame();
  frame.name = `${spec.project.brand} / ${spec.project.product} / Detail Page`;
  frame.resize(spec.canvas.width, spec.canvas.height);
  frame.fills = [{ type: "SOLID", color: hexToRgb(spec.canvas.background_color) }];
  frame.layoutMode = "VERTICAL";
  frame.counterAxisSizingMode = "FIXED";
  frame.primaryAxisSizingMode = "FIXED";

  let y = 0;
  for (const module of spec.modules) {
    const section = figma.createFrame();
    section.name = module.layer_group || `${module.index}_Module`;
    section.resize(spec.canvas.width, module.height);
    section.x = 0;
    section.y = y;
    const plan = module.render_plan || {};
    const textPlan = plan.text || { x: 40, y: 64, w: spec.canvas.width - 80, align: "left" };
    const imagePlan = plan.image || { enabled: false, x: 0, y: 0, w: 0, h: 0 };
    const bgColor = (plan.background || "card") === "scene"
      ? "#dbe3ea"
      : (module.index %% 2 ? "#ffffff" : "#f4f6f8");
    section.fills = [{ type: "SOLID", color: hexToRgb(bgColor) }];
    frame.appendChild(section);

    const accent = figma.createRectangle();
    accent.name = "BG_品牌强调条";
    accent.resize(6, 40);
    accent.x = 24;
    accent.y = 30;
    accent.cornerRadius = 3;
    accent.fills = [{ type: "SOLID", color: hexToRgb(spec.canvas.accent_color) }];
    section.appendChild(accent);

    const copy = module.copy || {};
    addText(section, "TXT_主标题", copy.headline || module.name, textPlan.x, textPlan.y, spec.typography.title_size + 8, true, spec.typography.text_color);
    addText(section, "TXT_副标题", copy.subtitle || "", textPlan.x, textPlan.y + 48, spec.typography.subtitle_size + 2, false, spec.canvas.accent_color);
    addText(section, "TXT_正文", copy.body || "", textPlan.x, textPlan.y + 90, Math.max(14, spec.typography.body_size + 4), false, "#4b5563");
    (copy.points || []).slice(0, 5).forEach((point: string, index: number) => {
      const pointStyle = plan.point_style || "list";
      const pointX = pointStyle === "cards" ? 40 + index * 180 : textPlan.x;
      const pointY = pointStyle === "cards" ? module.height - 60 : (pointStyle === "table" ? 190 + index * 34 : textPlan.y + 140 + index * 28);
      const pointText = pointStyle === "list" ? `• ${point}` : point;
      addText(section, `TXT_要点${index + 1}`, pointText, pointX, pointY, Math.max(14, spec.typography.body_size + 4), false, "#374151");
    });

    if (imagePlan.enabled) {
      const imageBox = figma.createRectangle();
      imageBox.name = `IMG_${module.image_role || "图片占位"}${module.image_file ? ` / ${module.image_file}` : ""}`;
      imageBox.x = imagePlan.x;
      imageBox.y = imagePlan.y;
      imageBox.resize(Math.max(120, imagePlan.w), Math.max(120, imagePlan.h));
      imageBox.cornerRadius = 18;
      imageBox.fills = [{ type: "SOLID", color: hexToRgb("#e2e8f0") }];
      imageBox.strokes = [{ type: "SOLID", color: hexToRgb("#cbd5e1") }];
      section.appendChild(imageBox);
      addText(section, "IMG_替换提示", module.image_file ? `替换为 ${module.image_file}` : (module.image_role || "图片素材占位"), imageBox.x + 20, imageBox.y + 34, 14, false, "#64748b");
    }

    y += module.height;
  }

  figma.currentPage.appendChild(frame);
  figma.viewport.scrollAndZoomIntoView([frame]);
  figma.closePlugin("BrandOS 可编辑 Figma 页面已生成");
}

function addText(parent: FrameNode, name: string, content: string, x: number, y: number, size: number, bold: boolean, color: string) {
  if (!content) return;
  const text = figma.createText();
  text.name = name;
  text.characters = content;
  text.fontName = { family: "Inter", style: bold ? "Bold" : "Regular" };
  text.fontSize = size;
  text.x = x;
  text.y = y;
  text.fills = [{ type: "SOLID", color: hexToRgb(color) }];
  text.resizeWithoutConstraints(Math.max(80, spec.canvas.width * 0.36), text.height);
  parent.appendChild(text);
}

function hexToRgb(hex: string) {
  const normalized = String(hex || "#ffffff").replace("#", "");
  const value = parseInt(normalized.length === 3 ? normalized.split("").map((c) => c + c).join("") : normalized, 16);
  return {
    r: ((value >> 16) & 255) / 255,
    g: ((value >> 8) & 255) / 255,
    b: (value & 255) / 255,
  };
}

main();
""" % payload


def render_editable_html(spec: dict[str, Any]) -> str:
    modules = []
    for module in spec["modules"]:
        copy = module.get("copy", {})
        points = "".join(
            f'<li contenteditable="true">{_esc(point)}</li>'
            for point in copy.get("points", [])[:5]
        )
        image = (
            f'<div class="image-box" contenteditable="true">替换图片：{_esc(module.get("image_file") or module.get("image_role") or "图片素材")}</div>'
            if module.get("role") not in ("brand_story", "cta")
            else ""
        )
        modules.append(
            f"""
            <section class="module" style="min-height:{int(module["height"])}px">
              <div class="copy">
                <div class="accent"></div>
                <h2 contenteditable="true">{_esc(copy.get("headline") or module["name"])}</h2>
                <h3 contenteditable="true">{_esc(copy.get("subtitle") or "")}</h3>
                <p contenteditable="true">{_esc(copy.get("body") or "")}</p>
                <ul>{points}</ul>
              </div>
              {image}
            </section>
            """
        )
    return textwrap.dedent(
        f"""<!doctype html>
        <html lang="zh-CN">
        <head>
          <meta charset="utf-8" />
          <title>{_esc(spec["project"]["name"])} - 可编辑审稿稿</title>
          <style>
            body {{ margin: 0; background: #e5e7eb; font-family: "PingFang SC", "Microsoft YaHei", sans-serif; }}
            .page {{ width: {int(spec["canvas"]["width"])}px; margin: 24px auto; background: {_esc(spec["canvas"]["background_color"])}; box-shadow: 0 18px 50px rgba(15,23,42,.18); }}
            .toolbar {{ position: sticky; top: 0; z-index: 2; padding: 12px 16px; background: #111827; color: white; font-size: 13px; }}
            .module {{ display: grid; grid-template-columns: 38% 1fr; gap: 30px; padding: 36px 40px; border-bottom: 1px solid #d8dee9; background: white; }}
            .module:nth-child(even) {{ background: #f8fafc; }}
            .copy {{ position: relative; }}
            .accent {{ width: 6px; height: 40px; border-radius: 4px; background: {_esc(spec["canvas"]["accent_color"])}; margin-bottom: 18px; }}
            h2 {{ margin: 0 0 14px; font-size: {int(spec["typography"].get("title_size", 28)) + 8}px; color: {_esc(spec["typography"].get("text_color", "#1f2937"))}; }}
            h3 {{ min-height: 24px; margin: 0 0 18px; font-size: {int(spec["typography"].get("subtitle_size", 18)) + 2}px; color: {_esc(spec["canvas"]["accent_color"])}; }}
            p, li {{ color: #475569; font-size: {max(14, int(spec["typography"].get("body_size", 10)) + 4)}px; line-height: 1.7; }}
            ul {{ padding-left: 18px; }}
            .image-box {{ min-height: 260px; display: grid; place-items: center; border: 1px dashed #94a3b8; border-radius: 20px; background: #e2e8f0; color: #64748b; text-align: center; padding: 20px; }}
            [contenteditable="true"] {{ outline: 1px dashed transparent; border-radius: 6px; }}
            [contenteditable="true"]:focus {{ outline-color: #4f46e5; background: #eef2ff; }}
          </style>
        </head>
        <body>
          <div class="toolbar">BrandOS 可编辑审稿稿：点击文字或图片占位说明即可修改，用于设计师初审与反馈记录。</div>
          <main class="page">
            {"".join(modules)}
          </main>
        </body>
        </html>"""
    )


def render_readme(spec: dict[str, Any]) -> str:
    modules = "\n".join(
        f"- {m['index']:02d} {m['name']}（{m.get('copy', {}).get('headline', '')}）"
        for m in spec["modules"]
    )
    return textwrap.dedent(
        f"""
        # {spec["project"]["name"]} 导出包

        按照「品牌知识库 / 规则版本 → Product Brief → 页面规划 → Image Studio → Layout Engine → Figma / PSD → Design Score → 反馈记录」流程生成。

        ## 文件说明
        - `design_spec.json`：完整结构（含品牌规则分层、模块文案、Figma/PSD 图层树、设计评分、审核清单）。
        - `preview.svg`：详情页低保真预览图（已嵌入上传的产品图/参考图）。
        - `assets/`：本次任务使用的产品图与参考图副本，供 PSD 脚本引用。
        - `create_detail_page.jsx`：Photoshop 脚本，运行后生成并保存 `editable_detail_page.psd`，包含可编辑文字层、图片层与图层分组。
        - `create_figma_page.ts`：Figma 插件脚本，运行后生成可编辑 Frame、文本层和图片占位层。
        - `editable_detail_page.html`：浏览器可编辑审稿稿，用于快速改文案和记录反馈。

        ## 模块结构
        {modules}

        ## 说明
        当前版本为 BrandOS MVP 初稿：AI 负责品牌规则消费、页面结构、文案、版式和设计稿结构规划；
        高清素材替换、抠图调色与最终审稿仍需设计师完成。设计师修改会作为反馈数据记录，不会自动覆盖品牌核心规则。
        """
    ).strip()


def write_artifacts(
    output_dir: Path, spec: dict[str, Any], ctx: PipelineContext
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    rel_paths = _copy_assets_to_output(output_dir, ctx)
    _resolve_module_images(spec["modules"], rel_paths)
    files = {
        "preview_svg": output_dir / "preview.svg",
        "design_spec": output_dir / "design_spec.json",
        "photoshop_jsx": output_dir / "create_detail_page.jsx",
        "figma_plugin": output_dir / "create_figma_page.ts",
        "editable_html": output_dir / "editable_detail_page.html",
        "readme": output_dir / "README.md",
    }
    files["preview_svg"].write_text(
        render_preview_svg(spec, output_dir), encoding="utf-8"
    )
    files["design_spec"].write_text(
        json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    files["photoshop_jsx"].write_text(render_photoshop_jsx(spec), encoding="utf-8")
    files["figma_plugin"].write_text(render_figma_plugin_ts(spec), encoding="utf-8")
    files["editable_html"].write_text(render_editable_html(spec), encoding="utf-8")
    files["readme"].write_text(render_readme(spec), encoding="utf-8")
    return {key: str(value) for key, value in files.items()}
