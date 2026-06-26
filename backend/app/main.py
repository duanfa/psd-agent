from __future__ import annotations

import json
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import ValidationError

from .defaults import load_workflow_defaults
from .file_utils import save_uploaded_assets
from .models import (
    AssetRole,
    AssetTrainingStatus,
    BrandAssetRecord,
    RunArtifactRefs,
    UploadedAsset,
    WorkflowArtifacts,
    WorkflowRequest,
    WorkflowResult,
    WorkflowRunRecord,
    generate_id,
    utc_now_iso,
)
from .pipeline import WorkflowCancelled, classify_asset, run_pipeline
from .render import build_design_spec, write_artifacts
from .routers.assets import router as assets_router
from .routers.brands import router as brands_router
from .routers.rule_versions import router as rule_versions_router
from .routers.runs import router as runs_router
from .runtime import append_log, get_run_snapshot, set_run_state
from .store import get_store

APP_ROOT = Path(__file__).resolve().parents[1]
RUNS_ROOT = APP_ROOT / "runs"
CANCELLED_RUNS: set[str] = set()

app = FastAPI(title="BrandOS AI Design Platform", version="0.3.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(brands_router)
app.include_router(assets_router)
app.include_router(rule_versions_router)
app.include_router(runs_router)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/workflows/{run_id}/cancel")
def cancel_workflow(run_id: str) -> dict[str, str]:
    CANCELLED_RUNS.add(run_id)
    append_log(run_id, "Workflow", "收到用户取消请求")
    set_run_state(run_id, "cancelling", None)
    return {"status": "cancelling", "run_id": run_id}


@app.get("/api/workflows/{run_id}/logs")
def workflow_logs(run_id: str) -> dict[str, object]:
    return get_run_snapshot(run_id)


@app.get("/api/config/defaults")
def config_defaults() -> dict[str, object]:
    defaults = load_workflow_defaults()
    return {
        "payload": defaults,
        "prompts": defaults["prompts"],
        "workflowModes": ["smart_recommend", "strict_brand"],
        "outputTypes": ["detail_page", "figma_page", "psd_file", "main_image", "banner"],
        "stages": [
            {"id": "product_understanding", "title": "商品理解 Agent", "icon": "eye"},
            {"id": "product_brief", "title": "Product Brief", "icon": "layers"},
            {"id": "brand_knowledge", "title": "品牌知识库 / 规则版本", "icon": "library"},
            {"id": "page_planner", "title": "页面规划 Agent", "icon": "palette"},
            {"id": "layout_engine", "title": "Layout Engine", "icon": "grid"},
            {"id": "copy", "title": "文案 Agent", "icon": "type"},
            {"id": "figma_psd", "title": "Figma / PSD 生成 Agent", "icon": "file-image"},
            {"id": "design_score", "title": "Design Score", "icon": "check-circle"},
            {"id": "output_review", "title": "输出、审核与反馈", "icon": "check-circle"},
        ],
    }


def _safe_filename(name: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "._-()[] " else "_" for ch in name)
    return cleaned.strip() or "asset"


def _safe_run_id(run_id: str | None) -> str:
    if not run_id:
        return uuid.uuid4().hex
    cleaned = "".join(ch if ch.isalnum() or ch in "-_" else "" for ch in run_id)
    return cleaned[:80] or uuid.uuid4().hex


def _merge_payload(incoming: dict) -> dict:
    data = load_workflow_defaults()
    for key, value in incoming.items():
        if isinstance(data.get(key), dict) and isinstance(value, dict):
            merged = dict(data[key])
            merged.update(value)
            data[key] = merged
        else:
            data[key] = value
    return data


def _resolve_brand_context(request: WorkflowRequest):
    store = get_store()
    brand_id = request.brand_id or "brand_default"
    brand = store.get_brand(brand_id)
    if not brand:
        raise HTTPException(status_code=404, detail="brand not found")
    rule_version = (
        store.get_rule_version(request.rule_version_id)
        if request.rule_version_id
        else store.get_current_rule_version(brand.id)
    )
    request.brand_id = brand.id
    request.brand_name = brand.name
    if rule_version:
        request.rule_version_id = rule_version.id
        core_rule = rule_version.brand_profile.get("core_rule", {})
        asset_memory = rule_version.brand_profile.get("asset_memory", {})
        guidelines = str(core_rule.get("brand_guidelines", "")).strip()
        reference_notes = str(asset_memory.get("reference_notes", "")).strip()
        if guidelines and guidelines not in request.brand_guidelines:
            request.brand_guidelines = "\n\n".join(
                part for part in [guidelines, request.brand_guidelines] if part
            )
        if reference_notes and reference_notes not in request.reference_notes:
            request.reference_notes = "\n\n".join(
                part for part in [reference_notes, request.reference_notes] if part
            )
    return brand, rule_version


def _register_workflow_assets(brand_id: str | None, assets: list[UploadedAsset]) -> list[str]:
    if not brand_id:
        return []
    store = get_store()
    referenced_ids: list[str] = []
    for asset in assets:
        asset_record = BrandAssetRecord(
            id=generate_id("asset"),
            brand_id=brand_id,
            name=asset.name,
            content_type=asset.content_type,
            size=asset.size,
            bucket=asset.bucket,
            role=(
                AssetRole.high_quality_case
                if asset.bucket in {"image", "reference_image"}
                else AssetRole.reference
            ),
            training_status=(
                AssetTrainingStatus.candidate
                if asset.bucket in {"image", "reference_image", "brief"}
                else AssetTrainingStatus.excluded
            ),
            path=asset.saved_path or "",
            source="workflow_input",
            notes="由工作流上传自动登记的任务输入资产。",
        )
        store.create_asset(asset_record)
        referenced_ids.append(asset_record.id)
    return referenced_ids


@app.post("/api/workflows/generate", response_model=WorkflowResult)
async def generate_workflow(
    payload: str = Form(...),
    client_run_id: str | None = Form(default=None),
    files: list[UploadFile] = File(default=[]),
    brief_files: list[UploadFile] = File(default=[]),
    reference_images: list[UploadFile] = File(default=[]),
) -> WorkflowResult:
    try:
        incoming = json.loads(payload)
        if not isinstance(incoming, dict):
            raise ValueError("payload 必须是 JSON 对象")
        request = WorkflowRequest.model_validate(_merge_payload(incoming))
    except (json.JSONDecodeError, ValidationError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    run_id = _safe_run_id(client_run_id)
    CANCELLED_RUNS.discard(run_id)
    run_dir = RUNS_ROOT / run_id
    input_dir = run_dir / "inputs"
    output_dir = run_dir / "outputs"
    assets = [
        *await save_uploaded_assets(files, input_dir / "assets"),
        *await save_uploaded_assets(brief_files, input_dir / "brief", bucket_override="brief"),
        *await save_uploaded_assets(
            reference_images,
            input_dir / "reference_images",
            bucket_override="reference_image",
        ),
    ]

    spreadsheet_text = "\n\n".join(
        asset.extracted_text or "" for asset in assets if asset.extracted_text
    ).strip()
    if spreadsheet_text and spreadsheet_text not in request.product_brief:
        request.product_brief = "\n\n".join(
            part for part in [request.product_brief, spreadsheet_text] if part
        )

    brand, rule_version = _resolve_brand_context(request)
    referenced_asset_ids = _register_workflow_assets(request.brand_id, assets)
    store = get_store()
    run_started_at = utc_now_iso()
    store.create_run(
        WorkflowRunRecord(
            id=run_id,
            brand_id=request.brand_id,
            rule_version_id=request.rule_version_id,
            project_name=request.project_name,
            product_name=request.product_name,
            status="queued",
            workflow_mode=request.workflow_mode.value,
            output_types=[item.value for item in request.output_types],
            input_payload=request.model_dump(by_alias=True),
            referenced_asset_ids=referenced_asset_ids,
            asset_names=[asset.name for asset in assets],
            run_started_at=run_started_at,
        )
    )

    try:
        stages, ctx = run_pipeline(
            request,
            assets,
            run_id=run_id,
            brand=brand,
            rule_version=rule_version,
            referenced_asset_ids=referenced_asset_ids,
            cancel_checker=lambda: run_id in CANCELLED_RUNS,
        )
    except WorkflowCancelled as exc:
        CANCELLED_RUNS.discard(run_id)
        set_run_state(run_id, "cancelled", None)
        store.update_run(
            run_id,
            status="cancelled",
            run_finished_at=utc_now_iso(),
        )
        raise HTTPException(status_code=499, detail=str(exc)) from exc
    except Exception:
        CANCELLED_RUNS.discard(run_id)
        set_run_state(run_id, "failed", None)
        store.update_run(
            run_id,
            status="failed",
            run_finished_at=utc_now_iso(),
        )
        raise
    CANCELLED_RUNS.discard(run_id)
    spec = build_design_spec(ctx)
    artifact_paths = write_artifacts(output_dir, spec, ctx)

    used_model = any(stage.used_model for stage in stages)
    agent_report = "\n\n".join(ctx.report_parts)
    run_finished_at = utc_now_iso()
    final_status = "completed" if used_model else "fallback_completed"
    artifacts = WorkflowArtifacts(
        run_id=run_id,
        output_dir=str(output_dir),
        **artifact_paths,
    )
    store.update_run(
        run_id,
        status=final_status,
        run_finished_at=run_finished_at,
        warnings=ctx.warnings,
        artifacts=RunArtifactRefs(
            output_dir=artifacts.output_dir,
            preview_svg=artifacts.preview_svg,
            design_spec=artifacts.design_spec,
            photoshop_jsx=artifacts.photoshop_jsx,
            readme=artifacts.readme,
        ),
    )

    return WorkflowResult(
        run_id=run_id,
        status=final_status,
        brand_id=request.brand_id,
        rule_version_id=request.rule_version_id,
        summary="BrandOS 设计任务已完成：含品牌规则分层、页面结构、SVG 预览、Figma/PSD 结构说明、评分与反馈清单。",
        used_deepagents=used_model,
        stages=stages,
        agent_report=agent_report,
        design_spec=spec,
        artifacts=artifacts,
        assets=assets,
        warnings=ctx.warnings,
        run_started_at=run_started_at,
        run_finished_at=run_finished_at,
        referenced_asset_ids=referenced_asset_ids,
    )


@app.get("/api/workflows/{run_id}/artifacts/{name}")
def download_artifact(run_id: str, name: str) -> FileResponse:
    allowed = {
        "preview.svg": "image/svg+xml",
        "design_spec.json": "application/json",
        "create_detail_page.jsx": "text/plain",
        "README.md": "text/markdown",
    }
    if name not in allowed:
        raise HTTPException(status_code=404, detail="artifact not found")
    path = RUNS_ROOT / run_id / "outputs" / name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="artifact not found")
    return FileResponse(path, media_type=allowed[name], filename=name)
