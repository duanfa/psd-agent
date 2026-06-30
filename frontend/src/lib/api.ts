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

export interface ChatMessage {
  role: "system" | "user" | "assistant";
  content: string;
}

export interface ModelTestResponse {
  reply: string;
  provider: string;
  model: string;
  base_url?: string | null;
}

export interface ModelTestConfigResponse {
  provider: string;
  model: string;
  vision_model: string;
  base_url?: string | null;
  temperature: number;
  max_tokens: number;
  enable_vision: boolean;
  max_vision_images: number;
  has_api_key: boolean;
  source_path: string;
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
  selected_core_rule_id?: number | null;
  selected_detail_page_rule_id?: number | null;
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
    figma_plugin: string;
    figma_url?: string | null;
    export_status?: string | null;
    export_mode?: string | null;
    export_error?: string | null;
    editable_html: string;
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
  warnings?: string[];
  failure_reason?: string | null;
}

export interface DesignFeedbackItem {
  id: number;
  runId: string;
  feedbackType: string;
  author: string;
  changes: Array<Record<string, unknown>>;
  notes: string;
  createdAt?: string | null;
}

export const API_BASE =
  process.env.NEXT_PUBLIC_PSD_AGENT_API_BASE ?? "http://localhost:8000";

async function fetchJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`${path} 加载失败：${response.status}`);
  }
  return response.json();
}

export interface DashboardResponse {
  page: {
    title: string;
    subtitle: string;
    currentBrandName?: string;
  };
  hero: {
    brandName: string;
    status: string;
    description: string;
    tags: string[];
    weeklyCompletionRate: number;
    weeklyStatus: string;
    weeklySummary: string;
  };
  stats: Array<{ label: string; value: string | number; description: string }>;
  trainingTasks: Array<{ title: string; status: string; summary: string }>;
  designTasks: Array<{ title: string; status: string; summary: string }>;
  quickActions: Array<{ title: string; description: string; href: string }>;
}

export interface BrandAssetsPageResponse {
  page: {
    title: string;
    subtitle: string;
    folders: Array<{ name: string; description: string; icon: string }>;
    uploadForm: { name: string; folder: string; source: string };
  };
  brands: Array<{ id: number; name: string; status: string; assets: number }>;
  filters: { brandId: number; folder: string; status: string; search: string };
  statuses: string[];
  selectedBrand: { id: number; name: string };
  folders: Array<{
    name: string;
    description: string;
    icon: string;
    count: number;
  }>;
  assets: Array<{
    id: number;
    name: string;
    folder: string;
    type: string;
    source: string;
    status: string;
    trainingRole: string;
    includeInTraining: boolean;
    qualityLevel: string;
    size: number;
    createdAt?: string | null;
  }>;
  uploadForm: { name: string; folder: string; source: string };
}

export interface BrandAssetPreviewResponse {
  id: number;
  brandName: string;
  name: string;
  folder: string;
  contentType: string;
  size: number;
  source: string;
  status: string;
  trainingRole: string;
  includeInTraining: boolean;
  qualityLevel: string;
  savedPath: string;
  fileExists: boolean;
  previewType: "image" | "pdf" | "text" | "metadata" | "unknown";
  fileUrl: string;
  textPreview: string;
  metadata: Record<string, unknown>;
  createdAt?: string | null;
}

export interface BrandRulesPageResponse {
  page: { title: string; subtitle: string };
  brands: Array<{
    id: number;
    name: string;
    status: string;
    version: string;
    ruleCount: number;
    coreVersion?: string;
    detailPageVersion?: string;
    totalVersions?: number;
  }>;
  selectedBrand: { id: number; name: string };
  overview: Array<{
    label: string;
    value: string | number;
    description: string;
  }>;
  designRules: Array<{ title: string; description: string }>;
  layoutRules: Array<{ title: string; description: string }>;
  components: Array<{ title: string; description: string }>;
  promptTemplates: Array<{ title: string; description: string }>;
  versions: Array<{
    id: number;
    version: string;
    status: string;
    createdAt?: string | null;
    baseVersion: string;
    ruleCount: number;
    layoutCount: number;
    promptCount: number;
    ruleType: string;
    pageType: string;
    sourceKind: string;
    parentRuleId?: number | null;
    parentVersion?: string;
    targetKey: BrandRuleTarget;
    targetLabel: string;
  }>;
  selectedVersionId?: number | null;
  markdown: string;
  trainingPrompt: string;
  selectedTargetKey?: BrandRuleTarget;
  activeVersions?: Partial<Record<BrandRuleTarget, BrandRuleVersionSummary | null>>;
  targetSummaries?: Array<{
    targetKey: BrandRuleTarget;
    label: string;
    summary: string;
    count: number;
    activeVersion: string;
  }>;
  sourceAssets: Array<{
    id: number;
    name: string;
    folder: string;
    status: string;
    trainingRole: string;
    includeInTraining: boolean;
    qualityLevel: string;
  }>;
  websiteUrls: string[];
  emptyState: string;
}

