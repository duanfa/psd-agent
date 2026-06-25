export type WorkflowMode = "smart_recommend" | "strict_brand";
export type OutputType = "detail_page" | "main_image" | "banner";

export interface ModelConfig {
  provider: string;
  model: string;
  vision_model: string;
  api_key?: string;
  base_url?: string;
  temperature: number;
  max_tokens: number;
  enable_deepagents: boolean;
  enable_vision: boolean;
  max_vision_images: number;
}

export interface TypographyConfig {
  title_font: string;
  subtitle_font: string;
  body_font: string;
  english_font: string;
  title_size: number;
  subtitle_size: number;
  body_size: number;
  line_height: number;
  letter_spacing: number;
  font_weight: "Regular" | "Medium" | "Bold";
  text_color: string;
  lock_brand_typography: boolean;
}

export interface LayoutConfig {
  canvas_width: number;
  module_count: number;
  hero_height: number;
  module_height: number;
  visual_style: string;
  background_color: string;
  accent_color: string;
  image_ratio: number;
  spacing_scale: number;
}

export interface AgentPrompts {
  system_prompt: string;
  vision_agent_prompt: string;
  structured_agent_prompt: string;
  brand_rag_agent_prompt: string;
  design_agent_prompt: string;
  layout_agent_prompt: string;
  copy_agent_prompt: string;
  psd_agent_prompt: string;
}

export interface WorkflowPayload {
  project_name: string;
  brand_name: string;
  product_name: string;
  product_brief: string;
  brand_guidelines: string;
  reference_notes: string;
  workflow_mode: WorkflowMode;
  output_types: OutputType[];
  model_config: ModelConfig;
  typography: TypographyConfig;
  layout: LayoutConfig;
  prompts: AgentPrompts;
}

export type StageStatus = "completed" | "fallback" | "skipped" | "failed";

export interface StageResult {
  id: string;
  title: string;
  icon: string;
  status: StageStatus;
  summary: string;
  detail: string;
  data: Record<string, unknown>;
  used_model: boolean;
  elapsed_ms: number;
}

export interface StageMeta {
  id: string;
  title: string;
  icon: string;
}

export interface WorkflowResult {
  run_id: string;
  status: "completed" | "fallback_completed" | "failed";
  summary: string;
  used_deepagents: boolean;
  stages: StageResult[];
  agent_report: string;
  design_spec: Record<string, unknown>;
  artifacts: {
    run_id: string;
    output_dir: string;
    preview_svg: string;
    design_spec: string;
    photoshop_jsx: string;
    readme: string;
  };
  assets: Array<{
    name: string;
    content_type?: string;
    size: number;
    saved_path?: string;
    extracted_text?: string;
    bucket: string;
  }>;
  warnings: string[];
}

export interface DefaultsResponse {
  payload: WorkflowPayload;
  prompts: AgentPrompts;
  workflowModes: WorkflowMode[];
  outputTypes: OutputType[];
  stages: StageMeta[];
}

export const API_BASE =
  process.env.NEXT_PUBLIC_PSD_AGENT_API_BASE ?? "http://localhost:8000";

export async function fetchDefaults(): Promise<DefaultsResponse> {
  const response = await fetch(`${API_BASE}/api/config/defaults`);
  if (!response.ok) {
    throw new Error(`默认配置加载失败：${response.status}`);
  }
  return response.json();
}

export async function generateWorkflow(
  payload: WorkflowPayload,
  files: File[],
): Promise<WorkflowResult> {
  const formData = new FormData();
  formData.append("payload", JSON.stringify(payload));
  files.forEach((file) => formData.append("files", file));

  const response = await fetch(`${API_BASE}/api/workflows/generate`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `生成失败：${response.status}`);
  }

  return response.json();
}

export function artifactUrl(runId: string, name: string): string {
  return `${API_BASE}/api/workflows/${runId}/artifacts/${name}`;
}
