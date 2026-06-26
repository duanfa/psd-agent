from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import ValidationError

from . import database
from .defaults import load_workflow_defaults
from .models import UploadedAsset, WorkflowArtifacts, WorkflowRequest, WorkflowResult
from .pipeline import WorkflowCancelled, classify_asset, run_pipeline
from .render import build_design_spec, write_artifacts
from .runtime import append_log, get_run_snapshot, set_run_state

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


@app.on_event("startup")
def startup() -> None:
    database.init_db()
    database.ensure_seed_data()


@app.get("/api/health")
def health() -> dict[str, object]:
    return {"status": "ok", "database": database.database_health()}


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
    defaults = database.get_workflow_defaults_data()
    stages = database.get_workflow_stages_data()
    if defaults is None or stages is None:
        database.ensure_seed_data()
        defaults = database.get_workflow_defaults_data() or load_workflow_defaults()
        stages = database.get_workflow_stages_data() or database.DEFAULT_WORKFLOW_STAGES
    return {
        "payload": defaults,
        "prompts": defaults["prompts"],
        "workflowModes": ["smart_recommend", "strict_brand"],
        "outputTypes": ["detail_page", "figma_page", "psd_file", "main_image", "banner"],
        "stages": stages,
    }


@app.get("/api/pages/dashboard")
def dashboard_page() -> dict[str, object]:
    data = database.get_dashboard_data()
    if data is None:
        database.ensure_seed_data()
        data = database.get_dashboard_data()
    if data is None:
        raise HTTPException(status_code=404, detail="dashboard data not found")
    return data


@app.get("/api/pages/brand-assets")
def brand_assets_page(
    brand_id: int | None = Query(default=None),
    folder: str | None = Query(default=None),
    status: str | None = Query(default=None),
    search: str | None = Query(default=None),
) -> dict[str, object]:
    data = database.get_brand_assets_page_data(
        brand_id=brand_id,
        folder=folder,
        status=status,
        search=search,
    )
    if data is None:
        database.ensure_seed_data()
        data = database.get_brand_assets_page_data(
            brand_id=brand_id,
            folder=folder,
            status=status,
            search=search,
        )
    if data is None:
        raise HTTPException(status_code=404, detail="brand assets data not found")
    return data


@app.get("/api/pages/brand-rules")
def brand_rules_page(brand_id: int | None = Query(default=None)) -> dict[str, object]:
    data = database.get_brand_rules_page_data(brand_id=brand_id)
    if data is None:
        database.ensure_seed_data()
        data = database.get_brand_rules_page_data(brand_id=brand_id)
    if data is None:
        raise HTTPException(status_code=404, detail="brand rules data not found")
    return data


@app.get("/api/pages/products")
def products_page() -> dict[str, object]:
    data = database.get_products_data()
    if data is None:
        database.ensure_seed_data()
        data = database.get_products_data()
    if data is None:
        raise HTTPException(status_code=404, detail="products data not found")
    return data


@app.get("/api/pages/design-tasks")
def design_tasks_page(
    brand: str | None = Query(default=None),
    status: str | None = Query(default=None),
    task_type: str | None = Query(default=None),
    search: str | None = Query(default=None),
) -> dict[str, object]:
    data = database.get_design_tasks_page_data(
        brand=brand,
        status=status,
        task_type=task_type,
        search=search,
    )
    if data is None:
        database.ensure_seed_data()
        data = database.get_design_tasks_page_data(
            brand=brand,
            status=status,
            task_type=task_type,
            search=search,
        )
    if data is None:
        raise HTTPException(status_code=404, detail="design tasks data not found")
    return data


def _safe_filename(name: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "._-()[] " else "_" for ch in name)
    return cleaned.strip() or "asset"


def _safe_run_id(run_id: str | None) -> str:
    if not run_id:
        return uuid.uuid4().hex
    cleaned = "".join(ch if ch.isalnum() or ch in "-_" else "" for ch in run_id)
    return cleaned[:80] or uuid.uuid4().hex


