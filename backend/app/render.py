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


def build_design_spec(ctx: PipelineContext) -> dict[str, Any]:
    req = ctx.request
    modules = ctx.modules
    total_height = sum(int(m["height"]) for m in modules) or req.layout.hero_height
    return {
        "project": {
            "name": req.project_name,
            "brand": req.brand_name,
            "brand_id": req.brand_id,
            "product": req.product_name,
            "workflow_mode": req.workflow_mode.value,
            "output_types": [item.value for item in req.output_types],
            "rule_version_id": req.rule_version_id,
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
        "referenced_asset_ids": ctx.referenced_asset_ids,
        "product_info": ctx.product_info,
        "structured_info": ctx.structured_info,
        "brand_profile": ctx.brand_profile,
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
    pad = 40
    for module in spec["modules"]:
        h = int(module["height"])
        copy = module.get("copy", {})
        role = module.get("role", "feature")
        card_bg = "#ffffff" if module["index"] % 2 else "#f4f6f8"
        blocks.append(
            f'<rect x="0" y="{y}" width="{width}" height="{h}" fill="{card_bg}" />'
        )
        blocks.append(
            f'<rect x="{pad - 16}" y="{y + 30}" width="6" height="40" rx="3" fill="{accent}" />'
        )
        blocks.append(
            f'<text x="{pad}" y="{y + 64}" font-size="{title_size}" font-weight="700" '
            f'font-family="PingFang SC, Microsoft YaHei, sans-serif" fill="{title_color}">'
            f"{_esc(copy.get('headline', module['name']))}</text>"
        )
        cursor = y + 64 + 30
        if copy.get("subtitle"):
            blocks.append(
                f'<text x="{pad}" y="{cursor}" font-size="{body_size + 3}" '
                f'font-family="PingFang SC, sans-serif" fill="{accent}">{_esc(copy["subtitle"])}</text>'
            )
            cursor += 30

        # 图片区：优先嵌入实际上传素材，否则显示占位
        img_top = cursor + 6
        img_bottom = y + h - 36
        if role not in ("brand_story", "cta") and img_bottom - img_top > 80:
            img_x = int(width * 0.40)
            img_w = width - img_x - pad
            img_h = img_bottom - img_top
            image_file = module.get("image_file")
            data_url = (
                _image_data_url(output_dir, image_file)
                if output_dir and image_file
                else None
            )
            if data_url:
                blocks.append(
                    f'<clipPath id="clip-{module["index"]}">'
                    f'<rect x="{img_x}" y="{img_top}" width="{img_w}" height="{img_h}" rx="18" />'
                    f"</clipPath>"
                )
                blocks.append(
                    f'<image x="{img_x}" y="{img_top}" width="{img_w}" height="{img_h}" '
                    f'href="{data_url}" preserveAspectRatio="xMidYMid slice" '
                    f'clip-path="url(#clip-{module["index"]})" />'
                )
                blocks.append(
                    f'<rect x="{img_x}" y="{img_top}" width="{img_w}" height="{img_h}" '
                    f'rx="18" fill="none" stroke="#cbd5e1" />'
                )
            else:
                blocks.append(
                    f'<rect x="{img_x}" y="{img_top}" width="{img_w}" height="{img_h}" '
                    f'rx="18" fill="{bg}" stroke="#cbd5e1" stroke-dasharray="9 7" />'
                )
                label = module.get("image_role") or "图片 / 素材占位"
                blocks.append(
                    f'<text x="{img_x + 22}" y="{img_top + 34}" font-size="14" '
                    f'font-family="sans-serif" fill="#94a3b8">{_esc(label)}</text>'
                )
            text_width = img_x - pad - 8
        else:
            text_width = width - pad * 2

        char_w = max(8, int(body_size * 0.62))
        wrap_chars = max(10, text_width // char_w)
        body_lines = _wrap(copy.get("body", ""), wrap_chars)
        for line in body_lines:
            blocks.append(
                f'<text x="{pad}" y="{cursor + 24}" font-size="{body_size}" '
                f'font-family="PingFang SC, sans-serif" fill="#4b5563">{_esc(line)}</text>'
            )
            cursor += int(body_size * 1.7)

        for point in copy.get("points", [])[:5]:
            blocks.append(
                f'<circle cx="{pad + 4}" cy="{cursor + 14}" r="3" fill="{accent}" />'
            )
            blocks.append(
                f'<text x="{pad + 16}" y="{cursor + 19}" font-size="{body_size}" '
                f'font-family="PingFang SC, sans-serif" fill="#374151">{_esc(point)}</text>'
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
""" % payload


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
        - `create_detail_page.jsx`：PSD 兼容脚本，运行后生成可编辑文字层、图片层与图层分组初稿。

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
        "readme": output_dir / "README.md",
    }
    files["preview_svg"].write_text(
        render_preview_svg(spec, output_dir), encoding="utf-8"
    )
    files["design_spec"].write_text(
        json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    files["photoshop_jsx"].write_text(render_photoshop_jsx(spec), encoding="utf-8")
    files["readme"].write_text(render_readme(spec), encoding="utf-8")
    return {key: str(value) for key, value in files.items()}
