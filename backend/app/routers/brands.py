from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..models import BrandCreateRequest, BrandTrainingRequest, BrandUpdateRequest
from ..store import get_store

router = APIRouter(prefix="/api/brands", tags=["brands"])


@router.get("")
def list_brands() -> dict[str, object]:
    store = get_store()
    brands = store.list_brands()
    return {"items": [brand.model_dump() for brand in brands]}


@router.post("")
def create_brand(request: BrandCreateRequest) -> dict[str, object]:
    brand = get_store().create_brand(request)
    return {"item": brand.model_dump()}


@router.get("/{brand_id}")
def get_brand(brand_id: str) -> dict[str, object]:
    store = get_store()
    brand = store.get_brand(brand_id)
    if not brand:
        raise HTTPException(status_code=404, detail="brand not found")
    current_rule_version = (
        store.get_rule_version(brand.current_rule_version_id)
        if brand.current_rule_version_id
        else None
    )
    return {
        "item": brand.model_dump(),
        "current_rule_version": current_rule_version.model_dump() if current_rule_version else None,
    }


@router.patch("/{brand_id}")
def update_brand(brand_id: str, request: BrandUpdateRequest) -> dict[str, object]:
    brand = get_store().update_brand(brand_id, request)
    if not brand:
        raise HTTPException(status_code=404, detail="brand not found")
    return {"item": brand.model_dump()}


@router.post("/{brand_id}/train")
def train_brand_rule_version(brand_id: str, request: BrandTrainingRequest) -> dict[str, object]:
    store = get_store()
    if not store.get_brand(brand_id):
        raise HTTPException(status_code=404, detail="brand not found")
    version = store.create_rule_version_from_assets(brand_id, request)
    return {"item": version.model_dump()}


@router.get("/{brand_id}/audit-events")
def list_brand_audit_events(brand_id: str) -> dict[str, object]:
    store = get_store()
    if not store.get_brand(brand_id):
        raise HTTPException(status_code=404, detail="brand not found")
    events = store.list_audit_events(brand_id=brand_id)
    return {"items": [event.model_dump() for event in events]}
