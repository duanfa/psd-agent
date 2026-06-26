export type WorkflowMode = "smart_recommend" | "strict_brand";
export type OutputType =
  | "detail_page"
  | "figma_page"
  | "psd_file"
  | "main_image"
  | "banner";

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
  brand_id?: string;
  rule_version_id?: string;
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

export type StageStatus =
  | "completed"
  | "fallback"
  | "skipped"
  | "failed"
  | "running";

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

export interface WorkflowLogsResponse {
  run_id: string;
  status: string;
  current_stage?: string | null;
  logs: string[];
  stages: StageResult[];
}

export interface BrandRecord {
  id: string;
  name: string;
  code?: string | null;
  description: string;
  status: "active" | "archived";
  owner: string;
  members: string[];
  current_rule_version_id?: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface BrandAssetRecord {
  id: string;
  brand_id: string;
  name: string;
  content_type?: string | null;
  size: number;
  bucket: string;
  role: "core_spec" | "high_quality_case" | "reference" | "excluded";
  training_status: "candidate" | "approved_for_training" | "excluded";
  path: string;
  enabled: boolean;
  source: "upload" | "workflow_input" | "seed";
  notes: string;
  tags: string[];
  created_at: string;
  updated_at: string;
}

export interface BrandRuleVersionRecord {
  id: string;
  brand_id: string;
  version_number: number;
  version_label: string;
  status: "draft" | "pending_publish" | "published" | "rolled_back";
  summary: string;
  change_reason: string;
  source_asset_ids: string[];
  brand_profile: Record<string, unknown>;
  prompt_overrides: Record<string, unknown>;
  diff_summary: Record<string, unknown>;
  drift_risks: string[];
  published_at?: string | null;
  rolled_back_from_version_id?: string | null;
  created_at: string;
  updated_at: string;
}

export interface AuditEventRecord {
  id: string;
  brand_id?: string | null;
  entity_type: "brand" | "asset" | "rule_version" | "workflow_run";
  entity_id: string;
  action: string;
  message: string;
  payload: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface WorkflowRunRecord {
  id: string;
  brand_id?: string | null;
  rule_version_id?: string | null;
  project_name: string;
  product_name: string;
  status: string;
  workflow_mode?: string | null;
  output_types: string[];
  input_payload: Record<string, unknown>;
  referenced_asset_ids: string[];
  asset_names: string[];
  run_started_at?: string | null;
  run_finished_at?: string | null;
  current_stage?: string | null;
  current_stage_title?: string | null;
  current_stage_icon?: string | null;
  warnings: string[];
  artifacts: {
    output_dir?: string | null;
    preview_svg?: string | null;
    design_spec?: string | null;
    photoshop_jsx?: string | null;
    readme?: string | null;
  };
  stage_results: StageResult[];
  logs: string[];
  created_at: string;
  updated_at: string;
}

export interface RuleVersionDiffResponse {
  current_version_id?: string | null;
  target_version_id: string;
  diff: Record<string, unknown>;
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

async function parseJsonOrThrow<T>(
  response: Response,
  fallbackMessage: string,
): Promise<T> {
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || fallbackMessage);
  }
  return response.json() as Promise<T>;
}

export async function fetchBrands(): Promise<BrandRecord[]> {
  const response = await fetch(`${API_BASE}/api/brands`);
  const data = await parseJsonOrThrow<{ items: BrandRecord[] }>(
    response,
    "品牌列表加载失败",
  );
  return data.items;
}

export async function createBrand(payload: {
  name: string;
  code?: string;
  description?: string;
}): Promise<BrandRecord> {
  const response = await fetch(`${API_BASE}/api/brands`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await parseJsonOrThrow<{ item: BrandRecord }>(
    response,
    "品牌创建失败",
  );
  return data.item;
}

export async function fetchBrandDetails(brandId: string): Promise<{
  item: BrandRecord;
  current_rule_version?: BrandRuleVersionRecord | null;
}> {
  const response = await fetch(`${API_BASE}/api/brands/${brandId}`);
  return parseJsonOrThrow(response, "品牌详情加载失败");
}

export async function fetchBrandAuditEvents(
  brandId: string,
): Promise<AuditEventRecord[]> {
  const response = await fetch(
    `${API_BASE}/api/brands/${brandId}/audit-events`,
  );
  const data = await parseJsonOrThrow<{ items: AuditEventRecord[] }>(
    response,
    "审计日志加载失败",
  );
  return data.items;
}

export async function fetchAssets(
  brandId: string,
): Promise<BrandAssetRecord[]> {
  const response = await fetch(
    `${API_BASE}/api/assets?brand_id=${encodeURIComponent(brandId)}`,
  );
  const data = await parseJsonOrThrow<{ items: BrandAssetRecord[] }>(
    response,
    "资产列表加载失败",
  );
  return data.items;
}

export async function uploadAsset(input: {
  brandId: string;
  role: BrandAssetRecord["role"];
  trainingStatus: BrandAssetRecord["training_status"];
  notes?: string;
  tags?: string;
  file: File;
}): Promise<BrandAssetRecord> {
  const formData = new FormData();
  formData.append("brand_id", input.brandId);
  formData.append("role", input.role);
  formData.append("training_status", input.trainingStatus);
  formData.append("notes", input.notes ?? "");
  formData.append("tags", input.tags ?? "");
  formData.append("file", input.file);
  const response = await fetch(`${API_BASE}/api/assets`, {
    method: "POST",
    body: formData,
  });
  const data = await parseJsonOrThrow<{ item: BrandAssetRecord }>(
    response,
    "资产上传失败",
  );
  return data.item;
}

export async function updateAsset(
  assetId: string,
  payload: Partial<BrandAssetRecord>,
): Promise<BrandAssetRecord> {
  const response = await fetch(`${API_BASE}/api/assets/${assetId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await parseJsonOrThrow<{ item: BrandAssetRecord }>(
    response,
    "资产更新失败",
  );
  return data.item;
}

export async function fetchRuleVersions(
  brandId: string,
): Promise<BrandRuleVersionRecord[]> {
  const response = await fetch(
    `${API_BASE}/api/rule-versions?brand_id=${encodeURIComponent(brandId)}`,
  );
  const data = await parseJsonOrThrow<{ items: BrandRuleVersionRecord[] }>(
    response,
    "规则版本列表加载失败",
  );
  return data.items;
}

export async function trainRuleVersion(input: {
  brandId: string;
  summary?: string;
  changeReason?: string;
  assetIds?: string[];
}): Promise<BrandRuleVersionRecord> {
  const response = await fetch(
    `${API_BASE}/api/brands/${input.brandId}/train`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        summary: input.summary ?? "",
        change_reason: input.changeReason ?? "",
        asset_ids: input.assetIds ?? [],
      }),
    },
  );
  const data = await parseJsonOrThrow<{ item: BrandRuleVersionRecord }>(
    response,
    "训练规则版本失败",
  );
  return data.item;
}

export async function fetchRuleVersionDiff(
  versionId: string,
): Promise<RuleVersionDiffResponse> {
  const response = await fetch(
    `${API_BASE}/api/rule-versions/${versionId}/diff`,
  );
  return parseJsonOrThrow(response, "规则版本差异加载失败");
}

export async function publishRuleVersion(
  versionId: string,
): Promise<BrandRuleVersionRecord> {
  const response = await fetch(
    `${API_BASE}/api/rule-versions/${versionId}/publish`,
    {
      method: "POST",
    },
  );
  const data = await parseJsonOrThrow<{ item: BrandRuleVersionRecord }>(
    response,
    "发布规则版本失败",
  );
  return data.item;
}

export async function rollbackRuleVersion(
  versionId: string,
): Promise<BrandRuleVersionRecord> {
  const response = await fetch(
    `${API_BASE}/api/rule-versions/${versionId}/rollback`,
    {
      method: "POST",
    },
  );
  const data = await parseJsonOrThrow<{ item: BrandRuleVersionRecord }>(
    response,
    "回滚规则版本失败",
  );
  return data.item;
}

export async function deleteRuleVersion(
  versionId: string,
): Promise<BrandRuleVersionRecord> {
  const response = await fetch(
    `${API_BASE}/api/rule-versions/${versionId}`,
    {
      method: "DELETE",
    },
  );
  const data = await parseJsonOrThrow<{ item: BrandRuleVersionRecord }>(
    response,
    "删除规则版本失败",
  );
  return data.item;
}

export async function fetchRuns(
  brandId?: string,
): Promise<WorkflowRunRecord[]> {
  const url = brandId
    ? `${API_BASE}/api/runs?brand_id=${encodeURIComponent(brandId)}`
    : `${API_BASE}/api/runs`;
  const response = await fetch(url);
  const data = await parseJsonOrThrow<{ items: WorkflowRunRecord[] }>(
    response,
    "任务历史加载失败",
  );
  return data.items;
}

export async function fetchRun(runId: string): Promise<WorkflowRunRecord> {
  const response = await fetch(`${API_BASE}/api/runs/${runId}`);
  const data = await parseJsonOrThrow<{ item: WorkflowRunRecord }>(
    response,
    "任务详情加载失败",
  );
  return data.item;
}

export async function generateWorkflow(
  payload: WorkflowPayload,
  files: File[],
  clientRunId?: string,
  briefFiles: File[] = [],
  referenceImages: File[] = [],
): Promise<WorkflowResult> {
  const formData = new FormData();
  formData.append("payload", JSON.stringify(payload));
  if (clientRunId) formData.append("client_run_id", clientRunId);
  files.forEach((file) => formData.append("files", file));
  briefFiles.forEach((file) => formData.append("brief_files", file));
  referenceImages.forEach((file) => formData.append("reference_images", file));

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

export async function cancelWorkflow(runId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/api/workflows/${runId}/cancel`, {
    method: "POST",
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `取消失败：${response.status}`);
  }
}

export async function fetchWorkflowLogs(
  runId: string,
): Promise<WorkflowLogsResponse> {
  const response = await fetch(`${API_BASE}/api/workflows/${runId}/logs`);
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `日志加载失败：${response.status}`);
  }
  return response.json();
}

export function artifactUrl(runId: string, name: string): string {
  return `${API_BASE}/api/workflows/${runId}/artifacts/${name}`;
}
