from __future__ import annotations

from typing import Any, Mapping, Sequence

from .models import UploadedAsset
from .wireframe import compact_wireframe_json, wireframe_summary_text


def _clip(text: str, limit: int) -> str:
    cleaned = text.strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 8].rstrip() + "\n...(截断)"


def _dedupe_lines(lines: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for raw in lines:
        line = str(raw).strip()
        if not line or line in seen:
            continue
        seen.add(line)
        unique.append(line)
    return unique


def _meaningful_spreadsheet_lines(text: str) -> list[str]:
    items: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("[WireframeSpec]") or line.startswith("[SheetWireframe]"):
            continue
        if line.startswith("- cell ") or line.startswith("- image ") or line.startswith("- shape "):
            continue
        items.append(line)
    return _dedupe_lines(items)


def _wireframe_spec(metadata: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(metadata, Mapping):
        return None
    spec = metadata.get("wireframe_spec")
    return dict(spec) if isinstance(spec, dict) else None


def build_asset_input_layers(
    asset_name: str,
    extracted_text: str | None,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, str]:
    text = str(extracted_text or "").strip()
    spec = _wireframe_spec(metadata)

    brief_lines = _meaningful_spreadsheet_lines(text)
    brief_summary = ""
    if brief_lines:
        summary_lines = [f"[来源文件] {asset_name}", *brief_lines[:18]]
        brief_summary = _clip("\n".join(summary_lines), 2400)

    layout_reference = ""
    if spec:
        layout_reference = _clip(wireframe_summary_text(spec, max_chars=3600), 3600)

    raw_wireframe_dump = ""
    if spec:
        raw_wireframe_dump = compact_wireframe_json(spec, max_chars=12000)

    return {
        key: value
        for key, value in {
            "brief_summary": brief_summary,
            "layout_reference": layout_reference,
            "raw_wireframe_dump": raw_wireframe_dump,
        }.items()
        if value
    }


def _asset_to_mapping(asset: UploadedAsset | Mapping[str, Any]) -> Mapping[str, Any]:
    if isinstance(asset, UploadedAsset):
        return asset.model_dump()
    return asset


def build_input_layers(
    user_brief: str,
    assets: Sequence[UploadedAsset | Mapping[str, Any]],
) -> dict[str, Any]:
    brief_summaries: list[str] = []
    layout_references: list[str] = []
    raw_wireframe_dumps: list[str] = []
    sources: list[dict[str, Any]] = []

    for item in assets:
        asset = _asset_to_mapping(item)
        metadata = asset.get("metadata")
        layers = metadata.get("input_layers") if isinstance(metadata, Mapping) else None
        if not isinstance(layers, Mapping):
            layers = build_asset_input_layers(
                asset_name=str(asset.get("name") or "asset"),
                extracted_text=str(asset.get("extracted_text") or ""),
                metadata=metadata if isinstance(metadata, Mapping) else {},
            )
        brief_summary = str(layers.get("brief_summary") or "").strip()
        layout_reference = str(layers.get("layout_reference") or "").strip()
        raw_wireframe_dump = str(layers.get("raw_wireframe_dump") or "").strip()
        if not any((brief_summary, layout_reference, raw_wireframe_dump)):
            continue
        if brief_summary:
            brief_summaries.append(brief_summary)
        if layout_reference:
            layout_references.append(layout_reference)
        if raw_wireframe_dump:
            raw_wireframe_dumps.append(raw_wireframe_dump)
        sources.append(
            {
                "name": str(asset.get("name") or ""),
                "bucket": str(asset.get("bucket") or ""),
                "has_brief_summary": bool(brief_summary),
                "has_layout_reference": bool(layout_reference),
                "has_raw_wireframe_dump": bool(raw_wireframe_dump),
            }
        )

    user_brief_text = str(user_brief or "").strip()
    summary_parts = []
    if user_brief_text:
        summary_parts.append(f"[用户 brief]\n{_clip(user_brief_text, 1800)}")
    if brief_summaries:
        summary_parts.extend(item for item in brief_summaries if item)

    return {
        "user_brief": user_brief_text,
        "brief_summary": _clip("\n\n".join(summary_parts), 4200) if summary_parts else "",
        "layout_reference": _clip(
            "\n\n".join(item for item in layout_references if item),
            4200,
        )
        if layout_references
        else "",
        "raw_wireframe_dump": _clip(
            "\n\n".join(item for item in raw_wireframe_dumps if item),
            12000,
        )
        if raw_wireframe_dumps
        else "",
        "sources": sources,
        "brief_asset_count": len(brief_summaries),
        "wireframe_asset_count": len(layout_references),
    }


def normalize_input_layers(layers: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(layers, Mapping):
        return {}

    brief_summary = str(layers.get("brief_summary") or "").strip()
    layout_reference = str(layers.get("layout_reference") or "").strip()
    raw_wireframe_dump = str(layers.get("raw_wireframe_dump") or "").strip()

    raw_sources = layers.get("sources")
    sources: list[dict[str, Any]] = []
    if isinstance(raw_sources, Sequence) and not isinstance(raw_sources, str | bytes):
        for item in raw_sources:
            if not isinstance(item, Mapping):
                continue
            sources.append(
                {
                    "name": str(item.get("name") or ""),
                    "bucket": str(item.get("bucket") or ""),
                    "has_brief_summary": bool(item.get("has_brief_summary")),
                    "has_layout_reference": bool(item.get("has_layout_reference")),
                    "has_raw_wireframe_dump": bool(item.get("has_raw_wireframe_dump")),
                }
            )

    brief_asset_count = int(layers.get("brief_asset_count") or 0)
    if not brief_asset_count and sources:
        brief_asset_count = sum(1 for item in sources if item["has_brief_summary"])

    wireframe_asset_count = int(layers.get("wireframe_asset_count") or 0)
    if not wireframe_asset_count and sources:
        wireframe_asset_count = sum(1 for item in sources if item["has_layout_reference"])

    user_brief = str(layers.get("user_brief") or "").strip()
    if not any((user_brief, brief_summary, layout_reference, raw_wireframe_dump, sources)):
        return {}

    return {
        "user_brief": user_brief,
        "brief_summary": brief_summary,
        "layout_reference": layout_reference,
        "raw_wireframe_dump": raw_wireframe_dump,
        "sources": sources,
        "brief_asset_count": brief_asset_count,
        "wireframe_asset_count": wireframe_asset_count,
    }


def detail_input_layers(
    layers: Mapping[str, Any] | None,
    *,
    raw_limit: int = 4000,
) -> dict[str, Any]:
    normalized = normalize_input_layers(layers)
    if not normalized:
        return {}

    raw_wireframe_dump = str(normalized.get("raw_wireframe_dump") or "")
    safe_raw_dump = _clip(raw_wireframe_dump, raw_limit) if raw_limit > 0 and raw_wireframe_dump else raw_wireframe_dump

    return {
        **normalized,
        "raw_wireframe_dump": safe_raw_dump,
        "raw_wireframe_dump_chars": len(raw_wireframe_dump),
        "raw_wireframe_dump_truncated": bool(raw_wireframe_dump and safe_raw_dump != raw_wireframe_dump),
    }


def semantic_brief_text(layers: Mapping[str, Any] | None) -> str:
    if not isinstance(layers, Mapping):
        return ""
    return str(layers.get("brief_summary") or "").strip()


def render_input_prompt(
    layers: Mapping[str, Any] | None,
    *,
    include_layout_reference: bool = False,
    include_raw_wireframe_dump: bool = False,
) -> str:
    if not isinstance(layers, Mapping):
        return ""

    sections: list[str] = []
    brief_summary = str(layers.get("brief_summary") or "").strip()
    layout_reference = str(layers.get("layout_reference") or "").strip()
    raw_wireframe_dump = str(layers.get("raw_wireframe_dump") or "").strip()

    if brief_summary:
        sections.append(f"brief_summary：\n{brief_summary}")
    if include_layout_reference and layout_reference:
        sections.append(f"layout_reference：\n{layout_reference}")
    if include_raw_wireframe_dump and raw_wireframe_dump:
        sections.append(
            "raw_wireframe_dump（仅用于审计/兜底，不要原样复述到最终文案或结构中）：\n"
            f"{raw_wireframe_dump}"
        )
    if not sections:
        return ""
    return "输入资料（分层注入）：\n" + "\n\n".join(sections)


def input_layers_log_payload(layers: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(layers, Mapping):
        return {}
    return {
        "brief_asset_count": int(layers.get("brief_asset_count") or 0),
        "wireframe_asset_count": int(layers.get("wireframe_asset_count") or 0),
        "sources": list(layers.get("sources") or []),
        "brief_summary_chars": len(str(layers.get("brief_summary") or "")),
        "layout_reference_chars": len(str(layers.get("layout_reference") or "")),
        "raw_wireframe_dump_chars": len(str(layers.get("raw_wireframe_dump") or "")),
        "injection_mode": "layered_summary_and_layout_reference",
    }
