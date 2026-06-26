from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from ..file_utils import safe_filename
from ..models import (
    AssetRole,
    AssetTrainingStatus,
    AssetUpdateRequest,
    BrandAssetRecord,
    generate_id,
)
from ..pipeline import classify_asset
from ..store import get_store

router = APIRouter(prefix="/api/assets", tags=["assets"])

APP_ROOT = Path(__file__).resolve().parents[2]
BRAND_ASSET_ROOT = APP_ROOT / "data" / "asset_files"


@router.get("")
def list_assets(brand_id: str | None = None) -> dict[str, object]:
    assets = get_store().list_assets(brand_id=brand_id)
    return {"items": [asset.model_dump() for asset in assets]}


@router.post("")
async def upload_asset(
    brand_id: str = Form(...),
    role: AssetRole = Form(default=AssetRole.reference),
    training_status: AssetTrainingStatus = Form(default=AssetTrainingStatus.candidate),
    notes: str = Form(default=""),
    tags: str = Form(default=""),
    file: UploadFile = File(...),
) -> dict[str, object]:
    store = get_store()
    if not store.get_brand(brand_id):
        raise HTTPException(status_code=404, detail="brand not found")
    asset_id = generate_id("asset")
    filename = safe_filename(file.filename or asset_id)
    target_dir = BRAND_ASSET_ROOT / brand_id
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / filename
    content = await file.read()
    target_path.write_bytes(content)
    asset = BrandAssetRecord(
        id=asset_id,
        brand_id=brand_id,
        name=filename,
        content_type=file.content_type,
        size=len(content),
        bucket=classify_asset(filename, file.content_type),
        role=role,
        training_status=training_status,
        path=str(target_path),
        notes=notes,
        tags=[item.strip() for item in tags.split(",") if item.strip()],
    )
    store.create_asset(asset)
    return {"item": asset.model_dump()}


@router.patch("/{asset_id}")
def update_asset(asset_id: str, request: AssetUpdateRequest) -> dict[str, object]:
    asset = get_store().update_asset(asset_id, **request.model_dump(exclude_none=True))
    if not asset:
        raise HTTPException(status_code=404, detail="asset not found")
    return {"item": asset.model_dump()}
