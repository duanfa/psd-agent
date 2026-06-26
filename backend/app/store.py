from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from .defaults import default_workflow_payload
from .models import (
    AssetTrainingStatus,
    AuditEntityType,
    AuditEventRecord,
    BrandAssetRecord,
    BrandCreateRequest,
    BrandRecord,
    BrandRuleVersionRecord,
    BrandTrainingRequest,
    BrandUpdateRequest,
    RuleVersionDiffResponse,
    RuleVersionStatus,
    RuleVersionUpdateRequest,
    WorkflowRunRecord,
    generate_id,
    utc_now_iso,
)

BACKEND_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = BACKEND_ROOT / "data"


def _slugify(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in value.strip())
    cleaned = "-".join(part for part in cleaned.split("-") if part)
    return cleaned[:40] or "brand"


class JsonStore:
    def __init__(self, root: Path = DATA_ROOT):
        self.root = root
        self.brands_dir = root / "brands"
        self.assets_dir = root / "assets"
        self.rule_versions_dir = root / "rule_versions"
        self.runs_dir = root / "runs"
        self.audit_dir = root / "audit_events"
        self._ensure_dirs()
        self._ensure_seed_brand()

    def _ensure_dirs(self) -> None:
        for path in (
            self.root,
            self.brands_dir,
            self.assets_dir,
            self.rule_versions_dir,
            self.runs_dir,
            self.audit_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)

    def _path_for(self, collection: str, item_id: str) -> Path:
        directory = {
            "brands": self.brands_dir,
            "assets": self.assets_dir,
            "rule_versions": self.rule_versions_dir,
            "runs": self.runs_dir,
            "audit": self.audit_dir,
        }[collection]
        return directory / f"{item_id}.json"

    def _write_json(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _read_json(self, path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))

    def _load_record(self, collection: str, item_id: str, model: type[Any]) -> Any | None:
        path = self._path_for(collection, item_id)
        if not path.is_file():
            return None
        return model.model_validate(self._read_json(path))

    def _save_record(self, collection: str, record: Any) -> Any:
        record.updated_at = utc_now_iso()
        self._write_json(self._path_for(collection, record.id), record.model_dump())
        return record

    def _list_records(self, directory: Path, model: type[Any]) -> list[Any]:
        rows = []
        for path in sorted(directory.glob("*.json")):
            try:
                rows.append(model.model_validate(self._read_json(path)))
            except Exception:
                continue
        rows.sort(key=lambda item: getattr(item, "updated_at", ""), reverse=True)
        return rows

    def _ensure_seed_brand(self) -> None:
        defaults = default_workflow_payload()
        seed_id = "brand_default"
        if self.get_brand(seed_id):
            return

        brand = BrandRecord(
            id=seed_id,
            name=defaults["brand_name"],
            code=_slugify(defaults["brand_name"]),
            description="BrandOS MVP 默认品牌空间",
            members=["local-admin"],
            metadata={"seeded": True},
        )
        self._save_record("brands", brand)

        rule = BrandRuleVersionRecord(
            id="rule_default_v1",
            brand_id=brand.id,
            version_number=1,
            version_label="Brand Rule V1.0",
            status=RuleVersionStatus.published,
            summary="基于默认工作流配置生成的初始规则版本。",
            change_reason="首次初始化 BrandOS 默认品牌空间。",
            brand_profile={
                "core_rule": {
                    "brand_name": defaults["brand_name"],
                    "brand_guidelines": defaults["brand_guidelines"],
                    "primary_color": defaults["layout"]["accent_color"],
                    "background_color": defaults["layout"]["background_color"],
                    "typography": defaults["typography"],
                },
                "derived_rule": {
                    "page_type": "detail_page",
                    "module_count": defaults["layout"]["module_count"],
                    "visual_style": defaults["layout"]["visual_style"],
                    "output_types": defaults["output_types"],
                },
                "asset_memory": {
                    "reference_notes": defaults["reference_notes"],
                    "reference_images": [],
                },
                "prompts": defaults["prompts"],
                "rule_weights": {"core_rule": 0.7, "derived_rule": 0.2, "asset_memory": 0.1},
                "drift_risks": ["默认品牌空间仅用于本地演示，请通过品牌训练生成正式版本。"],
            },
            diff_summary={"initial_version": True},
            drift_risks=["尚未经过真实品牌资产训练。"],
            published_at=utc_now_iso(),
        )
        self._save_record("rule_versions", rule)
        brand.current_rule_version_id = rule.id
        self._save_record("brands", brand)
        self.append_audit_event(
            AuditEventRecord(
                id=generate_id("audit"),
                brand_id=brand.id,
                entity_type=AuditEntityType.brand,
                entity_id=brand.id,
                action="seeded",
                message="已初始化默认品牌与发布版本。",
                payload={"rule_version_id": rule.id},
            )
        )

    def create_brand(self, request: BrandCreateRequest) -> BrandRecord:
        brand = BrandRecord(
            id=generate_id("brand"),
            name=request.name,
            code=request.code or _slugify(request.name),
            description=request.description,
        )
        self._save_record("brands", brand)
        self.append_audit_event(
            AuditEventRecord(
                id=generate_id("audit"),
                brand_id=brand.id,
                entity_type=AuditEntityType.brand,
                entity_id=brand.id,
                action="created",
                message=f"创建品牌：{brand.name}",
            )
        )
        return brand

    def list_brands(self) -> list[BrandRecord]:
        return self._list_records(self.brands_dir, BrandRecord)

    def get_brand(self, brand_id: str) -> BrandRecord | None:
        return self._load_record("brands", brand_id, BrandRecord)

    def update_brand(self, brand_id: str, request: BrandUpdateRequest) -> BrandRecord | None:
        brand = self.get_brand(brand_id)
        if not brand:
            return None
        for key, value in request.model_dump(exclude_none=True).items():
            setattr(brand, key, value)
        self._save_record("brands", brand)
        self.append_audit_event(
            AuditEventRecord(
                id=generate_id("audit"),
                brand_id=brand.id,
                entity_type=AuditEntityType.brand,
                entity_id=brand.id,
                action="updated",
                message=f"更新品牌：{brand.name}",
                payload=request.model_dump(exclude_none=True),
            )
        )
        return brand

    def create_asset(self, asset: BrandAssetRecord) -> BrandAssetRecord:
        self._save_record("assets", asset)
        self.append_audit_event(
            AuditEventRecord(
                id=generate_id("audit"),
                brand_id=asset.brand_id,
                entity_type=AuditEntityType.asset,
                entity_id=asset.id,
                action="created",
                message=f"新增品牌资产：{asset.name}",
                payload={"role": asset.role.value, "training_status": asset.training_status.value},
            )
        )
        return asset

    def get_asset(self, asset_id: str) -> BrandAssetRecord | None:
        return self._load_record("assets", asset_id, BrandAssetRecord)

    def list_assets(self, brand_id: str | None = None) -> list[BrandAssetRecord]:
        assets = self._list_records(self.assets_dir, BrandAssetRecord)
        if brand_id:
            assets = [asset for asset in assets if asset.brand_id == brand_id]
        return assets

    def update_asset(self, asset_id: str, **changes: Any) -> BrandAssetRecord | None:
        asset = self.get_asset(asset_id)
        if not asset:
            return None
        for key, value in changes.items():
            if value is not None:
                setattr(asset, key, value)
        self._save_record("assets", asset)
        self.append_audit_event(
            AuditEventRecord(
                id=generate_id("audit"),
                brand_id=asset.brand_id,
                entity_type=AuditEntityType.asset,
                entity_id=asset.id,
                action="updated",
                message=f"更新品牌资产：{asset.name}",
                payload={key: value for key, value in changes.items() if value is not None},
            )
        )
        return asset

    def list_rule_versions(self, brand_id: str | None = None) -> list[BrandRuleVersionRecord]:
        versions = self._list_records(self.rule_versions_dir, BrandRuleVersionRecord)
        if brand_id:
            versions = [version for version in versions if version.brand_id == brand_id]
        return versions

    def get_rule_version(self, version_id: str) -> BrandRuleVersionRecord | None:
        return self._load_record("rule_versions", version_id, BrandRuleVersionRecord)

    def get_current_rule_version(self, brand_id: str) -> BrandRuleVersionRecord | None:
        brand = self.get_brand(brand_id)
        if not brand or not brand.current_rule_version_id:
            return None
        return self.get_rule_version(brand.current_rule_version_id)

    def create_rule_version(self, version: BrandRuleVersionRecord) -> BrandRuleVersionRecord:
        self._save_record("rule_versions", version)
        self.append_audit_event(
            AuditEventRecord(
                id=generate_id("audit"),
                brand_id=version.brand_id,
                entity_type=AuditEntityType.rule_version,
                entity_id=version.id,
                action="created",
                message=f"创建规则版本：{version.version_label}",
                payload={"status": version.status.value},
            )
        )
        return version

    def next_rule_version_number(self, brand_id: str) -> int:
        versions = self.list_rule_versions(brand_id)
        if not versions:
            return 1
        return max(version.version_number for version in versions) + 1

    def create_rule_version_from_assets(
        self,
        brand_id: str,
        request: BrandTrainingRequest,
    ) -> BrandRuleVersionRecord:
        brand = self.get_brand(brand_id)
        if not brand:
            raise ValueError("brand not found")
        assets = self.list_assets(brand_id)
        selected_assets = [
            asset
            for asset in assets
            if asset.training_status == AssetTrainingStatus.approved_for_training
            and asset.enabled
            and (not request.asset_ids or asset.id in request.asset_ids)
        ]
        previous = self.get_current_rule_version(brand_id)
        version_number = self.next_rule_version_number(brand_id)
        selected_names = [asset.name for asset in selected_assets]
        previous_profile = previous.brand_profile if previous else {}
        brand_profile = {
            "core_rule": {
                **previous_profile.get("core_rule", {}),
                "brand_name": brand.name,
                "selected_asset_count": len(selected_assets),
            },
            "derived_rule": {
                **previous_profile.get("derived_rule", {}),
                "training_asset_names": selected_names,
            },
            "asset_memory": {
                "approved_assets": selected_names,
                "approved_asset_ids": [asset.id for asset in selected_assets],
            },
            "rule_weights": previous_profile.get(
                "rule_weights", {"core_rule": 0.7, "derived_rule": 0.2, "asset_memory": 0.1}
            ),
            "drift_risks": [
                "请人工确认字体、颜色和模块模板差异后再发布。",
                "新资产仅进入候选版本，不会自动覆盖当前已发布规则。",
            ],
        }
        version = BrandRuleVersionRecord(
            id=generate_id("rule"),
            brand_id=brand_id,
            version_number=version_number,
            version_label=f"Brand Rule V{version_number}.0",
            status=RuleVersionStatus.draft,
            summary=request.summary or f"基于 {len(selected_assets)} 个已批准资产生成的候选规则版本。",
            change_reason=request.change_reason or "品牌训练生成候选版本。",
            source_asset_ids=[asset.id for asset in selected_assets],
            brand_profile=brand_profile,
            diff_summary=self.compute_rule_diff(previous.id if previous else None, brand_profile).diff,
            drift_risks=brand_profile["drift_risks"],
        )
        return self.create_rule_version(version)

    def update_rule_version(
        self, version_id: str, request: RuleVersionUpdateRequest
    ) -> BrandRuleVersionRecord | None:
        version = self.get_rule_version(version_id)
        if not version:
            return None
        for key, value in request.model_dump(exclude_none=True).items():
            setattr(version, key, value)
        self._save_record("rule_versions", version)
        self.append_audit_event(
            AuditEventRecord(
                id=generate_id("audit"),
                brand_id=version.brand_id,
                entity_type=AuditEntityType.rule_version,
                entity_id=version.id,
                action="updated",
                message=f"更新规则版本：{version.version_label}",
                payload=request.model_dump(exclude_none=True),
            )
        )
        return version

    def publish_rule_version(self, version_id: str) -> BrandRuleVersionRecord | None:
        version = self.get_rule_version(version_id)
        if not version:
            return None
        versions = self.list_rule_versions(version.brand_id)
        for other in versions:
            if other.status == RuleVersionStatus.published and other.id != version.id:
                other.status = RuleVersionStatus.rolled_back
                other.rolled_back_from_version_id = version.id
                self._save_record("rule_versions", other)
        version.status = RuleVersionStatus.published
        version.published_at = utc_now_iso()
        self._save_record("rule_versions", version)
        brand = self.get_brand(version.brand_id)
        if brand:
            brand.current_rule_version_id = version.id
            self._save_record("brands", brand)
        self.append_audit_event(
            AuditEventRecord(
                id=generate_id("audit"),
                brand_id=version.brand_id,
                entity_type=AuditEntityType.rule_version,
                entity_id=version.id,
                action="published",
                message=f"发布规则版本：{version.version_label}",
            )
        )
        return version

    def rollback_rule_version(self, version_id: str) -> BrandRuleVersionRecord | None:
        version = self.get_rule_version(version_id)
        if not version:
            return None
        version.status = RuleVersionStatus.rolled_back
        self._save_record("rule_versions", version)
        brand = self.get_brand(version.brand_id)
        if brand and brand.current_rule_version_id == version.id:
            brand.current_rule_version_id = None
            self._save_record("brands", brand)
        self.append_audit_event(
            AuditEventRecord(
                id=generate_id("audit"),
                brand_id=version.brand_id,
                entity_type=AuditEntityType.rule_version,
                entity_id=version.id,
                action="rolled_back",
                message=f"回滚规则版本：{version.version_label}",
            )
        )
        return version

    def compute_rule_diff(
        self, current_version_id: str | None, target: str | dict[str, Any]
    ) -> RuleVersionDiffResponse:
        current = self.get_rule_version(current_version_id) if current_version_id else None
        if isinstance(target, str):
            target_version = self.get_rule_version(target)
            if not target_version:
                raise ValueError("target version not found")
            target_profile = target_version.brand_profile
            target_version_id = target_version.id
        else:
            target_profile = target
            target_version_id = "draft_preview"
        current_profile = current.brand_profile if current else {}
        diff = {
            "core_rule": {
                "before": current_profile.get("core_rule", {}),
                "after": target_profile.get("core_rule", {}),
            },
            "derived_rule": {
                "before": current_profile.get("derived_rule", {}),
                "after": target_profile.get("derived_rule", {}),
            },
            "asset_memory": {
                "before": current_profile.get("asset_memory", {}),
                "after": target_profile.get("asset_memory", {}),
            },
            "rule_weights": {
                "before": current_profile.get("rule_weights", {}),
                "after": target_profile.get("rule_weights", {}),
            },
            "drift_risks": {
                "before": current_profile.get("drift_risks", []),
                "after": target_profile.get("drift_risks", []),
            },
        }
        return RuleVersionDiffResponse(
            current_version_id=current.id if current else None,
            target_version_id=target_version_id,
            diff=diff,
        )

    def create_run(self, record: WorkflowRunRecord) -> WorkflowRunRecord:
        return self._save_record("runs", record)

    def get_run(self, run_id: str) -> WorkflowRunRecord | None:
        return self._load_record("runs", run_id, WorkflowRunRecord)

    def list_runs(self, brand_id: str | None = None) -> list[WorkflowRunRecord]:
        runs = self._list_records(self.runs_dir, WorkflowRunRecord)
        if brand_id:
            runs = [run for run in runs if run.brand_id == brand_id]
        return runs

    def update_run(self, run_id: str, **changes: Any) -> WorkflowRunRecord | None:
        run = self.get_run(run_id)
        if not run:
            return None
        for key, value in changes.items():
            if value is not None:
                setattr(run, key, value)
        return self._save_record("runs", run)

    def append_run_log(self, run_id: str, line: str) -> None:
        run = self.get_run(run_id)
        if not run:
            return
        run.logs.append(line)
        run.logs = run.logs[-1200:]
        self._save_record("runs", run)

    def set_run_state(
        self,
        run_id: str,
        *,
        status: str,
        current_stage: str | None,
        current_stage_title: str | None,
        current_stage_icon: str | None,
    ) -> None:
        run = self.get_run(run_id)
        if not run:
            return
        run.status = status
        run.current_stage = current_stage
        run.current_stage_title = current_stage_title
        run.current_stage_icon = current_stage_icon
        self._save_record("runs", run)

    def append_run_stage_result(self, run_id: str, stage_data: dict[str, Any]) -> None:
        run = self.get_run(run_id)
        if not run:
            return
        run.stage_results = [
            existing for existing in run.stage_results if existing.get("id") != stage_data.get("id")
        ]
        run.stage_results.append(stage_data)
        self._save_record("runs", run)

    def append_audit_event(self, event: AuditEventRecord) -> AuditEventRecord:
        self._save_record("audit", event)
        return event

    def list_audit_events(
        self,
        brand_id: str | None = None,
        entity_type: AuditEntityType | None = None,
    ) -> list[AuditEventRecord]:
        events = self._list_records(self.audit_dir, AuditEventRecord)
        if brand_id:
            events = [event for event in events if event.brand_id == brand_id]
        if entity_type:
            events = [event for event in events if event.entity_type == entity_type]
        return events


_STORE: JsonStore | None = None


def get_store() -> JsonStore:
    global _STORE
    if _STORE is None:
        _STORE = JsonStore()
    return _STORE


def summarize_assets_for_training(assets: Iterable[BrandAssetRecord]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for asset in assets:
        grouped.setdefault(asset.role.value, []).append(asset.name)
    return grouped
