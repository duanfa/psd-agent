from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..models import RuleVersionUpdateRequest
from ..store import get_store

router = APIRouter(prefix="/api/rule-versions", tags=["rule_versions"])


@router.get("")
def list_rule_versions(brand_id: str | None = None) -> dict[str, object]:
    versions = get_store().list_rule_versions(brand_id=brand_id)
    return {"items": [version.model_dump() for version in versions]}


@router.get("/{version_id}")
def get_rule_version(version_id: str) -> dict[str, object]:
    version = get_store().get_rule_version(version_id)
    if not version:
        raise HTTPException(status_code=404, detail="rule version not found")
    return {"item": version.model_dump()}


@router.patch("/{version_id}")
def update_rule_version(version_id: str, request: RuleVersionUpdateRequest) -> dict[str, object]:
    version = get_store().update_rule_version(version_id, request)
    if not version:
        raise HTTPException(status_code=404, detail="rule version not found")
    return {"item": version.model_dump()}


@router.get("/{version_id}/diff")
def diff_rule_version(version_id: str) -> dict[str, object]:
    store = get_store()
    version = store.get_rule_version(version_id)
    if not version:
        raise HTTPException(status_code=404, detail="rule version not found")
    current = store.get_current_rule_version(version.brand_id)
    diff = store.compute_rule_diff(current.id if current else None, version_id)
    return diff.model_dump()


@router.post("/{version_id}/publish")
def publish_rule_version(version_id: str) -> dict[str, object]:
    version = get_store().publish_rule_version(version_id)
    if not version:
        raise HTTPException(status_code=404, detail="rule version not found")
    return {"item": version.model_dump()}


@router.post("/{version_id}/rollback")
def rollback_rule_version(version_id: str) -> dict[str, object]:
    version = get_store().rollback_rule_version(version_id)
    if not version:
        raise HTTPException(status_code=404, detail="rule version not found")
    return {"item": version.model_dump()}
