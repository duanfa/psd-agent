from __future__ import annotations

import json
import os
from collections.abc import Mapping
from contextlib import contextmanager
from datetime import date, datetime
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
    inspect,
    or_,
    select,
    text,
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
    training_role: Mapped[str] = mapped_column(String(64), default="reference")
    include_in_training: Mapped[bool] = mapped_column(Boolean, default=False)
    quality_level: Mapped[str] = mapped_column(String(64), default="normal")
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
    markdown: Mapped[str | None] = mapped_column(Text, nullable=True)
    training_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_asset_ids: Mapped[list[int] | None] = mapped_column(JSON, nullable=True)
    website_urls: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    base_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    rule_type: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    page_type: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    source_kind: Mapped[str | None] = mapped_column(String(64), nullable=True)
    parent_rule_id: Mapped[int | None] = mapped_column(ForeignKey("brand_rules.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


RULE_TYPE_CORE = "core"
RULE_TYPE_DERIVED = "derived"
PAGE_TYPE_BRAND_IDENTITY = "brand_identity"
PAGE_TYPE_DETAIL_PAGE = "detail_page"
SOURCE_KIND_WEBSITE = "website"
SOURCE_KIND_ASSET_BATCH = "asset_batch"
RULE_TARGET_BRAND_CORE = "brand_core"
RULE_TARGET_DETAIL_PAGE_LAYOUT = "detail_page_layout"

RULE_TARGET_META: dict[str, dict[str, str]] = {
    RULE_TARGET_BRAND_CORE: {
        "label": "品牌设计规范",
        "rule_type": RULE_TYPE_CORE,
        "page_type": PAGE_TYPE_BRAND_IDENTITY,
        "source_kind": SOURCE_KIND_WEBSITE,
        "summary": "官网素材沉淀品牌级视觉约束、字体色彩和品牌语气。",
    },
    RULE_TARGET_DETAIL_PAGE_LAYOUT: {
        "label": "详情页布局规范",
        "rule_type": RULE_TYPE_DERIVED,
        "page_type": PAGE_TYPE_DETAIL_PAGE,
        "source_kind": SOURCE_KIND_ASSET_BATCH,
        "summary": "详情页素材沉淀模块布局、文字层级和图片区域规则。",
    },
}


def normalize_rule_target(training_target: str | None) -> str:
    if training_target in RULE_TARGET_META:
        return str(training_target)
    return RULE_TARGET_BRAND_CORE


def get_rule_target_meta(training_target: str | None) -> dict[str, str]:
    return RULE_TARGET_META[normalize_rule_target(training_target)]


def get_default_rule_target(rule: BrandRule | None) -> str:
    if rule is None:
        return RULE_TARGET_BRAND_CORE
    rule_type = rule.rule_type or RULE_TYPE_CORE
    page_type = rule.page_type or PAGE_TYPE_BRAND_IDENTITY
    if rule_type == RULE_TYPE_DERIVED and page_type == PAGE_TYPE_DETAIL_PAGE:
        return RULE_TARGET_DETAIL_PAGE_LAYOUT
    return RULE_TARGET_BRAND_CORE


def _target_filter_clauses(training_target: str) -> list[Any]:
    normalized = normalize_rule_target(training_target)
    meta = RULE_TARGET_META[normalized]
    if normalized == RULE_TARGET_BRAND_CORE:
        return [
            or_(BrandRule.rule_type == meta["rule_type"], BrandRule.rule_type.is_(None)),
            or_(BrandRule.page_type == meta["page_type"], BrandRule.page_type.is_(None)),
        ]
    return [
        BrandRule.rule_type == meta["rule_type"],
        BrandRule.page_type == meta["page_type"],
    ]


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

    run_id: Mapped[str] = mapped_column(String(100, collation="utf8mb4_unicode_ci"), primary_key=True)
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
    run_id: Mapped[str] = mapped_column(
        String(100, collation="utf8mb4_unicode_ci"),
        ForeignKey("workflow_runs.run_id"),
        index=True,
    )
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
    run_id: Mapped[str] = mapped_column(
        String(100, collation="utf8mb4_unicode_ci"),
        ForeignKey("workflow_runs.run_id"),
        index=True,
    )
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
    run_id: Mapped[str] = mapped_column(
        String(100, collation="utf8mb4_unicode_ci"),
        ForeignKey("workflow_runs.run_id"),
        index=True,
    )
    scope: Mapped[str] = mapped_column(String(100))
    title: Mapped[str] = mapped_column(Text)
    message: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict[str, Any] | list[Any] | str | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class WorkflowArtifact(Base):
    __tablename__ = "workflow_artifacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(
        String(100, collation="utf8mb4_unicode_ci"),
        ForeignKey("workflow_runs.run_id"),
        index=True,
    )
    output_dir: Mapped[str] = mapped_column(String(1024))
    preview_svg: Mapped[str] = mapped_column(String(1024))
    design_spec_path: Mapped[str] = mapped_column(String(1024))
    photoshop_jsx: Mapped[str] = mapped_column(String(1024))
    figma_plugin: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    figma_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    export_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    export_mode: Mapped[str | None] = mapped_column(String(64), nullable=True)
    export_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    editable_html: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    readme: Mapped[str] = mapped_column(String(1024))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DesignFeedback(Base):
    __tablename__ = "design_feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(
        String(100, collation="utf8mb4_unicode_ci"),
        ForeignKey("workflow_runs.run_id"),
        index=True,
    )
    feedback_type: Mapped[str] = mapped_column(String(64), default="designer_edit")
    author: Mapped[str] = mapped_column(String(100), default="designer")
    changes: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


def enabled() -> bool:
    return engine is not None


def init_db() -> None:
    if engine is not None:
        Base.metadata.create_all(bind=engine)
        _ensure_schema_upgrades()


def _ensure_schema_upgrades() -> None:
    if engine is None:
        return
    inspector = inspect(engine)
    table_names = inspector.get_table_names()
    if "workflow_artifacts" in table_names:
        artifact_existing = {
            column["name"] for column in inspector.get_columns("workflow_artifacts")
        }
        artifact_statements: list[str] = []
        if "figma_plugin" not in artifact_existing:
            artifact_statements.append(
                "ALTER TABLE workflow_artifacts ADD COLUMN figma_plugin VARCHAR(1024) NULL"
            )
        if "editable_html" not in artifact_existing:
            artifact_statements.append(
                "ALTER TABLE workflow_artifacts ADD COLUMN editable_html VARCHAR(1024) NULL"
            )
        if "figma_url" not in artifact_existing:
            artifact_statements.append(
                "ALTER TABLE workflow_artifacts ADD COLUMN figma_url VARCHAR(2048) NULL"
            )
        if "export_status" not in artifact_existing:
            artifact_statements.append(
                "ALTER TABLE workflow_artifacts ADD COLUMN export_status VARCHAR(64) NULL"
            )
        if "export_mode" not in artifact_existing:
            artifact_statements.append(
                "ALTER TABLE workflow_artifacts ADD COLUMN export_mode VARCHAR(64) NULL"
            )
        if "export_error" not in artifact_existing:
            artifact_statements.append(
                "ALTER TABLE workflow_artifacts ADD COLUMN export_error LONGTEXT NULL"
            )
        if artifact_statements:
            with engine.begin() as connection:
                for statement in artifact_statements:
                    connection.execute(text(statement))
    if "brand_assets" in table_names:
        asset_existing = {
            column["name"] for column in inspector.get_columns("brand_assets")
        }
        asset_statements: list[str] = []
        if "training_role" not in asset_existing:
            asset_statements.append(
                "ALTER TABLE brand_assets ADD COLUMN training_role VARCHAR(64) NOT NULL DEFAULT 'reference'"
            )
        if "include_in_training" not in asset_existing:
            asset_statements.append(
                "ALTER TABLE brand_assets ADD COLUMN include_in_training BOOLEAN NOT NULL DEFAULT FALSE"
            )
        if "quality_level" not in asset_existing:
            asset_statements.append(
                "ALTER TABLE brand_assets ADD COLUMN quality_level VARCHAR(64) NOT NULL DEFAULT 'normal'"
            )
        if asset_statements:
            with engine.begin() as connection:
                for statement in asset_statements:
                    connection.execute(text(statement))
    if "brand_rules" not in table_names:
        return
    existing = {column["name"] for column in inspector.get_columns("brand_rules")}
    statements: list[str] = []
    if "markdown" not in existing:
        statements.append("ALTER TABLE brand_rules ADD COLUMN markdown LONGTEXT NULL")
    if "training_prompt" not in existing:
        statements.append("ALTER TABLE brand_rules ADD COLUMN training_prompt LONGTEXT NULL")
    if "source_asset_ids" not in existing:
        statements.append("ALTER TABLE brand_rules ADD COLUMN source_asset_ids JSON NULL")
    if "website_urls" not in existing:
        statements.append("ALTER TABLE brand_rules ADD COLUMN website_urls JSON NULL")
    if "base_version" not in existing:
        statements.append("ALTER TABLE brand_rules ADD COLUMN base_version VARCHAR(64) NULL")
    if "rule_type" not in existing:
        statements.append("ALTER TABLE brand_rules ADD COLUMN rule_type VARCHAR(64) NULL")
    if "page_type" not in existing:
        statements.append("ALTER TABLE brand_rules ADD COLUMN page_type VARCHAR(64) NULL")
    if "source_kind" not in existing:
        statements.append("ALTER TABLE brand_rules ADD COLUMN source_kind VARCHAR(64) NULL")
    if "parent_rule_id" not in existing:
        statements.append("ALTER TABLE brand_rules ADD COLUMN parent_rule_id INTEGER NULL")
    if not statements:
        return
    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


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
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if hasattr(value, "model_dump"):
        try:
            return _jsonable(value.model_dump(mode="json"))
        except Exception:
            return _jsonable(value.model_dump())
    if isinstance(value, Mapping):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, list | tuple | set):
        return [_jsonable(item) for item in value]
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    return str(value)


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
        session.flush()

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
            session.flush()
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
                figma_plugin=artifact_paths.get("figma_plugin"),
                figma_url=artifact_paths.get("figma_url"),
                export_status=artifact_paths.get("export_status"),
                export_mode=artifact_paths.get("export_mode"),
                export_error=artifact_paths.get("export_error"),
                editable_html=artifact_paths.get("editable_html"),
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
            "warnings": run.warnings or [],
            "failure_reason": _workflow_failure_reason(run.status, run.warnings or [], logs),
        }