def _extract_spreadsheet_text(path: Path) -> str | None:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        try:
            return path.read_text(encoding="utf-8")[:16000]
        except UnicodeDecodeError:
            return path.read_text(encoding="gb18030", errors="ignore")[:16000]
        except Exception:
            return None
    if suffix not in {".xlsx", ".xlsm"}:
        return None
    try:
        from openpyxl import load_workbook
    except Exception:
        return None

    try:
        workbook = load_workbook(path, read_only=True, data_only=True)
        lines: list[str] = []
        for sheet in workbook.worksheets[:6]:
            lines.append(f"[Sheet] {sheet.title}")
            count = 0
            for row in sheet.iter_rows(values_only=True):
                values = [str(value).strip() for value in row if value not in (None, "")]
                if values:
                    lines.append(" | ".join(values))
                    count += 1
                if count >= 120:
                    break
        return "\n".join(lines)[:16000]
    except Exception:
        return None


async def _save_assets(
    files: list[UploadFile],
    input_dir: Path,
    bucket_override: str | None = None,
) -> list[UploadedAsset]:
    input_dir.mkdir(parents=True, exist_ok=True)
    assets: list[UploadedAsset] = []
    for file in files:
        filename = _safe_filename(file.filename or "asset")
        target = input_dir / filename
        with target.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        assets.append(
            UploadedAsset(
                name=filename,
                content_type=file.content_type,
                size=target.stat().st_size,
                saved_path=str(target),
                extracted_text=_extract_spreadsheet_text(target),
                bucket=bucket_override or classify_asset(filename, file.content_type),
            )
        )
    return assets


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


@app.post("/api/brand-assets/upload")
async def upload_brand_assets(
    brand_id: int = Form(...),
    name: str = Form(default=""),
    folder: str = Form(...),
    source: str = Form(default=""),
    files: list[UploadFile] = File(default=[]),
) -> dict[str, object]:
    if not files:
        raise HTTPException(status_code=422, detail="请至少上传一个文件")
    media_dir = APP_ROOT / "media" / "brand-assets" / str(brand_id)
    saved_assets = await _save_assets(files, media_dir, bucket_override="brand_asset")
    try:
        created = database.create_brand_assets(
            brand_id=brand_id,
            name=name,
            folder=folder,
            source=source,
            files=[asset.model_dump() for asset in saved_assets],
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"created": created, "count": len(created)}


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
        *await _save_assets(files, input_dir / "assets"),
        *await _save_assets(brief_files, input_dir / "brief", bucket_override="brief"),
        *await _save_assets(
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

    try:
        stages, ctx = run_pipeline(
            request,
            assets,
            run_id=run_id,
            cancel_checker=lambda: run_id in CANCELLED_RUNS,
        )
    except WorkflowCancelled as exc:
        CANCELLED_RUNS.discard(run_id)
        set_run_state(run_id, "cancelled", None)
        raise HTTPException(status_code=499, detail=str(exc)) from exc
    except Exception:
        CANCELLED_RUNS.discard(run_id)
        set_run_state(run_id, "failed", None)
        raise
    CANCELLED_RUNS.discard(run_id)
    spec = build_design_spec(ctx)
    artifact_paths = write_artifacts(output_dir, spec, ctx)

    used_model = any(stage.used_model for stage in stages)
    agent_report = "\n\n".join(ctx.report_parts)
    status = "completed" if used_model else "fallback_completed"
    summary = "BrandOS 设计任务已完成：含品牌规则分层、页面结构、SVG 预览、Figma/PSD 结构说明、评分与反馈清单。"
    try:
        database.persist_run_completed(
            run_id=run_id,
            status=status,
            summary=summary,
            used_deepagents=used_model,
            agent_report=agent_report,
            design_spec=spec,
            artifact_paths=artifact_paths,
            output_dir=str(output_dir),
            warnings=ctx.warnings,
        )
    except Exception as exc:
        append_log(run_id, "Database", f"MySQL 持久化最终结果失败：{exc}")

    return WorkflowResult(
        run_id=run_id,
        status=status,
        summary=summary,
        used_deepagents=used_model,
        stages=stages,
        agent_report=agent_report,
        design_spec=spec,
        artifacts=WorkflowArtifacts(
            run_id=run_id,
            output_dir=str(output_dir),
            **artifact_paths,
        ),
        assets=assets,
        warnings=ctx.warnings,
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