export type BrandRuleTarget = "brand_core" | "detail_page_layout";

export interface BrandRuleVersionSummary {
  id: number;
  version: string;
  status: string;
  createdAt?: string | null;
  baseVersion: string;
  ruleCount: number;
  layoutCount: number;
  promptCount: number;
  ruleType: string;
  pageType: string;
  sourceKind: string;
  parentRuleId?: number | null;
  parentVersion?: string;
  targetKey: BrandRuleTarget;
  targetLabel: string;
}

export interface BrandRuleOption {
  id: number;
  brandId: number;
  brandName: string;
  version: string;
  status: string;
  ruleCount: number;
  markdown: string;
  updatedAt?: string | null;
  targetKey: BrandRuleTarget;
  targetLabel: string;
  ruleType: string;
  pageType: string;
  label: string;
}

export interface BrandRuleDiffResponse {
  base: { id: number; version: string; status: string; targetKey: BrandRuleTarget };
  compare: { id: number; version: string; status: string; targetKey: BrandRuleTarget };
  diff: Record<
    string,
    {
      added: Array<{ title: string; description: string }>;
      removed: Array<{ title: string; description: string }>;
      changed: Array<{ title: string; from: string; to: string }>;
    }
  >;
}

export interface ProductsPageResponse {
  page: { title: string; subtitle: string };
  products: Array<{
    id: number;
    name: string;
    category: string;
    sellingPointCount: number;
    assetCount: number;
    updatedAt: string;
  }>;
  selectedProduct: {
    id: number;
    name: string;
    category: string;
    summary: string;
    brief: string;
    designDirection: string;
    sellingPoints: string[];
    materials: string[];
  } | null;
  emptyState: string;
}

export interface DesignTasksPageResponse {
  page: { title: string; subtitle: string };
  brands: string[];
  taskTypes: string[];
  statuses: string[];
  filters: { brand: string; status: string; taskType: string; search: string };
  metrics: { total: number; running: number; success: number; failed: number };
  tasks: Array<{
    runId: string;
    taskId: string;
    brand: string;
    product: string;
    taskType: string;
    status: string;
    createdAt?: string | null;
    completedAt?: string | null;
  }>;
}

export interface WorkflowDetailResponse {
  runId: string;
  taskCode: string;
  taskType: string;
  status: string;
  currentStage?: string | null;
  projectName: string;
  brandName: string;
  productName: string;
  workflowMode: string;
  summary: string;
  usedDeepagents: boolean;
  agentReport: string;
  requestPayload: Record<string, unknown>;
  designSpec: Record<string, unknown>;
  warnings: string[];
  failureReason?: string | null;
  createdAt?: string | null;
  completedAt?: string | null;
  stages: StageResult[];
  logs: Array<{
    scope: string;
    title: string;
    message: string;
    payload?: unknown;
    createdAt?: string | null;
  }>;
  assets: Array<{
    name: string;
    contentType?: string | null;
    size: number;
    savedPath?: string | null;
    bucket: string;
    extractedText?: string | null;
  }>;
  artifacts?: {
    previewSvg: string;
    designSpec: string;
    photoshopJsx: string;
    figmaPlugin?: string | null;
    figmaUrl?: string | null;
    exportStatus?: string | null;
    exportMode?: string | null;
    exportError?: string | null;
    editableHtml?: string | null;
    readme: string;
    outputDir: string;
  } | null;
  feedback: DesignFeedbackItem[];
}

export async function fetchDefaults(): Promise<DefaultsResponse> {
  return fetchJson("/api/config/defaults");
}

export async function fetchModelTestConfig(): Promise<ModelTestConfigResponse> {
  return fetchJson("/api/model-test/config");
}

export async function testModel(input: {
  messages: ChatMessage[];
}): Promise<ModelTestResponse> {
  const response = await fetch(`${API_BASE}/api/model-test`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      messages: input.messages,
    }),
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `模型测试失败：${response.status}`);
  }
  return response.json();
}