def _workflow_failure_reason(status: str, warnings: list[str], logs: list[str]) -> str | None:
    if status not in {"failed", "cancelled", "fallback_completed"} and not warnings:
        return None
    joined = "\n".join([*warnings, *logs]).lower()
    if "api key" in joined or "model" in joined or "llm" in joined:
        return "模型或密钥不可用"
    if "asset" in joined or "素材" in joined or "image" in joined:
        return "素材不足或图片处理失败"
    if "rule" in joined or "品牌规则" in joined:
        return "规则缺失或规则选择无效"
    if "artifact" in joined or "export" in joined or "导出" in joined:
        return "导出阶段失败"
    if status == "cancelled":
        return "任务被用户取消"
    if status == "fallback_completed":
        return "任务已降级完成，部分结果来自规则回退"
    return "任务执行失败，请查看阶段日志"


def _sanitize_request_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    data = dict(payload or {})
    model_config = data.get("model_config")
    if isinstance(model_config, dict):
        sanitized = dict(model_config)
        if "api_key" in sanitized:
            sanitized["api_key"] = ""
        data["model_config"] = sanitized
    model_settings = data.get("model_settings")
    if isinstance(model_settings, dict):
        sanitized = dict(model_settings)
        if "api_key" in sanitized:
            sanitized["api_key"] = ""
        data["model_settings"] = sanitized
    return data


def get_workflow_detail(run_id: str) -> dict[str, Any] | None:
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
            {
                "scope": log.scope,
                "title": log.title,
                "message": log.message,
                "payload": log.payload,
                "createdAt": log.created_at.isoformat() if log.created_at else None,
            }
            for log in session.execute(
                select(WorkflowLog)
                .where(WorkflowLog.run_id == run_id)
                .order_by(WorkflowLog.id.asc())
            ).scalars()
        ]
        artifact = session.execute(
            select(WorkflowArtifact)
            .where(WorkflowArtifact.run_id == run_id)
            .order_by(WorkflowArtifact.id.desc())
            .limit(1)
        ).scalar_one_or_none()
        feedback = [
            {
                "id": row.id,
                "runId": row.run_id,
                "feedbackType": row.feedback_type,
                "author": row.author,
                "changes": row.changes or [],
                "notes": row.notes,
                "createdAt": row.created_at.isoformat() if row.created_at else None,
            }
            for row in session.execute(
                select(DesignFeedback)
                .where(DesignFeedback.run_id == run_id)
                .order_by(DesignFeedback.created_at.desc(), DesignFeedback.id.desc())
            ).scalars()
        ]
        assets = [
            {
                "name": asset.name,
                "contentType": asset.content_type,
                "size": asset.size,
                "savedPath": asset.saved_path,
                "bucket": asset.bucket,
                "extractedText": asset.extracted_text,
            }
            for asset in session.execute(
                select(WorkflowAsset)
                .where(WorkflowAsset.run_id == run_id)
                .order_by(WorkflowAsset.id.asc())
            ).scalars()
        ]
        artifact_data = (
            {
                "previewSvg": artifact.preview_svg,
                "designSpec": artifact.design_spec_path,
                "photoshopJsx": artifact.photoshop_jsx,
                "figmaPlugin": artifact.figma_plugin,
                "figmaUrl": artifact.figma_url,
                "exportStatus": artifact.export_status or ("completed" if artifact.figma_url else "fallback_script"),
                "exportMode": artifact.export_mode or ("figma_url" if artifact.figma_url else "script"),
                "exportError": artifact.export_error,
                "editableHtml": artifact.editable_html,
                "readme": artifact.readme,
                "outputDir": artifact.output_dir,
            }
            if artifact
            else None
        )
        log_messages = [item["message"] for item in logs]
        return {
            "runId": run.run_id,
            "taskCode": run.task_code or run.run_id,
            "taskType": run.task_type or "商品详情页",
            "status": run.status,
            "currentStage": run.current_stage,
            "projectName": run.project_name or "",
            "brandName": run.brand_name or "",
            "productName": run.product_name or "",
            "workflowMode": run.workflow_mode or "",
            "summary": run.summary or "",
            "usedDeepagents": run.used_deepagents,
            "agentReport": run.agent_report or "",
            "requestPayload": _sanitize_request_payload(run.request_payload),
            "designSpec": run.design_spec or {},
            "warnings": run.warnings or [],
            "failureReason": _workflow_failure_reason(run.status, run.warnings or [], log_messages),
            "createdAt": run.created_at.isoformat() if run.created_at else None,
            "completedAt": run.completed_at.isoformat() if run.completed_at else None,
            "stages": stages,
            "logs": logs,
            "assets": assets,
            "artifacts": artifact_data,
            "feedback": feedback,
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
        if not isinstance(value, list):
            return None
        stage_ids = {str(item.get("id")) for item in value if isinstance(item, dict)}
        if "image_generation" not in stage_ids:
            value = [
                *value[:4],
                {"id": "image_generation", "title": "图片生成 Agent", "icon": "image"},
                *value[4:],
            ]
        return value


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
                    "trainingRole": asset.training_role,
                    "includeInTraining": asset.include_in_training,
                    "qualityLevel": asset.quality_level,
                    "size": asset.size,
                    "createdAt": asset.created_at.isoformat() if asset.created_at else None,
                }
                for asset in assets[:30]
            ],
            "uploadForm": (page or {}).get("uploadForm", {}),
        }


def create_brand(name: str, status: str = "active") -> dict[str, Any]:
    with session_scope() as session:
        if session is None:
            raise ValueError("database disabled")
        brand_name = name.strip()
        if not brand_name:
            raise ValueError("brand name is required")
        existing = session.execute(select(Brand).where(Brand.name == brand_name)).scalar_one_or_none()
        if existing is not None:
            raise ValueError("brand name already exists")
        row = Brand(name=brand_name, status=status.strip() or "active")
        session.add(row)
        session.flush()
        return {
            "id": row.id,
            "name": row.name,
            "status": row.status,
            "assets": 0,
        }


def update_brand(brand_id: int, name: str, status: str = "active") -> dict[str, Any]:
    with session_scope() as session:
        if session is None:
            raise ValueError("database disabled")
        brand = session.get(Brand, brand_id)
        if brand is None:
            raise ValueError("brand not found")
        brand_name = name.strip()
        if not brand_name:
            raise ValueError("brand name is required")
        existing = session.execute(
            select(Brand).where(Brand.name == brand_name, Brand.id != brand_id)
        ).scalar_one_or_none()
        if existing is not None:
            raise ValueError("brand name already exists")
        brand.name = brand_name
        brand.status = status.strip() or "active"
        brand.updated_at = datetime.utcnow()
        asset_count = session.execute(
            select(func.count(BrandAsset.id)).where(BrandAsset.brand_id == brand.id)
        ).scalar_one()
        return {
            "id": brand.id,
            "name": brand.name,
            "status": brand.status,
            "assets": asset_count,
        }


def delete_brand(brand_id: int) -> dict[str, Any]:
    with session_scope() as session:
        if session is None:
            raise ValueError("database disabled")
        brand = session.get(Brand, brand_id)
        if brand is None:
            raise ValueError("brand not found")
        brand_count = session.execute(select(func.count(Brand.id))).scalar_one()
        if brand_count <= 1:
            raise ValueError("at least one brand is required")
        assets = list(session.execute(select(BrandAsset).where(BrandAsset.brand_id == brand_id)).scalars())
        file_paths = [asset.saved_path for asset in assets if asset.saved_path]
        for model in (BrandTrainingTask, BrandRule, Product):
            for row in session.execute(select(model).where(model.brand_id == brand_id)).scalars():
                session.delete(row)
        for asset in assets:
            session.delete(asset)
        session.delete(brand)
        return {
            "id": brand_id,
            "deletedAssets": len(assets),
            "filePaths": file_paths,
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
                training_role="reference",
                include_in_training=False,
                quality_level="normal",
                extracted_text=file_item.get("extracted_text"),
                metadata_json={
                    "original_name": file_item.get("name"),
                    "bucket": file_item.get("bucket"),
                    **(file_item.get("metadata") or {}),
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
                    "trainingRole": row.training_role,
                    "includeInTraining": row.include_in_training,
                    "qualityLevel": row.quality_level,
                }
            )
        return created


def delete_brand_asset(asset_id: int) -> dict[str, Any]:
    with session_scope() as session:
        if session is None:
            raise ValueError("database disabled")
        asset = session.get(BrandAsset, asset_id)
        if asset is None:
            raise ValueError("asset not found")
        result = {
            "id": asset.id,
            "brandId": asset.brand_id,
            "savedPath": asset.saved_path or "",
        }
        session.delete(asset)
        return result


def get_brand_asset(asset_id: int) -> dict[str, Any] | None:
    with session_scope() as session:
        if session is None:
            return None
        asset = session.get(BrandAsset, asset_id)
        if asset is None:
            return None
        brand = session.get(Brand, asset.brand_id) if asset.brand_id else None
        return {
            "id": asset.id,
            "brandId": asset.brand_id,
            "brandName": brand.name if brand else "",
            "name": asset.name,
            "folder": asset.folder,
            "contentType": asset.content_type or "",
            "size": asset.size,
            "savedPath": asset.saved_path or "",
            "source": asset.source or "",
            "status": asset.status,
            "trainingRole": asset.training_role,
            "includeInTraining": asset.include_in_training,
            "qualityLevel": asset.quality_level,
            "extractedText": asset.extracted_text or "",
            "metadata": asset.metadata_json or {},
            "createdAt": asset.created_at.isoformat() if asset.created_at else None,
        }


def update_brand_asset_training_meta(
    asset_id: int,
    training_role: str,
    include_in_training: bool,
    quality_level: str,
) -> dict[str, Any]:
    with session_scope() as session:
        if session is None:
            raise ValueError("database disabled")
        asset = session.get(BrandAsset, asset_id)
        if asset is None:
            raise ValueError("asset not found")
        asset.training_role = training_role.strip() or "reference"
        asset.include_in_training = bool(include_in_training)
        asset.quality_level = quality_level.strip() or "normal"
        asset.updated_at = datetime.utcnow()
        session.merge(asset)
        return {
            "id": asset.id,
            "trainingRole": asset.training_role,
            "includeInTraining": asset.include_in_training,
            "qualityLevel": asset.quality_level,
        }


