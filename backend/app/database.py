from __future__ import annotations

import json
import os
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    and_,
    create_engine,
    func,
    or_,
    select,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from .defaults import load_workflow_defaults

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
except Exception:
    pass


def _database_url() -> str | None:
    raw = os.getenv("DATABASE_URL")
    if not raw:
        return None

    parsed = urlsplit(raw)
    scheme = "mysql+pymysql" if parsed.scheme == "mysql" else parsed.scheme
    query = urlencode(
        [(key, value) for key, value in parse_qsl(parsed.query) if key != "schema"]
    )
    return urlunsplit((scheme, parsed.netloc, parsed.path, query, parsed.fragment))


DATABASE_URL = _database_url()
engine = (
    create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=3600, future=True)
    if DATABASE_URL
    else None
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True) if engine else None


class Base(DeclarativeBase):
    pass


class Brand(Base):
    __tablename__ = "brands"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(64), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value_json: Mapped[dict[str, Any] | list[Any] | str | None] = mapped_column(JSON, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class BrandAsset(Base):
    __tablename__ = "brand_assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    brand_id: Mapped[int | None] = mapped_column(ForeignKey("brands.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    folder: Mapped[str] = mapped_column(String(64), index=True)
    content_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    size: Mapped[int] = mapped_column(BigInteger, default=0)
    saved_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    source: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(64), default="uploaded")
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class BrandTrainingTask(Base):
    __tablename__ = "brand_training_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    brand_id: Mapped[int | None] = mapped_column(ForeignKey("brands.id"), nullable=True, index=True)
    task_code: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(64), index=True)
    summary: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class BrandRule(Base):
    __tablename__ = "brand_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    brand_id: Mapped[int | None] = mapped_column(ForeignKey("brands.id"), nullable=True, index=True)
    version: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(64), default="draft")
    rule_count: Mapped[int] = mapped_column(Integer, default=0)
    layout_count: Mapped[int] = mapped_column(Integer, default=0)
    prompt_count: Mapped[int] = mapped_column(Integer, default=0)
    design_rules: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    layout_rules: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    components: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    prompt_templates: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    brand_id: Mapped[int | None] = mapped_column(ForeignKey("brands.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    category: Mapped[str] = mapped_column(String(100), default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    brief: Mapped[str] = mapped_column(Text, default="")
    design_direction: Mapped[str] = mapped_column(Text, default="")
    selling_points: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    materials: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    selling_point_count: Mapped[int] = mapped_column(Integer, default=0)
    asset_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"

    run_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    status: Mapped[str] = mapped_column(String(64), index=True)
    current_stage: Mapped[str | None] = mapped_column(String(100), nullable=True)
    current_stage_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    current_stage_icon: Mapped[str | None] = mapped_column(String(64), nullable=True)
    task_code: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    task_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    project_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    brand_name: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    product_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    workflow_mode: Mapped[str | None] = mapped_column(String(64), nullable=True)
    request_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    used_deepagents: Mapped[bool] = mapped_column(Boolean, default=False)
    agent_report: Mapped[str | None] = mapped_column(Text, nullable=True)
    design_spec: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    warnings: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class WorkflowAsset(Base):
    __tablename__ = "workflow_assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("workflow_runs.run_id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    size: Mapped[int] = mapped_column(BigInteger, default=0)
    saved_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    bucket: Mapped[str] = mapped_column(String(64), index=True)
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class WorkflowStage(Base):
    __tablename__ = "workflow_stages"
    __table_args__ = (UniqueConstraint("run_id", "stage_id", name="uq_workflow_stage_run_stage"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("workflow_runs.run_id"), index=True)
    stage_id: Mapped[str] = mapped_column(String(100), index=True)
    title: Mapped[str] = mapped_column(String(255))
    icon: Mapped[str] = mapped_column(String(64), default="sparkles")
    status: Mapped[str] = mapped_column(String(64), index=True)
    summary: Mapped[str] = mapped_column(Text, default="")
    detail: Mapped[str] = mapped_column(Text, default="")
    data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    used_model: Mapped[bool] = mapped_column(Boolean, default=False)
    elapsed_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class WorkflowLog(Base):
    __tablename__ = "workflow_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("workflow_runs.run_id"), index=True)
    scope: Mapped[str] = mapped_column(String(100))
    title: Mapped[str] = mapped_column(Text)
    message: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict[str, Any] | list[Any] | str | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class WorkflowArtifact(Base):
    __tablename__ = "workflow_artifacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("workflow_runs.run_id"), index=True)
    output_dir: Mapped[str] = mapped_column(String(1024))
    preview_svg: Mapped[str] = mapped_column(String(1024))
    design_spec_path: Mapped[str] = mapped_column(String(1024))
    photoshop_jsx: Mapped[str] = mapped_column(String(1024))
    readme: Mapped[str] = mapped_column(String(1024))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


def enabled() -> bool:
    return engine is not None


def init_db() -> None:
    if engine is not None:
        Base.metadata.create_all(bind=engine)


@contextmanager
def session_scope():
    if SessionLocal is None:
        yield None
        return

    session: Session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return _jsonable(value.model_dump(mode="json"))
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    return value


def persist_run_started(run_id: str, request: Any, assets: list[Any]) -> None:
    with session_scope() as session:
        if session is None:
            return

        payload = _jsonable(request)
        run = session.get(WorkflowRun, run_id) or WorkflowRun(run_id=run_id, status="running")
        run.status = "running"
        run.current_stage = None
        run.task_code = run.task_code or run_id
        run.task_type = run.task_type or "商品详情页"
        run.project_name = payload.get("project_name")
        run.brand_name = payload.get("brand_name")
        run.product_name = payload.get("product_name")
        run.workflow_mode = payload.get("workflow_mode")
        run.request_payload = payload
        run.updated_at = datetime.utcnow()
        session.merge(run)

        session.query(WorkflowAsset).filter(WorkflowAsset.run_id == run_id).delete()
        for asset in assets:
            data = _jsonable(asset)
            session.add(
                WorkflowAsset(
                    run_id=run_id,
                    name=data["name"],
                    content_type=data.get("content_type"),
                    size=data.get("size") or 0,
                    saved_path=data.get("saved_path"),
                    bucket=data.get("bucket") or "reference",
                    extracted_text=data.get("extracted_text"),
                )
            )


def persist_run_state(
    run_id: str,
    status: str,
    current_stage: str | None = None,
    current_stage_title: str | None = None,
    current_stage_icon: str | None = None,
) -> None:
    with session_scope() as session:
        if session is None:
            return
        run = session.get(WorkflowRun, run_id) or WorkflowRun(run_id=run_id, status=status)
        run.status = status
        run.current_stage = current_stage
        run.current_stage_title = current_stage_title
        run.current_stage_icon = current_stage_icon
        run.updated_at = datetime.utcnow()
        if status in {"completed", "failed", "cancelled"}:
            run.completed_at = datetime.utcnow()
        session.merge(run)


def persist_log(run_id: str, scope: str, title: str, message: str, payload: Any | None) -> None:
    with session_scope() as session:
        if session is None:
            return
        if session.get(WorkflowRun, run_id) is None:
            session.add(WorkflowRun(run_id=run_id, status="running"))
        session.add(
            WorkflowLog(
                run_id=run_id,
                scope=scope,
                title=title,
                message=message,
                payload=_jsonable(payload),
            )
        )


def persist_stage(run_id: str, stage: Any) -> None:
    data = _jsonable(stage)
    with session_scope() as session:
        if session is None:
            return
        current = session.execute(
            select(WorkflowStage).where(
                WorkflowStage.run_id == run_id,
                WorkflowStage.stage_id == data["id"],
            )
        ).scalar_one_or_none()
        stage_row = current or WorkflowStage(run_id=run_id, stage_id=data["id"], title=data["title"])
        stage_row.title = data["title"]
        stage_row.icon = data.get("icon") or "sparkles"
        stage_row.status = data["status"]
        stage_row.summary = data.get("summary") or ""
        stage_row.detail = data.get("detail") or ""
        stage_row.data = data.get("data") or {}
        stage_row.used_model = bool(data.get("used_model"))
        stage_row.elapsed_ms = int(data.get("elapsed_ms") or 0)
        stage_row.updated_at = datetime.utcnow()
        session.merge(stage_row)


def persist_run_completed(
    run_id: str,
    status: str,
    summary: str,
    used_deepagents: bool,
    agent_report: str,
    design_spec: dict[str, Any],
    artifact_paths: dict[str, str],
    output_dir: str,
    warnings: list[str],
) -> None:
    with session_scope() as session:
        if session is None:
            return
        run = session.get(WorkflowRun, run_id) or WorkflowRun(run_id=run_id, status=status)
        run.status = status
        run.current_stage = None
        run.summary = summary
        run.used_deepagents = used_deepagents
        run.agent_report = agent_report
        run.design_spec = _jsonable(design_spec)
        run.warnings = warnings
        run.completed_at = datetime.utcnow()
        run.updated_at = datetime.utcnow()
        session.merge(run)
        session.add(
            WorkflowArtifact(
                run_id=run_id,
                output_dir=output_dir,
                preview_svg=artifact_paths["preview_svg"],
                design_spec_path=artifact_paths["design_spec"],
                photoshop_jsx=artifact_paths["photoshop_jsx"],
                readme=artifact_paths["readme"],
            )
        )


def load_run_snapshot(run_id: str) -> dict[str, Any] | None:
    with session_scope() as session:
        if session is None:
            return None
        run = session.get(WorkflowRun, run_id)
        if run is None:
            return None
        stages = [
            {
                "id": stage.stage_id,
                "title": stage.title,
                "icon": stage.icon,
                "status": stage.status,
                "summary": stage.summary,
                "detail": stage.detail,
                "data": stage.data or {},
                "used_model": stage.used_model,
                "elapsed_ms": stage.elapsed_ms,
            }
            for stage in session.execute(
                select(WorkflowStage)
                .where(WorkflowStage.run_id == run_id)
                .order_by(WorkflowStage.id.asc())
            ).scalars()
        ]
        logs = [
            log.message
            for log in session.execute(
                select(WorkflowLog)
                .where(WorkflowLog.run_id == run_id)
                .order_by(WorkflowLog.id.asc())
            ).scalars()
        ]
        return {
            "run_id": run_id,
            "status": run.status,
            "current_stage": run.current_stage,
            "logs": logs,
            "stages": stages,
        }


def database_health() -> dict[str, Any]:
    if engine is None:
        return {"enabled": False}
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("SELECT 1")
        return {"enabled": True, "status": "ok"}
    except Exception as exc:
        return {"enabled": True, "status": "error", "error": str(exc)}


def _setting(session: Session, key: str, default: Any = None) -> Any:
    row = session.get(AppSetting, key)
    return default if row is None else row.value_json


def get_workflow_defaults_data() -> dict[str, Any] | None:
    with session_scope() as session:
        if session is None:
            return None
        value = _setting(session, "workflow_defaults")
        return value if isinstance(value, dict) else None


def get_workflow_stages_data() -> list[dict[str, Any]] | None:
    with session_scope() as session:
        if session is None:
            return None
        value = _setting(session, "workflow_stages")
        return value if isinstance(value, list) else None


def get_dashboard_data() -> dict[str, Any] | None:
    with session_scope() as session:
        if session is None:
            return None
        page = _setting(session, "dashboard_page", {})
        current_brand_name = (page or {}).get("currentBrandName")
        current_brand = None
        if current_brand_name:
            current_brand = session.execute(
                select(Brand).where(Brand.name == current_brand_name)
            ).scalar_one_or_none()
        if current_brand is None:
            current_brand = session.execute(select(Brand).order_by(Brand.id.asc())).scalar_one_or_none()
        if current_brand is None:
            return None

        asset_count = session.execute(
            select(func.count(BrandAsset.id)).where(BrandAsset.brand_id == current_brand.id)
        ).scalar_one()
        rule_count = session.execute(
            select(func.count(BrandRule.id)).where(BrandRule.brand_id == current_brand.id)
        ).scalar_one()
        training_completed = session.execute(
            select(func.count(BrandTrainingTask.id)).where(
                BrandTrainingTask.brand_id == current_brand.id,
                BrandTrainingTask.status == "生成成功",
            )
        ).scalar_one()
        pending_design = session.execute(
            select(func.count(WorkflowRun.run_id)).where(
                WorkflowRun.brand_name == current_brand.name,
                WorkflowRun.status.in_(["running", "fallback_completed", "completed"]),
            )
        ).scalar_one()

        training_tasks = [
            {
                "title": item.title,
                "status": item.status,
                "summary": item.summary,
            }
            for item in session.execute(
                select(BrandTrainingTask)
                .where(BrandTrainingTask.brand_id == current_brand.id)
                .order_by(BrandTrainingTask.created_at.desc())
                .limit(3)
            ).scalars()
        ]
        design_tasks = [
            {
                "title": item.product_name or item.task_code or item.run_id,
                "status": item.status,
                "summary": item.summary or "等待查看任务详情。",
            }
            for item in session.execute(
                select(WorkflowRun)
                .where(WorkflowRun.brand_name == current_brand.name)
                .order_by(WorkflowRun.created_at.desc())
                .limit(3)
            ).scalars()
        ]

        return {
            "page": page,
            "hero": {
                "brandName": current_brand.name,
                "status": current_brand.status,
                "description": (page or {}).get("heroDescription", ""),
                "tags": (page or {}).get("heroTags", []),
                "weeklyCompletionRate": (page or {}).get("weeklyCompletionRate", 0),
                "weeklyStatus": (page or {}).get("weeklyStatus", "状态稳定"),
                "weeklySummary": (page or {}).get("weeklySummary", ""),
            },
            "stats": [
                {"label": "品牌概览", "value": asset_count, "description": "累计品牌资产"},
                {"label": "资产统计", "value": rule_count, "description": "规则版本"},
                {"label": "最近训练任务", "value": training_completed, "description": "本周已完成训练"},
                {"label": "最近设计任务", "value": pending_design, "description": "待处理任务数"},
            ],
            "trainingTasks": training_tasks,
            "designTasks": design_tasks,
            "quickActions": (page or {}).get("quickActions", []),
        }


def get_brand_assets_data() -> dict[str, Any] | None:
    return get_brand_assets_page_data()


def get_brand_assets_page_data(
    brand_id: int | None = None,
    folder: str | None = None,
    status: str | None = None,
    search: str | None = None,
) -> dict[str, Any] | None:
    with session_scope() as session:
        if session is None:
            return None
        page = _setting(session, "brand_assets_page", {})
        brands = list(session.execute(select(Brand).order_by(Brand.id.asc())).scalars())
        if not brands:
            return None
        selected_brand = next((brand for brand in brands if brand.id == brand_id), brands[0])
        filters = [BrandAsset.brand_id == selected_brand.id]
        if folder:
            filters.append(BrandAsset.folder == folder)
        if status:
            filters.append(BrandAsset.status == status)
        if search:
            keyword = f"%{search.strip()}%"
            filters.append(or_(BrandAsset.name.like(keyword), BrandAsset.source.like(keyword)))
        assets = list(
            session.execute(
                select(BrandAsset)
                .where(and_(*filters))
                .order_by(BrandAsset.created_at.desc(), BrandAsset.id.desc())
            ).scalars()
        )
        folder_defs = (page or {}).get("folders", [])
        folder_counts = {
            folder_item["name"]: session.execute(
                select(func.count(BrandAsset.id)).where(
                    BrandAsset.brand_id == selected_brand.id,
                    BrandAsset.folder == folder_item["name"],
                )
            ).scalar_one()
            for folder_item in folder_defs
        }
        statuses = sorted(
            {
                item
                for item in session.execute(
                    select(BrandAsset.status).where(BrandAsset.brand_id == selected_brand.id)
                ).scalars()
                if item
            }
        )
        return {
            "page": page,
            "filters": {
                "brandId": selected_brand.id,
                "folder": folder or "",
                "status": status or "",
                "search": search or "",
            },
            "statuses": statuses,
            "brands": [
                {
                    "id": brand.id,
                    "name": brand.name,
                    "status": brand.status,
                    "assets": session.execute(
                        select(func.count(BrandAsset.id)).where(BrandAsset.brand_id == brand.id)
                    ).scalar_one(),
                }
                for brand in brands
            ],
            "selectedBrand": {"id": selected_brand.id, "name": selected_brand.name},
            "folders": [
                {**folder_item, "count": folder_counts.get(folder_item["name"], 0)}
                for folder_item in folder_defs
            ],
            "assets": [
                {
                    "id": asset.id,
                    "name": asset.name,
                    "folder": asset.folder,
                    "type": asset.content_type or "未知",
                    "source": asset.source or "未知来源",
                    "status": asset.status,
                    "size": asset.size,
                    "createdAt": asset.created_at.isoformat() if asset.created_at else None,
                }
                for asset in assets[:30]
            ],
            "uploadForm": (page or {}).get("uploadForm", {}),
        }


def create_brand_assets(
    brand_id: int,
    name: str,
    folder: str,
    source: str,
    files: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    with session_scope() as session:
        if session is None:
            return []
        brand = session.get(Brand, brand_id)
        if brand is None:
            raise ValueError("brand not found")
        created: list[dict[str, Any]] = []
        base_name = (name or "").strip()
        for index, file_item in enumerate(files, start=1):
            asset_name = base_name or file_item["name"]
            if len(files) > 1 and base_name:
                asset_name = f"{base_name} #{index}"
            row = BrandAsset(
                brand_id=brand_id,
                name=asset_name,
                folder=folder,
                content_type=file_item.get("content_type"),
                size=file_item.get("size") or 0,
                saved_path=file_item.get("saved_path"),
                source=source or None,
                status="待校验",
                extracted_text=file_item.get("extracted_text"),
                metadata_json={
                    "original_name": file_item.get("name"),
                    "bucket": file_item.get("bucket"),
                },
            )
            session.add(row)
            session.flush()
            created.append(
                {
                    "id": row.id,
                    "name": row.name,
                    "folder": row.folder,
                    "source": row.source,
                    "status": row.status,
                }
            )
        return created


def get_brand_rules_data() -> dict[str, Any] | None:
    return get_brand_rules_page_data()


def get_brand_rules_page_data(brand_id: int | None = None) -> dict[str, Any] | None:
    with session_scope() as session:
        if session is None:
            return None
        page = _setting(session, "brand_rules_page", {})
        brands = list(session.execute(select(Brand).order_by(Brand.id.asc())).scalars())
        if not brands:
            return None
        selected_brand = next((brand for brand in brands if brand.id == brand_id), brands[0])
        rule = session.execute(
            select(BrandRule)
            .where(BrandRule.brand_id == selected_brand.id)
            .order_by(BrandRule.updated_at.desc(), BrandRule.id.desc())
        ).scalar_one_or_none()
        brand_rows = []
        for brand in brands:
            latest_rule = session.execute(
                select(BrandRule)
                .where(BrandRule.brand_id == brand.id)
                .order_by(BrandRule.updated_at.desc(), BrandRule.id.desc())
            ).scalar_one_or_none()
            brand_rows.append(
                {
                    "id": brand.id,
                    "name": brand.name,
                    "status": brand.status,
                    "version": latest_rule.version if latest_rule else "未训练",
                    "ruleCount": latest_rule.rule_count if latest_rule else 0,
                }
            )
        if rule is None:
            return {
                "page": page,
                "brands": brand_rows,
                "selectedBrand": {"id": selected_brand.id, "name": selected_brand.name},
                "overview": [
                    {"label": "规则版本", "value": "未训练", "description": "当前生效版本"},
                    {"label": "设计规则说明", "value": 0, "description": "条结构化规则"},
                    {"label": "布局规则摘要", "value": 0, "description": "模块模板"},
                    {"label": "Prompt 模板摘要", "value": 0, "description": "场景模板"},
                ],
                "designRules": [],
                "layoutRules": [],
                "components": [],
                "promptTemplates": [],
                "emptyState": f"{selected_brand.name} 还没有品牌规则，请先上传品牌资产并发起训练。",
            }
        return {
            "page": page,
            "brands": brand_rows,
            "selectedBrand": {"id": selected_brand.id, "name": selected_brand.name},
            "overview": [
                {"label": "规则版本", "value": rule.version, "description": "当前生效版本"},
                {"label": "设计规则说明", "value": rule.rule_count, "description": "条结构化规则"},
                {"label": "布局规则摘要", "value": rule.layout_count, "description": "模块模板"},
                {"label": "Prompt 模板摘要", "value": rule.prompt_count, "description": "场景模板"},
            ],
            "designRules": rule.design_rules or [],
            "layoutRules": rule.layout_rules or [],
            "components": rule.components or [],
            "promptTemplates": rule.prompt_templates or [],
            "emptyState": "",
        }


def get_products_data() -> dict[str, Any] | None:
    with session_scope() as session:
        if session is None:
            return None
        page = _setting(session, "products_page", {})
        products = list(session.execute(select(Product).order_by(Product.updated_at.desc())).scalars())
        if not products:
            return None
        selected = products[0]
        return {
            "page": page,
            "products": [
                {
                    "id": product.id,
                    "name": product.name,
                    "category": product.category,
                    "sellingPointCount": product.selling_point_count,
                    "assetCount": product.asset_count,
                    "updatedAt": product.updated_at.isoformat(),
                }
                for product in products
            ],
            "selectedProduct": {
                "id": selected.id,
                "name": selected.name,
                "category": selected.category,
                "summary": selected.summary,
                "brief": selected.brief,
                "designDirection": selected.design_direction,
                "sellingPoints": selected.selling_points or [],
                "materials": selected.materials or [],
            },
        }


def get_design_tasks_data() -> dict[str, Any] | None:
    return get_design_tasks_page_data()


def get_design_tasks_page_data(
    brand: str | None = None,
    status: str | None = None,
    task_type: str | None = None,
    search: str | None = None,
) -> dict[str, Any] | None:
    with session_scope() as session:
        if session is None:
            return None
        page = _setting(session, "design_tasks_page", {})
        base_tasks = list(session.execute(select(WorkflowRun).order_by(WorkflowRun.created_at.desc())).scalars())
        if not base_tasks:
            return {
                "page": page,
                "metrics": {"total": 0, "running": 0, "success": 0, "failed": 0},
                "brands": [],
                "taskTypes": [],
                "statuses": [],
                "filters": {"brand": "", "status": "", "taskType": "", "search": ""},
                "tasks": [],
            }
        filtered = base_tasks
        if brand:
            filtered = [item for item in filtered if item.brand_name == brand]
        if status:
            filtered = [item for item in filtered if item.status == status]
        if task_type:
            filtered = [item for item in filtered if (item.task_type or "商品详情页") == task_type]
        if search:
            keyword = search.strip().lower()
            filtered = [
                item
                for item in filtered
                if keyword in (item.task_code or item.run_id or "").lower()
                or keyword in (item.brand_name or "").lower()
                or keyword in (item.product_name or "").lower()
            ]
        running_statuses = {"running", "cancelling"}
        success_statuses = {"completed", "fallback_completed", "生成成功", "待审核"}
        failed_statuses = {"failed", "cancelled", "生成失败"}
        brands = sorted({item.brand_name for item in base_tasks if item.brand_name})
        task_types = sorted({item.task_type or "商品详情页" for item in base_tasks})
        statuses = sorted({item.status for item in base_tasks if item.status})
        return {
            "page": page,
            "brands": brands,
            "taskTypes": task_types,
            "statuses": statuses,
            "filters": {
                "brand": brand or "",
                "status": status or "",
                "taskType": task_type or "",
                "search": search or "",
            },
            "metrics": {
                "total": len(filtered),
                "running": sum(1 for item in filtered if item.status in running_statuses),
                "success": sum(1 for item in filtered if item.status in success_statuses),
                "failed": sum(1 for item in filtered if item.status in failed_statuses),
            },
            "tasks": [
                {
                    "taskId": item.task_code or item.run_id,
                    "brand": item.brand_name or "",
                    "product": item.product_name or "",
                    "taskType": item.task_type or "商品详情页",
                    "status": item.status,
                    "createdAt": item.created_at.isoformat() if item.created_at else None,
                    "completedAt": item.completed_at.isoformat() if item.completed_at else None,
                }
                for item in filtered
            ],
        }


DEFAULT_WORKFLOW_STAGES: list[dict[str, Any]] = [
    {"id": "product_understanding", "title": "商品理解 Agent", "icon": "eye"},
    {"id": "product_brief", "title": "Product Brief", "icon": "layers"},
    {"id": "brand_knowledge", "title": "品牌知识库 / 规则版本", "icon": "library"},
    {"id": "page_planner", "title": "页面规划 Agent", "icon": "palette"},
    {"id": "layout_engine", "title": "Layout Engine", "icon": "grid"},
    {"id": "copy", "title": "文案 Agent", "icon": "type"},
    {"id": "figma_psd", "title": "Figma / PSD 生成 Agent", "icon": "file-image"},
    {"id": "design_score", "title": "Design Score", "icon": "check-circle"},
    {"id": "output_review", "title": "输出、审核与反馈", "icon": "check-circle"},
]


def _set_setting(session: Session, key: str, value: Any) -> None:
    row = session.get(AppSetting, key) or AppSetting(key=key)
    row.value_json = _jsonable(value)
    row.updated_at = datetime.utcnow()
    session.merge(row)


def ensure_seed_data() -> None:
    with session_scope() as session:
        if session is None:
            return

        if session.execute(select(func.count(AppSetting.key))).scalar_one() == 0:
            _set_setting(session, "workflow_stages", DEFAULT_WORKFLOW_STAGES)
            _set_setting(session, "workflow_defaults", load_workflow_defaults())
            _set_setting(
                session,
                "dashboard_page",
                {
                    "title": "工作台",
                    "subtitle": "查看当前品牌的训练进度、设计任务和常用操作入口",
                    "currentBrandName": "AURORA 家居旗舰店",
                    "heroDescription": "当前品牌最近一次训练完成于 2 小时前，已沉淀 4 个规则版本，可直接用于商品详情页生成。",
                    "heroTags": ["规则版本：V1.4", "最近训练成功率：96%"],
                    "weeklyCompletionRate": 87,
                    "weeklyStatus": "状态稳定",
                    "weeklySummary": "过去 7 天共完成 26 个设计任务，其中 18 个已进入结果审核阶段。",
                    "quickActions": [
                        {
                            "title": "上传品牌资产",
                            "description": "导入官网、PSD、品牌规范和历史案例，用于品牌训练。",
                            "href": "/brand-assets",
                        },
                        {
                            "title": "新建商品",
                            "description": "录入商品参数、卖点、素材与 Brief，作为任务输入。",
                            "href": "/products",
                        },
                        {
                            "title": "发起设计任务",
                            "description": "选择品牌与商品，配置风格偏向和输出格式后提交。",
                            "href": "/create-task",
                        },
                        {
                            "title": "查看设计任务",
                            "description": "在设计任务列表中查看执行进度、结果和失败原因。",
                            "href": "/design-tasks",
                        },
                    ],
                },
            )
            _set_setting(
                session,
                "brand_assets_page",
                {
                    "title": "品牌资产",
                    "subtitle": "按品牌统一管理设计规范、样例图、官网素材和详情页资产。",
                    "folders": [
                        {
                            "name": "品牌设计规范",
                            "description": "品牌手册、字体、色彩、版式和禁用规则",
                            "icon": "FileText",
                        },
                        {
                            "name": "样例图",
                            "description": "可训练的历史案例、风格参考和人工精选图",
                            "icon": "FileImage",
                        },
                        {
                            "name": "官网素材",
                            "description": "官网截图、活动页、品牌故事和页面源素材",
                            "icon": "Globe2",
                        },
                        {
                            "name": "详情页",
                            "description": "商品详情页源文件、导出图和历史投放版本",
                            "icon": "Folder",
                        },
                    ],
                    "uploadForm": {
                        "name": "2026 夏季新品详情页源文件",
                        "folder": "详情页",
                        "source": "设计团队交付",
                    },
                },
            )
            _set_setting(
                session,
                "brand_rules_page",
                {"title": "品牌规则", "subtitle": "查看 AI 提取出的品牌风格、结构和组件规则"},
            )
            _set_setting(
                session,
                "products_page",
                {"title": "商品管理", "subtitle": "维护商品基础信息、卖点和设计素材，作为生成任务的输入"},
            )
            _set_setting(
                session,
                "design_tasks_page",
                {"title": "设计任务", "subtitle": "查看所有设计任务的状态、进度和结果入口"},
            )

        if session.execute(select(func.count(Brand.id))).scalar_one() == 0:
            session.add_all(
                [
                    Brand(name="AURORA 家居旗舰店", status="已初始化"),
                    Brand(name="Nordic Living 官方店", status="待补充"),
                    Brand(name="Mellow Sleep", status="已初始化"),
                ]
            )
            session.flush()

        brands = {
            item.name: item
            for item in session.execute(select(Brand).order_by(Brand.id.asc())).scalars()
        }
        aurora = brands.get("AURORA 家居旗舰店")
        nordic = brands.get("Nordic Living 官方店")
        mellow = brands.get("Mellow Sleep")

        if aurora and session.execute(select(func.count(BrandAsset.id))).scalar_one() == 0:
            session.add_all(
                [
                    BrandAsset(
                        brand_id=aurora.id,
                        name="品牌视觉规范手册 V1.4",
                        folder="品牌设计规范",
                        content_type="application/pdf",
                        size=2048000,
                        saved_path="/seed/aurora/brand-guide-v1.4.pdf",
                        source="品牌方上传",
                        status="已解析",
                        metadata_json={"ext": "pdf"},
                    ),
                    BrandAsset(
                        brand_id=aurora.id,
                        name="2025 双十一详情页合集",
                        folder="详情页",
                        content_type="application/psd",
                        size=7340032,
                        saved_path="/seed/aurora/d11-detail-pages.psd",
                        source="历史案例",
                        status="可训练",
                        metadata_json={"ext": "psd"},
                    ),
                    BrandAsset(
                        brand_id=aurora.id,
                        name="官网首页截图集",
                        folder="官网素材",
                        content_type="image/png",
                        size=1258291,
                        saved_path="/seed/aurora/homepage-shots.zip",
                        source="官网采集",
                        status="可训练",
                        metadata_json={"ext": "png"},
                    ),
                    BrandAsset(
                        brand_id=aurora.id,
                        name="北欧卧室场景参考图",
                        folder="样例图",
                        content_type="image/jpeg",
                        size=824312,
                        saved_path="/seed/aurora/bedroom-scene.jpg",
                        source="设计团队",
                        status="待校验",
                        metadata_json={"ext": "jpg"},
                    ),
                    BrandAsset(
                        brand_id=nordic.id if nordic else None,
                        name="北欧风品牌规范草案",
                        folder="品牌设计规范",
                        content_type="application/pdf",
                        size=1024000,
                        saved_path="/seed/nordic/rules-draft.pdf",
                        source="品牌方上传",
                        status="已解析",
                        metadata_json={"ext": "pdf"},
                    ),
                    BrandAsset(
                        brand_id=mellow.id if mellow else None,
                        name="睡眠氛围场景图集",
                        folder="样例图",
                        content_type="image/jpeg",
                        size=952320,
                        saved_path="/seed/mellow/scene-pack.jpg",
                        source="设计团队",
                        status="可训练",
                        metadata_json={"ext": "jpg"},
                    ),
                ]
            )

        if aurora and session.execute(select(func.count(BrandTrainingTask.id))).scalar_one() == 0:
            session.add_all(
                [
                    BrandTrainingTask(
                        brand_id=aurora.id,
                        task_code="TR-240625-01",
                        title="品牌资产训练 #TR-240625-01",
                        status="生成成功",
                        summary="输入 36 份品牌资产，输出 design.md / layout.json / component_library.json",
                        created_at=datetime.fromisoformat("2026-06-25 09:12:00"),
                        completed_at=datetime.fromisoformat("2026-06-25 09:26:00"),
                    ),
                    BrandTrainingTask(
                        brand_id=aurora.id,
                        task_code="TR-240624-03",
                        title="品牌规则重训练 #TR-240624-03",
                        status="处理中",
                        summary="当前进行组件模式归纳，预计 6 分钟完成。",
                        created_at=datetime.fromisoformat("2026-06-24 19:18:00"),
                    ),
                    BrandTrainingTask(
                        brand_id=aurora.id,
                        task_code="TR-240623-02",
                        title="品牌素材补录训练 #TR-240623-02",
                        status="生成失败",
                        summary="失败原因：部分 PSD 素材解析异常，建议重新上传后发起训练。",
                        created_at=datetime.fromisoformat("2026-06-23 15:10:00"),
                        completed_at=datetime.fromisoformat("2026-06-23 15:14:00"),
                    ),
                ]
            )

        if aurora and session.execute(select(func.count(BrandRule.id))).scalar_one() == 0:
            session.add(
                BrandRule(
                    brand_id=aurora.id,
                    version="V1.4",
                    status="active",
                    rule_count=42,
                    layout_count=12,
                    prompt_count=18,
                    design_rules=[
                        {"title": "品牌调性", "description": "简洁、克制、带有科技家居感，强调自然光感与空间呼吸感。"},
                        {"title": "主色体系", "description": "主色以深蓝与暖白为核心，辅助色使用低饱和浅灰与淡金。"},
                        {"title": "字体规则", "description": "标题偏中黑，正文偏常规，强调信息层级与留白节奏。"},
                        {"title": "文案风格", "description": "标题短句、卖点拆分清晰，功能信息与场景利益点并行表达。"},
                    ],
                    layout_rules=[
                        {"title": "Hero 模块", "description": "左文案右大图，首屏突出核心卖点与场景视觉。"},
                        {"title": "Feature 模块", "description": "三列卡片结构，统一图文比例，适合功能点平铺表达。"},
                        {"title": "Parameter 模块", "description": "参数表横向排布，支持图标化表达和重点参数高亮。"},
                    ],
                    components=[
                        {"title": "标题区组件", "description": "支持品牌标题、副标题与简短卖点组合。"},
                        {"title": "卖点区组件", "description": "适合 3 到 4 个卖点并列展示。"},
                        {"title": "CTA 组件", "description": "强调行动按钮、利益点和促销信息的组合。"},
                    ],
                    prompt_templates=[
                        {"title": "详情页生成模板", "description": "适用于新品首发和常规详情页，默认输出 Hero / Feature / Scenario / CTA。"},
                        {"title": "场景图生成模板", "description": "强调家居氛围、自然光环境、产品主角突出、减少过度商业感。"},
                        {"title": "模块重生成模板", "description": "在保留品牌语言的前提下，对单个模块进行局部变体生成。"},
                    ],
                )
            )

        if aurora and session.execute(select(func.count(Product.id))).scalar_one() == 0:
            session.add_all(
                [
                    Product(
                        brand_id=aurora.id,
                        name="无线香薰机 Pro",
                        category="家居电器",
                        summary="支持超声波细腻雾化、低噪运行、夜灯氛围和定时功能，适用于卧室与客厅。",
                        brief="目标人群为 25-40 岁注重居家氛围和睡眠体验的城市人群，页面要突出静谧感和高颜值场景。",
                        design_direction="暖光、自然材质、留白充足，重点体现家居融合度和夜间使用场景。",
                        selling_points=["静音运行", "持久扩香", "自然夜灯", "一键定时", "家居友好设计", "易清洁水箱"],
                        materials=["商品主图", "商品场景图", "补充氛围图"],
                        selling_point_count=6,
                        asset_count=14,
                        updated_at=datetime.fromisoformat("2026-06-24 21:08:00"),
                    ),
                    Product(
                        brand_id=aurora.id,
                        name="凉感床品四件套",
                        category="家纺",
                        summary="面料凉感顺滑，适合夏季卧室场景，强调舒适睡眠与亲肤体验。",
                        brief="页面需要兼顾产品细节特写与卧室大场景展示，突出面料触感和降温卖点。",
                        design_direction="使用浅灰蓝和暖白，布局舒展，强调清凉和舒适感。",
                        selling_points=["凉感面料", "亲肤触感", "易打理", "适合夏季", "多尺寸可选"],
                        materials=["主图", "床品细节图", "卧室场景图"],
                        selling_point_count=5,
                        asset_count=9,
                        updated_at=datetime.fromisoformat("2026-06-24 18:40:00"),
                    ),
                    Product(
                        brand_id=aurora.id,
                        name="北欧风收纳架",
                        category="收纳用品",
                        summary="强调多层收纳、稳定承重与简洁外观，适合客厅与卧室。",
                        brief="需要表现收纳前后对比、层板细节和家居搭配氛围。",
                        design_direction="轻木纹、浅灰白、透气留白，突出收纳效率和空间整洁感。",
                        selling_points=["多层收纳", "稳定承重", "安装便捷", "百搭家居风"],
                        materials=["白底图", "收纳演示图", "空间搭配图"],
                        selling_point_count=4,
                        asset_count=7,
                        updated_at=datetime.fromisoformat("2026-06-23 16:55:00"),
                    ),
                ]
            )

        if session.execute(select(func.count(WorkflowRun.run_id))).scalar_one() == 0:
            session.add_all(
                [
                    WorkflowRun(
                        run_id="run-seed-240625-019",
                        status="completed",
                        task_code="DS-240625-019",
                        task_type="商品详情页",
                        project_name="BrandOS 商品详情页设计任务",
                        brand_name="AURORA 家居旗舰店",
                        product_name="无线香薰机 Pro",
                        workflow_mode="smart_recommend",
                        request_payload={"brand_name": "AURORA 家居旗舰店", "product_name": "无线香薰机 Pro"},
                        summary="已输出 Figma 页面，等待设计师审核。",
                        used_deepagents=True,
                        agent_report="阶段执行完成，建议进入人工审核。",
                        design_spec={"module_count": 7, "outputs": ["Figma 页面", "PSD 兼容文件"]},
                        warnings=[],
                        created_at=datetime.fromisoformat("2026-06-25 00:36:00"),
                        updated_at=datetime.fromisoformat("2026-06-25 00:41:00"),
                        completed_at=datetime.fromisoformat("2026-06-25 00:41:00"),
                    ),
                    WorkflowRun(
                        run_id="run-seed-240625-018",
                        status="running",
                        current_stage="layout_engine",
                        current_stage_title="Layout Engine",
                        current_stage_icon="grid",
                        task_code="DS-240625-018",
                        task_type="商品详情页",
                        project_name="BrandOS 商品详情页设计任务",
                        brand_name="AURORA 家居旗舰店",
                        product_name="北欧风收纳架",
                        workflow_mode="smart_recommend",
                        request_payload={"brand_name": "AURORA 家居旗舰店", "product_name": "北欧风收纳架"},
                        summary="当前执行到布局生成阶段，已完成 72%。",
                        used_deepagents=True,
                        warnings=[],
                        created_at=datetime.fromisoformat("2026-06-25 00:28:00"),
                        updated_at=datetime.fromisoformat("2026-06-25 00:28:00"),
                    ),
                    WorkflowRun(
                        run_id="run-seed-240624-014",
                        status="failed",
                        task_code="DS-240624-014",
                        task_type="商品详情页",
                        project_name="BrandOS 商品详情页设计任务",
                        brand_name="AURORA 家居旗舰店",
                        product_name="凉感床品四件套",
                        workflow_mode="smart_recommend",
                        request_payload={"brand_name": "AURORA 家居旗舰店", "product_name": "凉感床品四件套"},
                        summary="失败原因：参考素材质量不足，建议补充高质量场景图后重试。",
                        used_deepagents=False,
                        warnings=["参考素材质量不足"],
                        created_at=datetime.fromisoformat("2026-06-24 20:15:00"),
                        updated_at=datetime.fromisoformat("2026-06-24 20:17:00"),
                        completed_at=datetime.fromisoformat("2026-06-24 20:17:00"),
                    ),
                ]
            )