export async function fetchDashboard(): Promise<DashboardResponse> {
  return fetchJson("/api/pages/dashboard");
}

export async function fetchBrandAssetsPage(): Promise<BrandAssetsPageResponse> {
  return fetchJson("/api/pages/brand-assets");
}

export async function fetchBrandAssetsPageWithFilters(filters: {
  brandId?: number;
  folder?: string;
  status?: string;
  search?: string;
}): Promise<BrandAssetsPageResponse> {
  const params = new URLSearchParams();
  if (filters.brandId) params.set("brand_id", String(filters.brandId));
  if (filters.folder) params.set("folder", filters.folder);
  if (filters.status) params.set("status", filters.status);
  if (filters.search) params.set("search", filters.search);
  const query = params.toString();
  return fetchJson(`/api/pages/brand-assets${query ? `?${query}` : ""}`);
}

export async function createBrand(input: {
  name: string;
  status: string;
}): Promise<{ id: number; name: string; status: string; assets: number }> {
  const response = await fetch(`${API_BASE}/api/brands`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `创建品牌失败：${response.status}`);
  }
  return response.json();
}

export async function updateBrand(input: {
  id: number;
  name: string;
  status: string;
}): Promise<{ id: number; name: string; status: string; assets: number }> {
  const response = await fetch(`${API_BASE}/api/brands/${input.id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name: input.name, status: input.status }),
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `更新品牌失败：${response.status}`);
  }
  return response.json();
}

export async function deleteBrand(
  brandId: number,
): Promise<{ id: number; deletedAssets: number }> {
  const response = await fetch(`${API_BASE}/api/brands/${brandId}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `删除品牌失败：${response.status}`);
  }
  return response.json();
}

export async function fetchBrandRulesPage(): Promise<BrandRulesPageResponse> {
  return fetchJson("/api/pages/brand-rules");
}

export async function fetchBrandRulesPageWithFilters(filters: {
  brandId?: number;
  versionId?: number;
}): Promise<BrandRulesPageResponse> {
  const params = new URLSearchParams();
  if (filters.brandId) params.set("brand_id", String(filters.brandId));
  if (filters.versionId) params.set("version_id", String(filters.versionId));
  const query = params.toString();
  return fetchJson(`/api/pages/brand-rules${query ? `?${query}` : ""}`);
}

export async function fetchBrandRuleOptions(): Promise<{
  rules: BrandRuleOption[];
  coreRules: BrandRuleOption[];
  detailPageRules: BrandRuleOption[];
}> {
  return fetchJson("/api/brand-rules/options");
}

export async function trainBrandRules(input: {
  brandId: number;
  assetIds: number[];
  prompt: string;
  websiteUrls: string[];
  trainingTarget: BrandRuleTarget;
  baseVersionId?: number | null;
  clientRunId?: string;
}): Promise<{ id: number; version: string; markdown: string; targetKey: BrandRuleTarget }> {
  const response = await fetch(`${API_BASE}/api/brand-rules/train`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      brand_id: input.brandId,
      asset_ids: input.assetIds,
      prompt: input.prompt,
      website_urls: input.websiteUrls,
      training_target: input.trainingTarget,
      base_version_id: input.baseVersionId ?? null,
      client_run_id: input.clientRunId ?? null,
    }),
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `训练规则失败：${response.status}`);
  }
  return response.json();
}

export async function fetchBrandRuleTrainLogs(
  runId: string,
): Promise<WorkflowLogsResponse> {
  return fetchJson(`/api/brand-rules/train/${runId}/logs`);
}

export async function updateBrandRuleMarkdown(
  ruleId: number,
  markdown: string,
): Promise<{ id: number; version: string; markdown: string }> {
  const response = await fetch(
    `${API_BASE}/api/brand-rules/${ruleId}/markdown`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ markdown }),
    },
  );
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `保存 Markdown 失败：${response.status}`);
  }
  return response.json();
}

export async function publishBrandRule(
  ruleId: number,
): Promise<{ id: number; version: string; status: string }> {
  const response = await fetch(
    `${API_BASE}/api/brand-rules/${ruleId}/publish`,
    {
      method: "POST",
    },
  );
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `发布版本失败：${response.status}`);
  }
  return response.json();
}

export async function rollbackBrandRule(
  ruleId: number,
): Promise<{ id: number; version: string; status: string }> {
  const response = await fetch(
    `${API_BASE}/api/brand-rules/${ruleId}/rollback`,
    {
      method: "POST",
    },
  );
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `回滚版本失败：${response.status}`);
  }
  return response.json();
}