def get_brand_rules_data() -> dict[str, Any] | None:
    return get_brand_rules_page_data()


def _serialize_rule_version(
    rule: BrandRule,
    parent_versions: dict[int, str] | None = None,
) -> dict[str, Any]:
    target_key = get_default_rule_target(rule)
    meta = get_rule_target_meta(target_key)
    return {
        "id": rule.id,
        "version": rule.version,
        "status": rule.status,
        "createdAt": rule.created_at.isoformat() if rule.created_at else None,
        "baseVersion": rule.base_version or "",
        "ruleCount": rule.rule_count,
        "layoutCount": rule.layout_count,
        "promptCount": rule.prompt_count,
        "ruleType": rule.rule_type or meta["rule_type"],
        "pageType": rule.page_type or meta["page_type"],
        "sourceKind": rule.source_kind or meta["source_kind"],
        "parentRuleId": rule.parent_rule_id,
        "parentVersion": (parent_versions or {}).get(rule.parent_rule_id or -1, ""),
        "targetKey": target_key,
        "targetLabel": meta["label"],
    }


def _serialize_workflow_rule(rule: BrandRule, brand: Brand, parent_versions: dict[int, str] | None = None) -> dict[str, Any]:
    target_key = get_default_rule_target(rule)
    target_meta = get_rule_target_meta(target_key)
    markdown = rule.markdown or _default_rule_markdown(
        brand.name,
        rule.version,
        rule.design_rules or [],
        rule.layout_rules or [],
        rule.prompt_templates or [],
        rule.website_urls or [],
        target_label=target_meta["label"],
        target_key=target_key,
    )
    return {
        "id": rule.id,
        "brandId": brand.id,
        "brandName": brand.name,
        "version": rule.version,
        "status": rule.status,
        "targetKey": target_key,
        "targetLabel": target_meta["label"],
        "ruleType": rule.rule_type or target_meta["rule_type"],
        "pageType": rule.page_type or target_meta["page_type"],
        "sourceKind": rule.source_kind or target_meta["source_kind"],
        "parentRuleId": rule.parent_rule_id,
        "parentVersion": (parent_versions or {}).get(rule.parent_rule_id or -1, ""),
        "designRules": rule.design_rules or [],
        "layoutRules": rule.layout_rules or [],
        "components": rule.components or [],
        "promptTemplates": rule.prompt_templates or [],
        "websiteUrls": rule.website_urls or [],
        "trainingPrompt": rule.training_prompt or "",
        "markdown": markdown,
    }


def get_workflow_rule_context(
    core_rule_id: int | None = None,
    detail_page_rule_id: int | None = None,
    brand_name: str | None = None,
) -> dict[str, Any]:
    with session_scope() as session:
        if session is None:
            raise ValueError("database disabled")

        def load_rule(rule_id: int, expected_target: str) -> tuple[BrandRule, Brand]:
            row = session.execute(
                select(BrandRule, Brand)
                .join(Brand, BrandRule.brand_id == Brand.id)
                .where(BrandRule.id == rule_id)
                .limit(1)
            ).first()
            if row is None:
                raise ValueError("brand rule not found")
            rule, brand = row
            actual_target = get_default_rule_target(rule)
            if actual_target != expected_target:
                raise ValueError("brand rule target does not match workflow selection")
            return rule, brand

        core_payload: dict[str, Any] | None = None
        detail_payload: dict[str, Any] | None = None
        selected_brand_id: int | None = None
        selected_brand_name = ""

        def default_brand_id() -> int | None:
            name = (brand_name or "").strip()
            if name:
                brand = session.execute(
                    select(Brand).where(Brand.name == name).limit(1)
                ).scalar_one_or_none()
                if brand is not None:
                    return brand.id
            active_core = session.execute(
                select(BrandRule)
                .where(BrandRule.status == "active", *_target_filter_clauses(RULE_TARGET_BRAND_CORE))
                .order_by(BrandRule.updated_at.desc(), BrandRule.id.desc())
                .limit(1)
            ).scalar_one_or_none()
            return active_core.brand_id if active_core is not None else None

        if not core_rule_id and not detail_page_rule_id:
            brand_id = default_brand_id()
            if brand_id:
                core_default = session.execute(
                    select(BrandRule)
                    .where(
                        BrandRule.brand_id == brand_id,
                        BrandRule.status == "active",
                        *_target_filter_clauses(RULE_TARGET_BRAND_CORE),
                    )
                    .order_by(BrandRule.updated_at.desc(), BrandRule.id.desc())
                    .limit(1)
                ).scalar_one_or_none()
                detail_default = session.execute(
                    select(BrandRule)
                    .where(
                        BrandRule.brand_id == brand_id,
                        BrandRule.status == "active",
                        *_target_filter_clauses(RULE_TARGET_DETAIL_PAGE_LAYOUT),
                    )
                    .order_by(BrandRule.updated_at.desc(), BrandRule.id.desc())
                    .limit(1)
                ).scalar_one_or_none()
                core_rule_id = core_default.id if core_default else None
                detail_page_rule_id = detail_default.id if detail_default else None

        if core_rule_id:
            core_rule, core_brand = load_rule(core_rule_id, RULE_TARGET_BRAND_CORE)
            parent_versions = {core_rule.id: core_rule.version}
            core_payload = _serialize_workflow_rule(core_rule, core_brand, parent_versions)
            selected_brand_id = core_brand.id
            selected_brand_name = core_brand.name

        if detail_page_rule_id:
            detail_rule, detail_brand = load_rule(detail_page_rule_id, RULE_TARGET_DETAIL_PAGE_LAYOUT)
            parent_versions = {detail_rule.id: detail_rule.version}
            if detail_rule.parent_rule_id:
                parent = session.get(BrandRule, detail_rule.parent_rule_id)
                if parent is not None:
                    parent_versions[parent.id] = parent.version
            detail_payload = _serialize_workflow_rule(detail_rule, detail_brand, parent_versions)
            if selected_brand_id is not None and detail_brand.id != selected_brand_id:
                raise ValueError("所选品牌核心规则与详情页规则不属于同一品牌，请重新选择同品牌的规则组合")
            selected_brand_id = detail_brand.id
            selected_brand_name = detail_brand.name

        return {
            "brandId": selected_brand_id,
            "brandName": selected_brand_name,
            "coreRule": core_payload,
            "detailPageRule": detail_payload,
        }


def get_brand_rules_page_data(
    brand_id: int | None = None,
    version_id: int | None = None,
) -> dict[str, Any] | None:
    with session_scope() as session:
        if session is None:
            return None
        page = _setting(session, "brand_rules_page", {})
        brands = list(session.execute(select(Brand).order_by(Brand.id.asc())).scalars())
        if not brands:
            return None
        selected_brand = next((brand for brand in brands if brand.id == brand_id), brands[0])
        brand_rule_rows = list(
            session.execute(
                select(BrandRule)
                .where(BrandRule.brand_id == selected_brand.id)
                .order_by(BrandRule.updated_at.desc(), BrandRule.id.desc())
            ).scalars()
        )
        parent_versions = {item.id: item.version for item in brand_rule_rows}
        if version_id:
            rule = next((item for item in brand_rule_rows if item.id == version_id), None)
        else:
            rule = brand_rule_rows[0] if brand_rule_rows else None
        versions = [_serialize_rule_version(item, parent_versions) for item in brand_rule_rows]
        assets = [
            {
                "id": asset.id,
                "name": asset.name,
                "folder": asset.folder,
                "status": asset.status,
                "trainingRole": asset.training_role,
                "includeInTraining": asset.include_in_training,
                "qualityLevel": asset.quality_level,
            }
            for asset in session.execute(
                select(BrandAsset)
                .where(BrandAsset.brand_id == selected_brand.id)
                .order_by(BrandAsset.created_at.desc(), BrandAsset.id.desc())
            ).scalars()
        ]
        brand_rows = []
        for brand in brands:
            latest_rule = session.execute(
                select(BrandRule)
                .where(BrandRule.brand_id == brand.id)
                .order_by(BrandRule.updated_at.desc(), BrandRule.id.desc())
                .limit(1)
            ).scalar_one_or_none()
            active_core = session.execute(
                select(BrandRule)
                .where(
                    BrandRule.brand_id == brand.id,
                    BrandRule.status == "active",
                    *_target_filter_clauses(RULE_TARGET_BRAND_CORE),
                )
                .order_by(BrandRule.updated_at.desc(), BrandRule.id.desc())
                .limit(1)
            ).scalar_one_or_none()
            active_detail = session.execute(
                select(BrandRule)
                .where(
                    BrandRule.brand_id == brand.id,
                    BrandRule.status == "active",
                    *_target_filter_clauses(RULE_TARGET_DETAIL_PAGE_LAYOUT),
                )
                .order_by(BrandRule.updated_at.desc(), BrandRule.id.desc())
                .limit(1)
            ).scalar_one_or_none()
            brand_rows.append(
                {
                    "id": brand.id,
                    "name": brand.name,
                    "status": brand.status,
                    "version": latest_rule.version if latest_rule else "未训练",
                    "ruleCount": latest_rule.rule_count if latest_rule else 0,
                    "coreVersion": active_core.version if active_core else "",
                    "detailPageVersion": active_detail.version if active_detail else "",
                    "totalVersions": session.execute(
                        select(func.count(BrandRule.id)).where(BrandRule.brand_id == brand.id)
                    ).scalar_one(),
                }
            )
        active_versions: dict[str, dict[str, Any] | None] = {}
        for target_key in RULE_TARGET_META:
            active_rule = session.execute(
                select(BrandRule)
                .where(
                    BrandRule.brand_id == selected_brand.id,
                    BrandRule.status == "active",
                    *_target_filter_clauses(target_key),
                )
                .order_by(BrandRule.updated_at.desc(), BrandRule.id.desc())
                .limit(1)
            ).scalar_one_or_none()
            active_versions[target_key] = (
                _serialize_rule_version(active_rule, parent_versions) if active_rule else None
            )
        target_summaries = [
            {
                "targetKey": target_key,
                "label": meta["label"],
                "summary": meta["summary"],
                "count": len([item for item in versions if item["targetKey"] == target_key]),
                "activeVersion": (active_versions[target_key] or {}).get("version", ""),
            }
            for target_key, meta in RULE_TARGET_META.items()
        ]
        if rule is None:
            return {
                "page": page,
                "brands": brand_rows,
                "selectedBrand": {"id": selected_brand.id, "name": selected_brand.name},
                "overview": [
                    {"label": "规则版本", "value": "未训练", "description": "当前生效版本"},
                    {"label": "规则类型", "value": "未选择", "description": "请先训练品牌级或详情页规则"},
                    {"label": "设计规则说明", "value": 0, "description": "条结构化规则"},
                    {"label": "布局规则摘要", "value": 0, "description": "模块模板"},
                    {"label": "Prompt 模板摘要", "value": 0, "description": "场景模板"},
                ],
                "designRules": [],
                "layoutRules": [],
                "components": [],
                "promptTemplates": [],
                "versions": versions,
                "selectedVersionId": version_id,
                "markdown": "",
                "trainingPrompt": default_training_prompt(RULE_TARGET_BRAND_CORE),
                "sourceAssets": assets,
                "websiteUrls": [],
                "selectedTargetKey": RULE_TARGET_BRAND_CORE,
                "activeVersions": active_versions,
                "targetSummaries": target_summaries,
                "emptyState": f"{selected_brand.name} 还没有品牌规则，请先上传品牌资产并发起训练。",
            }
        version_id = rule.id
        target_key = get_default_rule_target(rule)
        target_meta = get_rule_target_meta(target_key)
        markdown = rule.markdown or _default_rule_markdown(
            selected_brand.name,
            rule.version,
            rule.design_rules or [],
            rule.layout_rules or [],
            rule.prompt_templates or [],
            rule.website_urls or [],
            target_label=target_meta["label"],
            target_key=target_key,
        )
        return {
            "page": page,
            "brands": brand_rows,
            "selectedBrand": {"id": selected_brand.id, "name": selected_brand.name},
            "overview": [
                {"label": "规则版本", "value": rule.version, "description": "当前查看版本"},
                {"label": "规则类型", "value": target_meta["label"], "description": "规则层级与页面类型"},
                {"label": "设计规则说明", "value": rule.rule_count, "description": "条结构化规则"},
                {"label": "布局规则摘要", "value": rule.layout_count, "description": "模块模板"},
                {"label": "Prompt 模板摘要", "value": rule.prompt_count, "description": "场景模板"},
            ],
            "designRules": rule.design_rules or [],
            "layoutRules": rule.layout_rules or [],
            "components": rule.components or [],
            "promptTemplates": rule.prompt_templates or [],
            "versions": versions,
            "selectedVersionId": version_id,
            "markdown": markdown,
            "trainingPrompt": rule.training_prompt or default_training_prompt(target_key),
            "sourceAssets": assets,
            "websiteUrls": rule.website_urls or [],
            "selectedTargetKey": target_key,
            "activeVersions": active_versions,
            "targetSummaries": target_summaries,
            "emptyState": "",
        }


