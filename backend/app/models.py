from __future__ import annotations

from enum import Enum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel as PydanticBaseModel
from pydantic import ConfigDict, Field


class BaseModel(PydanticBaseModel):
    @classmethod
    def model_validate(cls, obj: Any):
        if hasattr(super(), "model_validate"):
            return super().model_validate(obj)
        return cls.parse_obj(obj)

    def model_dump(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        if hasattr(super(), "model_dump"):
            return super().model_dump(*args, **kwargs)
        return self.dict(*args, **kwargs)

    def model_dump_json(self, *args: Any, **kwargs: Any) -> str:
        if hasattr(super(), "model_dump_json"):
            return super().model_dump_json(*args, **kwargs)
        return self.json(*args, **kwargs)


def utc_now_iso() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def generate_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


class WorkflowMode(str, Enum):
    strict_brand = "strict_brand"
    smart_recommend = "smart_recommend"


class OutputType(str, Enum):
    detail_page = "detail_page"
    figma_page = "figma_page"
    psd_file = "psd_file"
    main_image = "main_image"
    banner = "banner"


class AssetRole(str, Enum):
    core_spec = "core_spec"
    high_quality_case = "high_quality_case"
    reference = "reference"
    excluded = "excluded"


class AssetTrainingStatus(str, Enum):
    candidate = "candidate"
    approved_for_training = "approved_for_training"
    excluded = "excluded"


class RuleVersionStatus(str, Enum):
    draft = "draft"
    pending_publish = "pending_publish"
    published = "published"
    rolled_back = "rolled_back"


class AuditEntityType(str, Enum):
    brand = "brand"
    asset = "asset"
    rule_version = "rule_version"
    workflow_run = "workflow_run"


class ModelConfig(BaseModel):
    provider: str = Field(default="openai", description="LangChain 模型 provider")
    model: str = Field(default="qwen-plus", description="文本模型名称")
    vision_model: str = Field(default="qwen-vl-max", description="多模态视觉模型名称")
    api_key: str | None = Field(default=None, description="可选，优先于环境变量")
    base_url: str | None = Field(default=None, description="OpenAI compatible base url")
    temperature: float = Field(default=0.4, ge=0, le=2)
    max_tokens: int = Field(default=4096, ge=512, le=32000)
    enable_deepagents: bool = Field(default=True)
    enable_vision: bool = Field(default=True, description="是否用多模态模型真正读取图片")
    max_vision_images: int = Field(default=4, ge=1, le=12)


class TypographyConfig(BaseModel):
    title_font: str = "方正兰亭特黑简体"
    subtitle_font: str = "方正兰亭黑简体"
    body_font: str = "方正兰亭黑简体"
    english_font: str = "AKR Sans"
    title_size: int = Field(default=28, ge=12, le=160)
    subtitle_size: int = Field(default=18, ge=10, le=96)
    body_size: int = Field(default=10, ge=8, le=64)
    line_height: float = Field(default=1.5, ge=0.8, le=3)
    letter_spacing: float = Field(default=0, ge=-5, le=20)
    font_weight: Literal["Regular", "Medium", "Bold"] = "Medium"
    text_color: str = "#1f2937"
    lock_brand_typography: bool = True


class LayoutConfig(BaseModel):
    canvas_width: int = Field(default=790, ge=320, le=3000)
    module_count: int = Field(default=6, ge=1, le=12)
    hero_height: int = Field(default=1000, ge=400, le=2400)
    module_height: int = Field(default=820, ge=300, le=1800)
    visual_style: str = "简洁商务 / 浅色质感 / 接近参考图"
    background_color: str = "#eef1f4"
    accent_color: str = "#1f2937"
    image_ratio: float = Field(default=0.62, ge=0.2, le=0.9)
    spacing_scale: float = Field(default=1.0, ge=0.5, le=2.0)


class AgentPrompts(BaseModel):
    """对应图一中各 Agent 的可调提示词。"""

    system_prompt: str
    vision_agent_prompt: str
    structured_agent_prompt: str
    brand_rag_agent_prompt: str
    design_agent_prompt: str
    layout_agent_prompt: str
    copy_agent_prompt: str
    psd_agent_prompt: str


class RecordBase(BaseModel):
    id: str
    created_at: str = Field(default_factory=utc_now_iso)
    updated_at: str = Field(default_factory=utc_now_iso)


class BrandRecord(RecordBase):
    name: str
    code: str | None = None
    description: str = ""
    status: Literal["active", "archived"] = "active"
    owner: str = "local-admin"
    members: list[str] = Field(default_factory=list)
    current_rule_version_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class BrandAssetRecord(RecordBase):
    brand_id: str
    name: str
    content_type: str | None = None
    size: int = 0
    bucket: str = "reference"
    role: AssetRole = AssetRole.reference
    training_status: AssetTrainingStatus = AssetTrainingStatus.candidate
    path: str = ""
    enabled: bool = True
    source: Literal["upload", "workflow_input", "seed"] = "upload"
    notes: str = ""
    tags: list[str] = Field(default_factory=list)


class BrandRuleVersionRecord(RecordBase):
    brand_id: str
    version_number: int
    version_label: str
    status: RuleVersionStatus = RuleVersionStatus.draft
    summary: str = ""
    change_reason: str = ""
    source_asset_ids: list[str] = Field(default_factory=list)
    brand_profile: dict[str, Any] = Field(default_factory=dict)
    prompt_overrides: dict[str, Any] = Field(default_factory=dict)
    diff_summary: dict[str, Any] = Field(default_factory=dict)
    drift_risks: list[str] = Field(default_factory=list)
    published_at: str | None = None
    rolled_back_from_version_id: str | None = None


class RunArtifactRefs(BaseModel):
    output_dir: str | None = None
    preview_svg: str | None = None
    design_spec: str | None = None
    photoshop_jsx: str | None = None
    readme: str | None = None


class WorkflowRunRecord(RecordBase):
    brand_id: str | None = None
    rule_version_id: str | None = None
    project_name: str = ""
    product_name: str = ""
    status: str = "queued"
    workflow_mode: str | None = None
    output_types: list[str] = Field(default_factory=list)
    input_payload: dict[str, Any] = Field(default_factory=dict)
    referenced_asset_ids: list[str] = Field(default_factory=list)
    asset_names: list[str] = Field(default_factory=list)
    run_started_at: str | None = None
    run_finished_at: str | None = None
    current_stage: str | None = None
    current_stage_title: str | None = None
    current_stage_icon: str | None = None
    warnings: list[str] = Field(default_factory=list)
    artifacts: RunArtifactRefs = Field(default_factory=RunArtifactRefs)
    stage_results: list[dict[str, Any]] = Field(default_factory=list)
    logs: list[str] = Field(default_factory=list)


class AuditEventRecord(RecordBase):
    brand_id: str | None = None
    entity_type: AuditEntityType
    entity_id: str
    action: str
    message: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)