export async function fetchBrandRuleDiff(
  baseRuleId: number,
  compareRuleId: number,
): Promise<BrandRuleDiffResponse> {
  const params = new URLSearchParams({
    base_rule_id: String(baseRuleId),
    compare_rule_id: String(compareRuleId),
  });
  return fetchJson(`/api/brand-rules/diff?${params.toString()}`);
}

export async function deleteBrandRuleVersion(
  ruleId: number,
): Promise<{ id: number; brandId: number | null; version: string }> {
  const response = await fetch(`${API_BASE}/api/brand-rules/${ruleId}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `删除规则版本失败：${response.status}`);
  }
  return response.json();
}

export async function fetchProductsPage(): Promise<ProductsPageResponse> {
  return fetchJson("/api/pages/products");
}

export async function fetchDesignTasksPage(): Promise<DesignTasksPageResponse> {
  return fetchJson("/api/pages/design-tasks");
}

export async function fetchDesignTasksPageWithFilters(filters: {
  brand?: string;
  status?: string;
  taskType?: string;
  search?: string;
}): Promise<DesignTasksPageResponse> {
  const params = new URLSearchParams();
  if (filters.brand) params.set("brand", filters.brand);
  if (filters.status) params.set("status", filters.status);
  if (filters.taskType) params.set("task_type", filters.taskType);
  if (filters.search) params.set("search", filters.search);
  const query = params.toString();
  return fetchJson(`/api/pages/design-tasks${query ? `?${query}` : ""}`);
}

export async function uploadBrandAssets(input: {
  brandId: number;
  name: string;
  folder: string;
  source: string;
  files: File[];
}): Promise<{ created: Array<{ id: number; name: string }>; count: number }> {
  const formData = new FormData();
  formData.append("brand_id", String(input.brandId));
  formData.append("name", input.name);
  formData.append("folder", input.folder);
  formData.append("source", input.source);
  input.files.forEach((file) => formData.append("files", file));
  const response = await fetch(`${API_BASE}/api/brand-assets/upload`, {
    method: "POST",
    body: formData,
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `资产上传失败：${response.status}`);
  }
  return response.json();
}

export async function fetchBrandAssetPreview(
  assetId: number,
): Promise<BrandAssetPreviewResponse> {
  return fetchJson(`/api/brand-assets/${assetId}/preview`);
}

export async function deleteBrandAsset(
  assetId: number,
): Promise<{ id: number; brandId: number }> {
  const response = await fetch(`${API_BASE}/api/brand-assets/${assetId}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `删除资产失败：${response.status}`);
  }
  return response.json();
}

export async function updateBrandAssetTrainingMeta(input: {
  assetId: number;
  trainingRole: string;
  includeInTraining: boolean;
  qualityLevel: string;
}): Promise<{
  id: number;
  trainingRole: string;
  includeInTraining: boolean;
  qualityLevel: string;
}> {
  const response = await fetch(`${API_BASE}/api/brand-assets/${input.assetId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      training_role: input.trainingRole,
      include_in_training: input.includeInTraining,
      quality_level: input.qualityLevel,
    }),
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `更新资产训练信息失败：${response.status}`);
  }
  return response.json();
}

export function brandAssetFileUrl(path: string): string {
  return `${API_BASE}${path}`;
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
  const response = await fetch(`${API_BASE}/api/workflows/${runId}/logs`, {
    cache: "no-store",
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `日志加载失败：${response.status}`);
  }
  return response.json();
}

export async function fetchWorkflowDetail(
  runId: string,
): Promise<WorkflowDetailResponse> {
  return fetchJson(`/api/workflows/${runId}`);
}

export async function createWorkflowFeedback(input: {
  runId: string;
  feedbackType: string;
  author: string;
  changes: Array<Record<string, unknown>>;
  notes: string;
}): Promise<DesignFeedbackItem> {
  const response = await fetch(
    `${API_BASE}/api/workflows/${input.runId}/feedback`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        feedback_type: input.feedbackType,
        author: input.author,
        changes: input.changes,
        notes: input.notes,
      }),
    },
  );
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `保存反馈失败：${response.status}`);
  }
  return response.json();
}

export async function fetchWorkflowFeedback(
  runId: string,
): Promise<{ items: DesignFeedbackItem[] }> {
  return fetchJson(`/api/workflows/${runId}/feedback`);
}

export function artifactUrl(runId: string, name: string): string {
  return `${API_BASE}/api/workflows/${runId}/artifacts/${name}`;
}