def _clip(value: str, limit: int = 180) -> str:
    text_value = " ".join((value or "").split())
    return text_value[:limit] + ("..." if len(text_value) > limit else "")


def _prompt_focuses(prompt: str) -> list[str]:
    mapping = [
        ("色彩", ("色彩", "配色", "颜色", "主色", "辅助色")),
        ("字体", ("字体", "字号", "字重", "排版")),
        ("布局", ("布局", "结构", "模块", "版式", "栅格")),
        ("组件", ("组件", "按钮", "卡片", "标签", "图标")),
        ("文案语气", ("文案", "语气", "卖点", "标题", "口吻")),
        ("禁用规则", ("禁止", "不要", "避免", "不可", "负面")),
        ("详情页转化", ("详情页", "转化", "购买", "cta", "首屏")),
    ]
    lowered = prompt.lower()
    focuses = [label for label, keywords in mapping if any(keyword.lower() in lowered for keyword in keywords)]
    return focuses or ["视觉规范", "布局结构", "组件模式", "文案语气"]


def _asset_rule_summary(asset: BrandAsset) -> dict[str, str]:
    extracted = _clip(asset.extracted_text or "", 220)
    metadata = asset.metadata_json or {}
    original_name = metadata.get("original_name") if isinstance(metadata, dict) else ""
    source = asset.source or original_name or "未知来源"
    description = (
        f"{asset.folder} / {asset.content_type or '未知类型'} / {source}。"
        f"{'可解析内容：' + extracted if extracted else '暂无可解析文本，按文件类型和命名沉淀视觉约束。'}"
    )
    return {"title": asset.name, "description": description}


def _asset_training_weight(asset: BrandAsset) -> float:
    role = (asset.training_role or "").lower()
    quality = (asset.quality_level or "").lower()
    weight = 1.0
    if asset.include_in_training:
        weight += 0.5
    if role in {"core", "golden", "canonical", "high_quality"}:
        weight += 0.8
    if role in {"exclude", "negative"}:
        weight -= 0.8
    if quality in {"golden", "excellent", "high"}:
        weight += 0.7
    if quality in {"low", "poor"}:
        weight -= 0.5
    return max(0.1, round(weight, 2))


def _asset_wireframe_specs(assets: list[BrandAsset]) -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    for asset in assets:
        metadata = asset.metadata_json or {}
        spec = metadata.get("wireframe_spec") if isinstance(metadata, dict) else None
        if isinstance(spec, dict):
            specs.append({"asset_id": asset.id, "asset_name": asset.name, "spec": spec})
    return specs


def _infer_slot_role(text: str, media_path: str = "") -> str:
    normalized = f"{text} {media_path}".lower()
    checks = [
        ("hero", ("hero", "主图", "头图", "视频", "banner", "9:16")),
        ("product_gallery", ("图集", "packshot", "产品", "product")),
        ("lifestyle", ("lifestyle", "场景", "搭配", "model", "routine", "day")),
        ("recommendation", ("推荐", "new arrivals", "member section", "koi")),
        ("brand_story", ("brand story", "品牌故事", "品牌")),
        ("size", ("尺码", "size", "参数", "规格")),
        ("interaction", ("互动", "cta", "购买")),
    ]
    for role, keywords in checks:
        if any(keyword in normalized for keyword in keywords):
            return role
    return "detail"


def _build_layout_schema_from_assets(
    assets: list[BrandAsset],
    target_key: str,
) -> dict[str, Any]:
    wireframes = _asset_wireframe_specs(assets)
    source_assets = [
        {
            "id": asset.id,
            "name": asset.name,
            "folder": asset.folder,
            "content_type": asset.content_type or "",
            "training_role": asset.training_role,
            "quality_level": asset.quality_level,
            "weight": _asset_training_weight(asset),
        }
        for asset in assets
    ]
    schema: dict[str, Any] = {
        "schema_version": "brandos_layout_schema.v1",
        "page_type": "detail_page" if target_key == RULE_TARGET_DETAIL_PAGE_LAYOUT else "brand_core_reference",
        "source_assets": source_assets,
        "canvas": {"width": 790, "height_mode": "auto", "unit": "px"},
        "sections": [],
        "image_slots": [],
        "text_layers": [],
        "component_templates": [],
    }

    section_index = 1
    for wireframe in wireframes[:4]:
        spec = wireframe["spec"]
        for sheet in (spec.get("sheets") or [])[:3]:
            objects = sheet.get("objects") or []
            cells = sheet.get("cells") or []
            image_objects = [obj for obj in objects if obj.get("type") == "image"]
            text_objects = [obj for obj in objects if obj.get("text")]
            if not image_objects and not cells:
                continue
            dims = sheet.get("dimensions") or {}
            section_id = f"wf_{section_index:02d}_{str(sheet.get('name') or 'sheet').lower()}"
            section = {
                "id": section_id,
                "name": str(sheet.get("name") or f"线框页 {section_index}"),
                "component_type": "wireframe_sheet",
                "source_asset": wireframe["asset_name"],
                "x": 0,
                "y": 0,
                "w": int(dims.get("width_px") or 790),
                "h": int(dims.get("height_px") or 900),
                "background": {"type": "solid", "color": "#ffffff"},
                "z_index": section_index,
            }
            schema["sections"].append(section)
            for image_index, obj in enumerate(image_objects[:36], start=1):
                box = obj.get("box") or {}
                slot_role = _infer_slot_role(str(obj.get("name") or ""), str(obj.get("media_path") or ""))
                schema["image_slots"].append(
                    {
                        "id": f"{section_id}_img_{image_index:02d}",
                        "section_id": section_id,
                        "role": slot_role,
                        "asset_type": slot_role,
                        "x": int(box.get("x") or 0),
                        "y": int(box.get("y") or 0),
                        "w": int(box.get("w") or 1),
                        "h": int(box.get("h") or 1),
                        "fit": "cover",
                        "crop": "center",
                        "source_media_path": obj.get("media_path") or "",
                        "cell_anchor": obj.get("cell_anchor") or {},
                    }
                )
            for text_index, item in enumerate([*text_objects, *cells][:80], start=1):
                box = item.get("box") or {}
                text = str(item.get("text") or "")
                schema["text_layers"].append(
                    {
                        "id": f"{section_id}_txt_{text_index:02d}",
                        "section_id": section_id,
                        "role": _infer_slot_role(text),
                        "text": text[:300],
                        "x": int(box.get("x") or 0),
                        "y": int(box.get("y") or 0),
                        "w": int(box.get("w") or 160),
                        "h": int(box.get("h") or 28),
                        "font": (item.get("style") or {}).get("font") if isinstance(item.get("style"), dict) else "",
                        "font_size": (item.get("style") or {}).get("font_size") if isinstance(item.get("style"), dict) else None,
                    }
                )
            section_index += 1

    if not schema["sections"]:
        template = [
            ("hero", "首屏主视觉", 960),
            ("product_gallery", "产品图集", 820),
            ("lifestyle", "场景展示", 860),
            ("detail", "细节卖点", 760),
            ("size", "尺码参数", 640),
            ("recommendation", "人气推荐", 760),
            ("brand_story", "品牌故事", 720),
        ]
        y = 0
        for index, (role, name, height) in enumerate(template, start=1):
            section_id = f"section_{index:02d}_{role}"
            schema["sections"].append(
                {
                    "id": section_id,
                    "name": name,
                    "component_type": role,
                    "x": 0,
                    "y": y,
                    "w": 790,
                    "h": height,
                    "background": {"type": "solid", "color": "#ffffff" if index % 2 else "#f7f7f4"},
                    "z_index": index,
                }
            )
            schema["image_slots"].append(
                {
                    "id": f"{section_id}_image",
                    "section_id": section_id,
                    "role": role,
                    "asset_type": role,
                    "x": 40,
                    "y": 120,
                    "w": 710,
                    "h": max(260, height - 200),
                    "fit": "cover",
                    "crop": "center",
                }
            )
            y += height

    schema["component_templates"] = [
        {
            "id": item["id"],
            "name": item["name"],
            "component_type": item["component_type"],
            "image_slot_count": len([slot for slot in schema["image_slots"] if slot.get("section_id") == item["id"]]),
            "text_layer_count": len([layer for layer in schema["text_layers"] if layer.get("section_id") == item["id"]]),
        }
        for item in schema["sections"]
    ]
    return schema


