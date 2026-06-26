from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ..store import get_store

router = APIRouter(prefix="/api/runs", tags=["runs"])

APP_ROOT = Path(__file__).resolve().parents[2]
RUNS_ROOT = APP_ROOT / "runs"


@router.get("")
def list_runs(brand_id: str | None = None) -> dict[str, object]:
    runs = get_store().list_runs(brand_id=brand_id)
    return {"items": [run.model_dump() for run in runs]}


@router.get("/{run_id}")
def get_run(run_id: str) -> dict[str, object]:
    run = get_store().get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")
    return {"item": run.model_dump()}


@router.get("/{run_id}/logs")
def get_run_logs(run_id: str) -> dict[str, object]:
    run = get_store().get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")
    return {
        "run_id": run.id,
        "status": run.status,
        "current_stage": run.current_stage,
        "logs": run.logs,
        "stages": run.stage_results,
    }


@router.get("/{run_id}/artifacts/{name}")
def download_run_artifact(run_id: str, name: str) -> FileResponse:
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
