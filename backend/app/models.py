from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel as PydanticBaseModel
from pydantic import Field


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


class WorkflowMode(str, Enum):
    strict_brand = "strict_brand"
    smart_recommend = "smart_recommend"


class OutputType(str, Enum):
    detail_page = "detail_page"
    figma_page = "figma_page"
    psd_file = "psd_file"
    main_image = "main_image"
    banner = "banner"


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


class RequirementConstraints(BaseModel):
    preferred_module_order: list[str] = Field(default_factory=list)
    required_modules: list[str] = Field(default_factory=list)
    forbidden_modules: list[str] = Field(default_factory=list)
    layout_constraints: list[str] = Field(default_factory=list)
    visual_constraints: list[str] = Field(default_factory=list)
    copy_constraints: list[str] = Field(default_factory=list)
    asset_constraints: list[str] = Field(default_factory=list)
    negative_constraints: list[str] = Field(default_factory=list)
    reference_alignment: str = ""
    apply_feedback_constraints: bool = True
    feedback_scope: Literal["none", "same_product", "same_brand", "run"] = "same_product"
    feedback_run_id: str | None = None


class WorkflowRequest(BaseModel):
    project_name: str = "详情页自动生成"
    brand_name: str = "ANKORAU × ANAR FC"
    product_name: str = "电脑包"
    product_brief: str = ""
    brand_guidelines: str = ""
    reference_notes: str = ""
    selected_core_rule_id: int | None = None
    selected_detail_page_rule_id: int | None = None
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
    requirement_constraints: RequirementConstraints = Field(
        default_factory=RequirementConstraints
    )
    prompts: AgentPrompts

    class Config:
        allow_population_by_field_name = True


class UploadedAsset(BaseModel):
    name: str
    content_type: str | None = None
    size: int = 0
    saved_path: str | None = None
    extracted_text: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
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
    figma_plugin: str
    figma_url: str | None = None
    export_status: str | None = None
    export_mode: str | None = None
    export_error: str | None = None
    editable_html: str
    readme: str


class WorkflowResult(BaseModel):
    run_id: str
    status: Literal["completed", "fallback_completed", "failed"]
    summary: str
    used_deepagents: bool
    stages: list[StageResult]
    agent_report: str
    design_spec: dict[str, Any]
    artifacts: WorkflowArtifacts
    assets: list[UploadedAsset]
    warnings: list[str] = Field(default_factory=list)