def _build_visual_tokens(brand_name: str, assets: list[BrandAsset]) -> dict[str, Any]:
    return {
        "brand_name": brand_name,
        "asset_weights": [
            {
                "asset_id": asset.id,
                "asset_name": asset.name,
                "training_role": asset.training_role,
                "quality_level": asset.quality_level,
                "weight": _asset_training_weight(asset),
            }
            for asset in assets
        ],
        "color_policy": "优先从高权重品牌资产与历史详情页中提取主色、背景色和辅助色；不得由单次商品素材覆盖 Core Rule。",
        "typography_policy": "字体、字号、字重和中英文字体关系进入 Core Rule；生成任务只允许在规则范围内选择。",
    }


def _score_rule_quality(
    target_key: str,
    design_rules: list[dict[str, Any]],
    layout_rules: list[dict[str, Any]],
    components: list[dict[str, Any]],
) -> dict[str, Any]:
    layout_schema = next(
        (item.get("schema") for item in layout_rules if item.get("title") == "__layout_schema__"),
        None,
    )
    image_slots = next(
        (item.get("slots") for item in components if item.get("title") == "__image_slots__"),
        None,
    )
    visual_tokens = next(
        (item.get("tokens") for item in design_rules if item.get("title") == "__visual_tokens__"),
        None,
    )
    checks = {
        "has_visual_tokens": isinstance(visual_tokens, dict),
        "has_layout_schema": target_key != RULE_TARGET_DETAIL_PAGE_LAYOUT or isinstance(layout_schema, dict),
        "has_sections": target_key != RULE_TARGET_DETAIL_PAGE_LAYOUT or (isinstance(layout_schema, dict) and bool(layout_schema.get("sections"))),
        "has_image_slots": target_key != RULE_TARGET_DETAIL_PAGE_LAYOUT or (isinstance(image_slots, list) and bool(image_slots)),
        "has_components": bool([item for item in components if not str(item.get("title") or "").startswith("__")]),
        "has_human_readable_rules": bool(
            [item for item in [*design_rules, *layout_rules] if not str(item.get("title") or "").startswith("__")]
        ),
    }
    weights = (
        {
            "has_visual_tokens": 45,
            "has_components": 20,
            "has_human_readable_rules": 35,
        }
        if target_key == RULE_TARGET_BRAND_CORE
        else {
            "has_visual_tokens": 5,
            "has_layout_schema": 30,
            "has_sections": 25,
            "has_image_slots": 25,
            "has_components": 8,
            "has_human_readable_rules": 7,
        }
    )
    score = sum(weight for key, weight in weights.items() if checks.get(key))
    max_score = sum(weights.values())
    overall = round(score / max_score * 100, 1)
    blockers = []
    if target_key == RULE_TARGET_DETAIL_PAGE_LAYOUT and not checks["has_layout_schema"]:
        blockers.append("缺少可执行 layout_schema，生成阶段会退回通用模板")
    if target_key == RULE_TARGET_DETAIL_PAGE_LAYOUT and not checks["has_image_slots"]:
        blockers.append("缺少 image_slots，素材无法精准匹配图片槽")
    if target_key == RULE_TARGET_BRAND_CORE and not checks["has_visual_tokens"]:
        blockers.append("缺少 visual_tokens，品牌规范仍主要依赖文本提示词")
    return {
        "overall": overall,
        "checks": checks,
        "blocking_issues": blockers,
        "publish_recommendation": "ready" if overall >= 75 and not blockers else "needs_review",
    }