class BrandTrainingRequest(BaseModel):
    summary: str = ""
    change_reason: str = ""
    asset_ids: list[str] = Field(default_factory=list)


class BrandCreateRequest(BaseModel):
    name: str
    code: str | None = None
    description: str = ""


class BrandUpdateRequest(BaseModel):
    name: str | None = None
    code: str | None = None
    description: str | None = None
    status: Literal["active", "archived"] | None = None


class AssetUpdateRequest(BaseModel):
    role: AssetRole | None = None
    training_status: AssetTrainingStatus | None = None
    enabled: bool | None = None
    notes: str | None = None
    tags: list[str] | None = None


class RuleVersionUpdateRequest(BaseModel):
    summary: str | None = None
    change_reason: str | None = None
    status: RuleVersionStatus | None = None


class RuleVersionDiffResponse(BaseModel):
    current_version_id: str | None = None
    target_version_id: str
    diff: dict[str, Any] = Field(default_factory=dict)


class WorkflowRequest(BaseModel):
    project_name: str = "详情页自动生成"
    brand_name: str = "ANKORAU × ANAR FC"
    brand_id: str | None = None
    rule_version_id: str | None = None
    product_name: str = "电脑包"
    product_brief: str = ""
    brand_guidelines: str = ""
    reference_notes: str = ""
    workflow_mode: WorkflowMode = WorkflowMode.smart_recommend
    output_types: list[OutputType] = Field(
        default_factory=lambda: [OutputType.detail_page]
    )
    model_settings: ModelConfig = Field(
        default_factory=ModelConfig,
        alias="model_config",
    )
    typography: TypographyConfig = Field(default_factory=TypographyConfig)
    layout: LayoutConfig = Field(default_factory=LayoutConfig)
    prompts: AgentPrompts

    model_config = ConfigDict(populate_by_name=True)


class UploadedAsset(BaseModel):
    name: str
    content_type: str | None = None
    size: int = 0
    saved_path: str | None = None
    extracted_text: str | None = None
    bucket: str = "reference"


StageStatus = Literal["completed", "fallback", "skipped", "failed"]


class StageResult(BaseModel):
    """图一中每个节点对应的一次执行结果。"""

    id: str
    title: str
    icon: str = "sparkles"
    status: StageStatus
    summary: str = ""
    detail: str = ""
    data: dict[str, Any] = Field(default_factory=dict)
    used_model: bool = False
    elapsed_ms: int = 0


class WorkflowArtifacts(BaseModel):
    run_id: str
    output_dir: str
    preview_svg: str
    design_spec: str
    photoshop_jsx: str
    readme: str


class WorkflowResult(BaseModel):
    run_id: str
    status: Literal["completed", "fallback_completed", "failed"]
    brand_id: str | None = None
    rule_version_id: str | None = None
    summary: str
    used_deepagents: bool
    stages: list[StageResult]
    agent_report: str
    design_spec: dict[str, Any]
    artifacts: WorkflowArtifacts
    assets: list[UploadedAsset]
    warnings: list[str] = Field(default_factory=list)
    run_started_at: str | None = None
    run_finished_at: str | None = None
    referenced_asset_ids: list[str] = Field(default_factory=list)