def _merge_rule_lists(
    base_items: list[dict[str, Any]] | None,
    new_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in [*(base_items or []), *new_items]:
        title = str(item.get("title") or "")
        if title in seen:
            continue
        seen.add(title)
        normalized = dict(item)
        normalized["title"] = title
        normalized["description"] = str(item.get("description") or "")
        merged.append(normalized)
    return merged


def _build_trained_rule_content(
    brand_name: str,
    version: str,
    assets: list[BrandAsset],
    prompt: str,
    website_urls: list[str],
    base_rule: BrandRule | None,
    training_target: str,
) -> dict[str, Any]:
    target_key = normalize_rule_target(training_target)
    asset_names = [asset.name for asset in assets]
    folder_names = sorted({asset.folder for asset in assets})
    focuses = _prompt_focuses(prompt)
    source_assets = [_asset_rule_summary(asset) for asset in assets]
    base_text = f"叠加历史版本 {base_rule.version}" if base_rule else "不叠加历史版本"
    website_count = len([url for url in website_urls if url])
    focus_text = "、".join(focuses)
    source_text = "、".join(asset_names) or "未选择素材"
    folder_text = "、".join(folder_names) or ("官网 URL" if website_count else "空白输入")

    if target_key == RULE_TARGET_BRAND_CORE:
        visual_tokens = _build_visual_tokens(brand_name, assets)
        new_design_rules = [
            {
                "title": "品牌训练输入策略",
                "description": f"{base_text}，基于 {len(assets)} 个素材和 {website_count} 个官网 URL 生成 {version}。",
            },
            {
                "title": "品牌视觉要素",
                "description": f"从 {source_text or '官网输入'} 中提炼品牌色彩、字体、图形语言与调性表达。",
            },
            {
                "title": "品牌语气与禁用项",
                "description": f"提示词重点沉淀 {focus_text}；输出须明确品牌口吻、风险项和不应出现的视觉偏差。",
            },
            {
                "title": "核心规则稳定性",
                "description": "Core Rule 作为品牌级约束，只允许补充说明，不直接被单次页面素材覆盖。",
            },
            {
                "title": "__visual_tokens__",
                "description": "可执行品牌视觉 Token，供生成阶段直接消费。",
                "tokens": visual_tokens,
            },
        ]
        new_layout_rules = [
            {
                "title": "官网视觉结构",
                "description": f"根据 {folder_text} 总结官网首屏、栏目节奏和品牌信息组织方式，但不固化为具体详情页模板。",
            },
            {
                "title": "品牌留白与栅格",
                "description": "沉淀品牌常用的留白密度、卡片间距、图文平衡和版心宽度偏好，供后续页面规则继承。",
            },
        ]
        new_components = [
            {
                "title": f"{brand_name} 品牌识别组件",
                "description": "包含品牌标题、辅助文案、色块、图形符号和 Logo 组合方式。",
            },
            {
                "title": "品牌语气检查项",
                "description": f"生成前确认文案与视觉是否覆盖 {focus_text}。",
            },
        ]
    else:
        layout_schema = _build_layout_schema_from_assets(assets, target_key)
        new_design_rules = [
            {
                "title": "详情页训练输入策略",
                "description": f"{base_text}，基于 {len(assets)} 个详情页素材沉淀商品详情页 Derived Rule。",
            },
            {
                "title": "文字层级规范",
                "description": "明确标题、副标题、正文、参数说明与 CTA 的字号层级、对齐方式和段落节奏。",
            },
            {
                "title": "图文协同约束",
                "description": f"优先从 {folder_text} 提取图片主次关系、卖点呈现顺序与图文占比。",
            },
            {
                "title": "页面转化检查项",
                "description": "详情页规则需兼顾视觉统一与转化表达，避免模块顺序混乱或信息密度失衡。",
            },
        ]
        new_layout_rules = [
            {
                "title": "页面模块顺序",
                "description": "先首屏主视觉，再卖点展开、参数说明、场景证明与结尾转化模块，形成稳定的信息流。",
            },
            {
                "title": "主图区域",
                "description": "主图区域应占据首屏核心视觉面积，文字与主体图保持清晰主次，避免遮挡关键商品信息。",
            },
            {
                "title": "卖点图区域",
                "description": "卖点图与说明文案成组出现，建议按 2-4 个分区排列，保持统一边距、图比和留白。",
            },
            {
                "title": "参数与对比区域",
                "description": "参数图、对比图和表格信息应集中在中后段模块，采用稳定栅格和重复模板减少阅读负担。",
            },
            {
                "title": "图片放置规则",
                "description": f"根据 {source_text or '详情页素材'} 确定横图、竖图、局部特写和场景图的推荐位置与裁切比例。",
            },
            {
                "title": "__layout_schema__",
                "description": "可执行详情页 Layout JSON Schema，包含 section、坐标、图片槽和文本层。",
                "schema": layout_schema,
            },
        ]
        if "详情页转化" in focuses:
            new_layout_rules.append(
                {"title": "转化模块", "description": "在首屏、功能说明和结尾区域保留明确 CTA 与购买理由。"}
            )
        new_components = [
            {
                "title": f"{brand_name} Hero 组件",
                "description": "适用于商品详情页首屏，包含主标题、副标题、卖点摘要与主视觉图片区域。",
            },
            {
                "title": "卖点卡片组件",
                "description": "用于功能点、参数点或场景点的重复模块，保持标题长度、图标样式和边距一致。",
            },
            {
                "title": "图文区块模板",
                "description": "规定左图右文、上文下图或双列对比等常用详情页图文版式。",
            },
            {
                "title": "__image_slots__",
                "description": "可执行图片槽定义，供素材匹配与裁切使用。",
                "slots": layout_schema.get("image_slots", []),
            },
        ]
    if any(focus == "禁用规则" for focus in focuses):
        new_design_rules.append(
            {
                "title": "禁用与风险控制",
                "description": "提示词包含禁用/避免类要求，输出前必须检查颜色、组件、文案是否触碰负向约束。",
            }
        )

    return {
        "design_rules": _merge_rule_lists(base_rule.design_rules if base_rule else None, new_design_rules),
        "layout_rules": _merge_rule_lists(base_rule.layout_rules if base_rule else None, new_layout_rules),
        "components": _merge_rule_lists(base_rule.components if base_rule else None, new_components),
        "source_assets": source_assets,
    }


def _latest_rule_for_target(
    session: Session,
    brand_id: int,
    training_target: str,
    status: str | None = None,
) -> BrandRule | None:
    stmt = select(BrandRule).where(
        BrandRule.brand_id == brand_id,
        *_target_filter_clauses(training_target),
    )
    if status:
        stmt = stmt.where(BrandRule.status == status)
    return session.execute(
        stmt.order_by(BrandRule.updated_at.desc(), BrandRule.id.desc()).limit(1)
    ).scalar_one_or_none()


def get_brand_rule_training_context(
    brand_id: int,
    asset_ids: list[int],
    base_version_id: int | None = None,
    training_target: str | None = None,
) -> dict[str, Any]:
    with session_scope() as session:
        if session is None:
            raise ValueError("database disabled")
        target_key = normalize_rule_target(training_target)
        brand = session.get(Brand, brand_id)
        if brand is None:
            raise ValueError("brand not found")
        base_rule = session.get(BrandRule, base_version_id) if base_version_id else None
        if base_rule is not None and base_rule.brand_id != brand_id:
            raise ValueError("base version does not belong to brand")
        if base_rule is not None and get_default_rule_target(base_rule) != target_key:
            raise ValueError("base version type does not match training target")
        linked_core_rule = _latest_rule_for_target(session, brand_id, RULE_TARGET_BRAND_CORE, status="active")
        if linked_core_rule is None:
            linked_core_rule = _latest_rule_for_target(session, brand_id, RULE_TARGET_BRAND_CORE)
        asset_query = select(BrandAsset).where(BrandAsset.brand_id == brand_id)
        if asset_ids:
            asset_query = asset_query.where(BrandAsset.id.in_(asset_ids))
        else:
            included_assets = list(
                session.execute(
                    asset_query.where(BrandAsset.include_in_training.is_(True))
                ).scalars()
            )
            assets = included_assets or list(
                session.execute(asset_query.order_by(BrandAsset.id.asc())).scalars()
            )
            return {
                "brand": {"id": brand.id, "name": brand.name, "status": brand.status},
                "trainingTarget": target_key,
                "targetMeta": get_rule_target_meta(target_key),
                "baseRule": {
                    "id": base_rule.id,
                    "version": base_rule.version,
                    "markdown": base_rule.markdown or "",
                    "designRules": base_rule.design_rules or [],
                    "layoutRules": base_rule.layout_rules or [],
                    "components": base_rule.components or [],
                    "targetKey": get_default_rule_target(base_rule),
                }
                if base_rule
                else None,
                "linkedCoreRule": {
                    "id": linked_core_rule.id,
                    "version": linked_core_rule.version,
                    "markdown": linked_core_rule.markdown or "",
                }
                if linked_core_rule
                else None,
                "assets": [
                    {
                        "id": asset.id,
                        "name": asset.name,
                        "folder": asset.folder,
                        "contentType": asset.content_type or "",
                        "source": asset.source or "",
                        "size": asset.size,
                        "savedPath": asset.saved_path or "",
                        "extractedText": asset.extracted_text or "",
                        "trainingRole": asset.training_role,
                        "includeInTraining": asset.include_in_training,
                        "qualityLevel": asset.quality_level,
                        "metadata": asset.metadata_json or {},
                    }
                    for asset in assets
                ],
            }
        assets = list(session.execute(asset_query).scalars())
        return {
            "brand": {"id": brand.id, "name": brand.name, "status": brand.status},
            "trainingTarget": target_key,
            "targetMeta": get_rule_target_meta(target_key),
            "baseRule": {
                "id": base_rule.id,
                "version": base_rule.version,
                "markdown": base_rule.markdown or "",
                "designRules": base_rule.design_rules or [],
                "layoutRules": base_rule.layout_rules or [],
                "components": base_rule.components or [],
                "targetKey": get_default_rule_target(base_rule),
            }
            if base_rule
            else None,
            "linkedCoreRule": {
                "id": linked_core_rule.id,
                "version": linked_core_rule.version,
                "markdown": linked_core_rule.markdown or "",
            }
            if linked_core_rule
            else None,
            "assets": [
                {
                    "id": asset.id,
                    "name": asset.name,
                    "folder": asset.folder,
                    "contentType": asset.content_type or "",
                    "source": asset.source or "",
                    "size": asset.size,
                    "savedPath": asset.saved_path or "",
                    "extractedText": asset.extracted_text or "",
                    "trainingRole": asset.training_role,
                    "includeInTraining": asset.include_in_training,
                    "qualityLevel": asset.quality_level,
                    "metadata": asset.metadata_json or {},
                }
                for asset in assets
            ],
        }


def _normalize_rule_items(value: Any, fallback: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return fallback
    items = []
    for item in value:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        description = str(item.get("description") or "").strip()
        if title or description:
            normalized = dict(item)
            normalized["title"] = title or "未命名规则"
            normalized["description"] = description
            items.append(normalized)
    return items or fallback


def _normalize_model_rule_content(
    model_result: dict[str, Any],
    fallback: dict[str, Any],
    target_key: str,
) -> dict[str, Any]:
    design_rules = _normalize_rule_items(model_result.get("design_rules"), fallback["design_rules"])
    layout_rules = _normalize_rule_items(model_result.get("layout_rules"), fallback["layout_rules"])
    components = _normalize_rule_items(model_result.get("components"), fallback["components"])

    visual_tokens = model_result.get("visual_tokens")
    if target_key == RULE_TARGET_BRAND_CORE and isinstance(visual_tokens, dict):
        design_rules.append(
            {
                "title": "__visual_tokens__",
                "description": "可执行品牌视觉 Token，供生成阶段直接消费。",
                "tokens": visual_tokens,
            }
        )

    layout_schema = model_result.get("layout_schema")
    if target_key == RULE_TARGET_DETAIL_PAGE_LAYOUT and isinstance(layout_schema, dict):
        layout_rules.append(
            {
                "title": "__layout_schema__",
                "description": "可执行详情页 Layout JSON Schema，包含 section、坐标、图片槽和文本层。",
                "schema": layout_schema,
            }
        )

    image_slots = model_result.get("image_slots")
    if target_key == RULE_TARGET_DETAIL_PAGE_LAYOUT and isinstance(image_slots, list):
        components.append(
            {
                "title": "__image_slots__",
                "description": "可执行图片槽定义，供素材匹配与裁切使用。",
                "slots": image_slots,
            }
        )
    if target_key == RULE_TARGET_BRAND_CORE and (
        isinstance(layout_schema, dict) or isinstance(image_slots, list)
    ):
        design_rules.append(
            {
                "title": "__ignored_page_schema__",
                "description": "模型在 Core Rule 中返回了页面 layout_schema/image_slots，已忽略；请使用“详情页布局规范”训练目标生成 Derived Rule。",
            }
        )

    return {
        "design_rules": design_rules,
        "layout_rules": layout_rules,
        "components": components,
        "source_assets": _normalize_rule_items(model_result.get("source_assets"), fallback["source_assets"]),
        "markdown": str(model_result.get("markdown") or "").strip(),
    }


def train_brand_rule_version(
    brand_id: int,
    asset_ids: list[int],
    prompt: str,
    website_urls: list[str],
    base_version_id: int | None = None,
    model_result: dict[str, Any] | None = None,
    training_target: str | None = None,
) -> dict[str, Any]:
    with session_scope() as session:
        if session is None:
            raise ValueError("database disabled")
        target_key = normalize_rule_target(training_target)
        target_meta = get_rule_target_meta(target_key)
        brand = session.get(Brand, brand_id)
        if brand is None:
            raise ValueError("brand not found")
        base_rule = session.get(BrandRule, base_version_id) if base_version_id else None
        if base_rule is not None and base_rule.brand_id != brand_id:
            raise ValueError("base version does not belong to brand")
        if base_rule is not None and get_default_rule_target(base_rule) != target_key:
            raise ValueError("base version type does not match training target")
        version_count = session.execute(
            select(func.count(BrandRule.id)).where(
                BrandRule.brand_id == brand_id,
                *_target_filter_clauses(target_key),
            )
        ).scalar_one()
        version = f"V1.{version_count + 4}"
        assets = list(
            session.execute(
                select(BrandAsset).where(
                    BrandAsset.brand_id == brand_id,
                    BrandAsset.id.in_(asset_ids),
                )
            ).scalars()
        )
        generated = _build_trained_rule_content(
            brand_name=brand.name,
            version=version,
            assets=assets,
            prompt=prompt,
            website_urls=website_urls,
            base_rule=base_rule,
            training_target=target_key,
        )
        if model_result:
            generated = _normalize_model_rule_content(model_result, generated, target_key)
        design_rules = generated["design_rules"]
        layout_rules = generated["layout_rules"]
        components = generated["components"]
        rule_quality = _score_rule_quality(target_key, design_rules, layout_rules, components)
        design_rules.append(
            {
                "title": "__rule_quality__",
                "description": "规则训练质量评分，用于判断是否适合发布和进入生成任务。",
                "score": rule_quality,
            }
        )
        if target_key == RULE_TARGET_BRAND_CORE:
            prompt_templates = [
                {
                    "title": "品牌核心规则提取模板",
                    "description": f"从 {len([url for url in website_urls if url])} 个官网 URL 与 {len(assets)} 个素材中提取品牌视觉规范与语气。",
                },
                {
                    "title": "品牌审核模板",
                    "description": "输出颜色、字体、图形语言与禁用项，供设计师审核后发布为 Core Rule。",
                },
                {
                    "title": "叠加训练模板",
                    "description": (
                        f"基于 {base_rule.version} 保留历史品牌规则并追加本次官网素材结论。"
                        if base_rule
                        else "不叠加历史版本，直接根据本次官网素材和提示词创建全新品牌核心规则。"
                    ),
                },
            ]
            parent_rule_id = None
        else:
            prompt_templates = [
                {
                    "title": "详情页布局提取模板",
                    "description": f"基于 {len(assets)} 个详情页素材提取模块顺序、图文排版和图片区域规则。",
                },
                {
                    "title": "详情页生成模板",
                    "description": "后续详情页生成必须同时消费品牌 Core Rule 与当前商品详情页 Derived Rule。",
                },
                {
                    "title": "叠加训练模板",
                    "description": (
                        f"基于 {base_rule.version} 保留历史详情页规则并追加本次素材结论。"
                        if base_rule
                        else "不叠加历史版本，直接根据本次详情页素材和提示词创建全新页面规则。"
                    ),
                },
            ]
            linked_core_rule = _latest_rule_for_target(session, brand_id, RULE_TARGET_BRAND_CORE, status="active")
            if linked_core_rule is None:
                linked_core_rule = _latest_rule_for_target(session, brand_id, RULE_TARGET_BRAND_CORE)
            parent_rule_id = linked_core_rule.id if linked_core_rule else None
        markdown = _default_rule_markdown(
            brand.name,
            version,
            design_rules,
            layout_rules,
            prompt_templates,
            website_urls,
            training_prompt=prompt,
            source_assets=generated["source_assets"],
            base_version=base_rule.version if base_rule else None,
            target_label=target_meta["label"],
            target_key=target_key,
        )
        if generated.get("markdown"):
            markdown = str(generated["markdown"])
        row = BrandRule(
            brand_id=brand_id,
            version=version,
            status="draft",
            rule_count=len(design_rules),
            layout_count=len(layout_rules),
            prompt_count=len(prompt_templates),
            design_rules=design_rules,
            layout_rules=layout_rules,
            components=components,
            prompt_templates=prompt_templates,
            markdown=markdown,
            training_prompt=prompt,
            source_asset_ids=asset_ids,
            website_urls=website_urls,
            base_version=base_rule.version if base_rule else None,
            rule_type=target_meta["rule_type"],
            page_type=target_meta["page_type"],
            source_kind=target_meta["source_kind"],
            parent_rule_id=parent_rule_id,
        )
        session.add(row)
        session.flush()
        return {
            "id": row.id,
            "version": row.version,
            "markdown": row.markdown,
            "targetKey": target_key,
        }


def update_brand_rule_markdown(rule_id: int, markdown: str) -> dict[str, Any]:
    with session_scope() as session:
        if session is None:
            raise ValueError("database disabled")
        rule = session.get(BrandRule, rule_id)
        if rule is None:
            raise ValueError("brand rule not found")
        rule.markdown = markdown
        rule.updated_at = datetime.utcnow()
        session.merge(rule)
        return {"id": rule.id, "version": rule.version, "markdown": rule.markdown}


def publish_brand_rule_version(rule_id: int) -> dict[str, Any]:
    with session_scope() as session:
        if session is None:
            raise ValueError("database disabled")
        rule = session.get(BrandRule, rule_id)
        if rule is None:
            raise ValueError("brand rule not found")
        target_key = get_default_rule_target(rule)
        active_rules = session.execute(
            select(BrandRule).where(
                BrandRule.brand_id == rule.brand_id,
                BrandRule.status == "active",
                BrandRule.id != rule.id,
                *_target_filter_clauses(target_key),
            )
        ).scalars()
        for item in active_rules:
            item.status = "archived"
            item.updated_at = datetime.utcnow()
        rule.status = "active"
        rule.updated_at = datetime.utcnow()
        session.merge(rule)
        return {"id": rule.id, "version": rule.version, "status": rule.status}


def rollback_brand_rule_version(rule_id: int) -> dict[str, Any]:
    with session_scope() as session:
        if session is None:
            raise ValueError("database disabled")
        target = session.get(BrandRule, rule_id)
        if target is None:
            raise ValueError("brand rule not found")
        target_key = get_default_rule_target(target)
        active_rules = session.execute(
            select(BrandRule).where(
                BrandRule.brand_id == target.brand_id,
                BrandRule.status == "active",
                BrandRule.id != target.id,
                *_target_filter_clauses(target_key),
            )
        ).scalars()
        for item in active_rules:
            item.status = "rolled_back"
            item.updated_at = datetime.utcnow()
        target.status = "active"
        target.updated_at = datetime.utcnow()
        session.merge(target)
        return {"id": target.id, "version": target.version, "status": target.status}


def diff_brand_rule_versions(base_rule_id: int, compare_rule_id: int) -> dict[str, Any]:
    with session_scope() as session:
        if session is None:
            raise ValueError("database disabled")
        base = session.get(BrandRule, base_rule_id)
        compare = session.get(BrandRule, compare_rule_id)
        if base is None or compare is None:
            raise ValueError("brand rule not found")
        if base.brand_id != compare.brand_id:
            raise ValueError("versions do not belong to the same brand")
        if get_default_rule_target(base) != get_default_rule_target(compare):
            raise ValueError("versions do not belong to the same rule target")

        def keyed(items: list[dict[str, Any]] | None) -> dict[str, str]:
            result: dict[str, str] = {}
            for item in items or []:
                title = str(item.get("title") or "").strip()
                if title:
                    result[title] = str(item.get("description") or "").strip()
            return result

        sections = {
            "designRules": (base.design_rules, compare.design_rules),
            "layoutRules": (base.layout_rules, compare.layout_rules),
            "components": (base.components, compare.components),
            "promptTemplates": (base.prompt_templates, compare.prompt_templates),
        }
        diff: dict[str, Any] = {}
        for section, (left_items, right_items) in sections.items():
            left = keyed(left_items)
            right = keyed(right_items)
            left_keys = set(left)
            right_keys = set(right)
            changed = [
                {"title": key, "from": left[key], "to": right[key]}
                for key in sorted(left_keys & right_keys)
                if left[key] != right[key]
            ]
            diff[section] = {
                "added": [{"title": key, "description": right[key]} for key in sorted(right_keys - left_keys)],
                "removed": [{"title": key, "description": left[key]} for key in sorted(left_keys - right_keys)],
                "changed": changed,
            }
        return {
            "base": {
                "id": base.id,
                "version": base.version,
                "status": base.status,
                "targetKey": get_default_rule_target(base),
            },
            "compare": {
                "id": compare.id,
                "version": compare.version,
                "status": compare.status,
                "targetKey": get_default_rule_target(compare),
            },
            "diff": diff,
        }


def record_design_feedback(
    run_id: str,
    feedback_type: str,
    author: str,
    changes: list[dict[str, Any]],
    notes: str,
) -> dict[str, Any]:
    with session_scope() as session:
        if session is None:
            raise ValueError("database disabled")
        run = session.get(WorkflowRun, run_id)
        if run is None:
            raise ValueError("workflow run not found")
        row = DesignFeedback(
            run_id=run_id,
            feedback_type=feedback_type.strip() or "designer_edit",
            author=author.strip() or "designer",
            changes=_jsonable(changes),
            notes=notes.strip(),
        )
        session.add(row)
        session.flush()
        return {
            "id": row.id,
            "runId": row.run_id,
            "feedbackType": row.feedback_type,
            "author": row.author,
            "changes": row.changes or [],
            "notes": row.notes,
            "createdAt": row.created_at.isoformat() if row.created_at else None,
        }


def list_design_feedback(run_id: str) -> dict[str, Any]:
    with session_scope() as session:
        if session is None:
            return {"items": []}
        rows = list(
            session.execute(
                select(DesignFeedback)
                .where(DesignFeedback.run_id == run_id)
                .order_by(DesignFeedback.created_at.desc(), DesignFeedback.id.desc())
            ).scalars()
        )
        return {
            "items": [
                {
                    "id": row.id,
                    "runId": row.run_id,
                    "feedbackType": row.feedback_type,
                    "author": row.author,
                    "changes": row.changes or [],
                    "notes": row.notes,
                    "createdAt": row.created_at.isoformat() if row.created_at else None,
                }
                for row in rows
            ]
        }


def _empty_feedback_constraints(scope: str, feedback_run_id: str | None = None) -> dict[str, Any]:
    return {
        "applied": False,
        "scope": scope,
        "feedback_run_id": feedback_run_id,
        "source_feedback_ids": [],
        "source_run_ids": [],
        "layout_constraints": [],
        "visual_constraints": [],
        "copy_constraints": [],
        "asset_constraints": [],
        "negative_constraints": [],
        "general_notes": [],
    }


def _split_feedback_notes(notes: str) -> list[str]:
    text = (
        notes.replace("\r", "\n")
        .replace("；", "\n")
        .replace(";", "\n")
        .replace("。", "\n")
    )
    items: list[str] = []
    for raw in text.splitlines():
        line = raw.strip(" -•·\t")
        if line:
            items.append(line)
    return items


def _classify_feedback_note(note: str) -> str:
    lowered = note.lower()
    if any(
        keyword in note
        for keyword in ("首屏", "模块", "布局", "排版", "顺序", "结构", "留白", "栅格", "对齐")
    ):
        return "layout"
    if any(
        keyword in note
        for keyword in ("图片", "主图", "场景", "素材", "模特", "抠图", "细节图", "特写")
    ):
        return "asset"
    if any(
        keyword in note
        for keyword in ("文案", "标题", "副标题", "正文", "要点", "措辞", "语气")
    ):
        return "copy"
    if any(
        keyword in note
        for keyword in ("颜色", "配色", "字体", "字号", "字重", "阴影", "质感", "饱和", "明度")
    ):
        return "visual"
    if any(keyword in lowered for keyword in ("avoid", "don't", "remove", "forbid")):
        return "negative"
    return "general"


def _push_feedback_constraint(bucket: dict[str, list[str]], key: str, value: str) -> None:
    text = value.strip()
    if not text:
        return
    current = bucket.setdefault(key, [])
    if text not in current:
        current.append(text)


def get_feedback_constraints_for_request(
    brand_name: str,
    product_name: str,
    feedback_scope: str = "same_product",
    feedback_run_id: str | None = None,
    limit: int = 6,
) -> dict[str, Any]:
    scope = (feedback_scope or "same_product").strip()
    if scope == "none":
        return _empty_feedback_constraints(scope, feedback_run_id)

    with session_scope() as session:
        if session is None:
            return _empty_feedback_constraints(scope, feedback_run_id)

        query = (
            select(DesignFeedback, WorkflowRun)
            .join(WorkflowRun, DesignFeedback.run_id == WorkflowRun.run_id)
            .order_by(DesignFeedback.created_at.desc(), DesignFeedback.id.desc())
        )
        if feedback_run_id:
            query = query.where(DesignFeedback.run_id == feedback_run_id)
        elif scope == "same_brand":
            query = query.where(WorkflowRun.brand_name == brand_name)
        else:
            query = query.where(
                WorkflowRun.brand_name == brand_name,
                WorkflowRun.product_name == product_name,
            )
        rows = list(session.execute(query.limit(max(1, limit))).all())
        if not rows:
            return _empty_feedback_constraints(scope, feedback_run_id)

        result = _empty_feedback_constraints(scope, feedback_run_id)
        buckets: dict[str, list[str]] = {
            "layout": [],
            "visual": [],
            "copy": [],
            "asset": [],
            "negative": [],
            "general": [],
        }
        for feedback, run in rows:
            result["source_feedback_ids"].append(feedback.id)
            if run.run_id not in result["source_run_ids"]:
                result["source_run_ids"].append(run.run_id)
            for item in _split_feedback_notes(feedback.notes or ""):
                bucket = _classify_feedback_note(item)
                _push_feedback_constraint(buckets, bucket, item)
            for change in feedback.changes or []:
                tracked = change.get("trackedChanges") or []
                if not isinstance(tracked, list):
                    continue
                for item in tracked:
                    text = str(item).strip()
                    if not text:
                        continue
                    bucket = _classify_feedback_note(text)
                    prefix = "优先修正：" if bucket != "general" else "关注点："
                    _push_feedback_constraint(buckets, bucket, f"{prefix}{text}")

        result["layout_constraints"] = buckets["layout"]
        result["visual_constraints"] = buckets["visual"]
        result["copy_constraints"] = buckets["copy"]
        result["asset_constraints"] = buckets["asset"]
        result["negative_constraints"] = buckets["negative"]
        result["general_notes"] = buckets["general"]
        result["applied"] = any(
            result[key]
            for key in (
                "layout_constraints",
                "visual_constraints",
                "copy_constraints",
                "asset_constraints",
                "negative_constraints",
                "general_notes",
            )
        )
        return result


def delete_brand_rule_version(rule_id: int) -> dict[str, Any]:
    with session_scope() as session:
        if session is None:
            raise ValueError("database disabled")
        rule = session.get(BrandRule, rule_id)
        if rule is None:
            raise ValueError("brand rule not found")
        child_rules = session.execute(
            select(BrandRule).where(BrandRule.parent_rule_id == rule.id)
        ).scalars()
        for item in child_rules:
            item.parent_rule_id = None
            item.updated_at = datetime.utcnow()
        result = {"id": rule.id, "brandId": rule.brand_id, "version": rule.version}
        session.delete(rule)
        return result


def get_brand_rule_options_data() -> dict[str, Any] | None:
    with session_scope() as session:
        if session is None:
            return None
        rows = session.execute(
            select(BrandRule, Brand)
            .join(Brand, BrandRule.brand_id == Brand.id)
            .order_by(Brand.name.asc(), BrandRule.updated_at.desc(), BrandRule.id.desc())
        ).all()
        rules = []
        core_rules = []
        detail_page_rules = []
        for rule, brand in rows:
            target_key = get_default_rule_target(rule)
            target_meta = get_rule_target_meta(target_key)
            markdown = rule.markdown or _default_rule_markdown(
                brand.name,
                rule.version,
                rule.design_rules or [],
                rule.layout_rules or [],
                rule.prompt_templates or [],
                rule.website_urls or [],
                target_label=target_meta["label"],
                target_key=target_key,
            )
            item = {
                "id": rule.id,
                "brandId": brand.id,
                "brandName": brand.name,
                "version": rule.version,
                "status": rule.status,
                "ruleCount": rule.rule_count,
                "markdown": markdown,
                "updatedAt": rule.updated_at.isoformat() if rule.updated_at else None,
                "targetKey": target_key,
                "targetLabel": target_meta["label"],
                "ruleType": rule.rule_type or target_meta["rule_type"],
                "pageType": rule.page_type or target_meta["page_type"],
                "sourceKind": rule.source_kind or target_meta["source_kind"],
                "label": f"{brand.name} / {target_meta['label']} / {rule.version} / {rule.status}",
            }
            rules.append(item)
            if target_key == RULE_TARGET_BRAND_CORE:
                core_rules.append(item)
            elif target_key == RULE_TARGET_DETAIL_PAGE_LAYOUT:
                detail_page_rules.append(item)
        return {
            "rules": rules,
            "coreRules": core_rules,
            "detailPageRules": detail_page_rules,
        }


def get_products_data() -> dict[str, Any] | None:
    with session_scope() as session:
        if session is None:
            return None
        page = _setting(session, "products_page", {})
        products = list(session.execute(select(Product).order_by(Product.updated_at.desc())).scalars())
        if not products:
            return {
                "page": page,
                "products": [],
                "selectedProduct": None,
                "emptyState": "当前还没有商品数据，请先创建商品或导入商品资料。",
            }
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
            "emptyState": "",
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
                    "runId": item.run_id,
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
    {"id": "image_generation", "title": "图片生成 Agent", "icon": "image"},
    {"id": "layout_engine", "title": "Layout Engine", "icon": "grid"},
    {"id": "copy", "title": "文案 Agent", "icon": "type"},
    {"id": "figma_psd", "title": "Figma / PSD 生成 Agent", "icon": "file-image"},
    {"id": "design_score", "title": "Design Score", "icon": "check-circle"},
    {"id": "output_review", "title": "输出、审核与反馈", "icon": "check-circle"},
]

DEFAULT_BRAND_RULE_PROMPTS: dict[str, str] = {
    RULE_TARGET_BRAND_CORE: (
        "你是 BrandOS 的品牌设计规范训练 Agent。请基于官网素材、品牌资产和历史品牌规则版本，"
        "提取品牌视觉规范、字体色彩、品牌语气、禁用项与稳定的品牌级布局倾向。输出 Markdown，"
        "要求可读、可审阅、可被设计师手动修改。"
    ),
    RULE_TARGET_DETAIL_PAGE_LAYOUT: (
        "你是 BrandOS 的详情页布局规则训练 Agent。请基于商品详情页素材、历史详情页规则和关联品牌规范，"
        "提取页面模块顺序、文字排版层级、图片放置区域、比例、留白与图文协同约束。输出 Markdown，"
        "要求可直接用于后续商品详情页生成。"
    ),
}


DEFAULT_BRAND_RULE_PROMPT = DEFAULT_BRAND_RULE_PROMPTS[RULE_TARGET_BRAND_CORE]


def default_training_prompt(training_target: str | None) -> str:
    return DEFAULT_BRAND_RULE_PROMPTS[normalize_rule_target(training_target)]


def _default_rule_markdown(
    brand_name: str,
    version: str,
    design_rules: list[dict[str, Any]],
    layout_rules: list[dict[str, Any]],
    prompt_templates: list[dict[str, Any]],
    website_urls: list[str] | None = None,
    training_prompt: str | None = None,
    source_assets: list[dict[str, str]] | None = None,
    base_version: str | None = None,
    target_label: str | None = None,
    target_key: str | None = None,
) -> str:
    title_label = target_label or "品牌规则"
    lines = [
        f"# {brand_name} {title_label} {version}",
        "",
        "## 训练输入",
        f"- 规则目标：{title_label}",
        f"- 目标编码：{normalize_rule_target(target_key)}",
        f"- 叠加版本：{base_version or '不叠加，创建全新规则'}",
    ]
    if training_prompt:
        lines.append(f"- 训练提示词：{_clip(training_prompt, 500)}")
    if source_assets:
        lines.extend(["", "## 所选素材摘要"])
        for item in source_assets:
            lines.append(f"- **{item.get('title', '')}**：{item.get('description', '')}")
    lines.extend(["", "## 设计规则说明"])
    for item in design_rules:
        lines.append(f"- **{item.get('title', '')}**：{item.get('description', '')}")
    lines.extend(["", "## 布局规则摘要"])
    for item in layout_rules:
        lines.append(f"- **{item.get('title', '')}**：{item.get('description', '')}")
    lines.extend(["", "## Prompt 模板摘要"])
    for item in prompt_templates:
        lines.append(f"- **{item.get('title', '')}**：{item.get('description', '')}")
    if website_urls:
        lines.extend(["", "## 官网来源"])
        lines.extend(f"- {url}" for url in website_urls if url)
    return "\n".join(lines)


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
            design_rules = [
                {"title": "品牌调性", "description": "简洁、克制、带有科技家居感，强调自然光感与空间呼吸感。"},
                {"title": "主色体系", "description": "主色以深蓝与暖白为核心，辅助色使用低饱和浅灰与淡金。"},
                {"title": "字体规则", "description": "标题偏中黑，正文偏常规，强调信息层级与留白节奏。"},
                {"title": "文案风格", "description": "标题短句、卖点拆分清晰，功能信息与场景利益点并行表达。"},
            ]
            layout_rules = [
                {"title": "Hero 模块", "description": "左文案右大图，首屏突出核心卖点与场景视觉。"},
                {"title": "Feature 模块", "description": "三列卡片结构，统一图文比例，适合功能点平铺表达。"},
                {"title": "Parameter 模块", "description": "参数表横向排布，支持图标化表达和重点参数高亮。"},
            ]
            components = [
                {"title": "标题区组件", "description": "支持品牌标题、副标题与简短卖点组合。"},
                {"title": "卖点区组件", "description": "适合 3 到 4 个卖点并列展示。"},
                {"title": "CTA 组件", "description": "强调行动按钮、利益点和促销信息的组合。"},
            ]
            prompt_templates = [
                {"title": "详情页生成模板", "description": "适用于新品首发和常规详情页，默认输出 Hero / Feature / Scenario / CTA。"},
                {"title": "场景图生成模板", "description": "强调家居氛围、自然光环境、产品主角突出、减少过度商业感。"},
                {"title": "模块重生成模板", "description": "在保留品牌语言的前提下，对单个模块进行局部变体生成。"},
            ]
            session.add(
                BrandRule(
                    brand_id=aurora.id,
                    version="V1.4",
                    status="active",
                    rule_count=42,
                    layout_count=12,
                    prompt_count=18,
                    design_rules=design_rules,
                    layout_rules=layout_rules,
                    components=components,
                    prompt_templates=prompt_templates,
                    markdown=_default_rule_markdown(
                        aurora.name,
                        "V1.4",
                        design_rules,
                        layout_rules,
                        prompt_templates,
                        target_label=get_rule_target_meta(RULE_TARGET_BRAND_CORE)["label"],
                        target_key=RULE_TARGET_BRAND_CORE,
                    ),
                    training_prompt=default_training_prompt(RULE_TARGET_BRAND_CORE),
                    source_asset_ids=[],
                    website_urls=[],
                    rule_type=RULE_TYPE_CORE,
                    page_type=PAGE_TYPE_BRAND_IDENTITY,
                    source_kind=SOURCE_KIND_WEBSITE,
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
