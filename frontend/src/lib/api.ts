export type WorkflowMode = "smart_recommend" | "strict_brand";
export type OutputType = "detail_page" | "figma_page" | "psd_file" | "main_image" | "banner";

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

export type StageStatus = "completed" | "fallback" | "skipped" | "failed" | "running";

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
  folders: Array<{ name: string; description: string; icon: string; count: number }>;
  assets: Array<{
    id: number;
    name: string;
    folder: string;
    type: string;
    source: string;
    status: string;
    size: number;
    createdAt?: string | null;
  }>;
  uploadForm: { name: string; folder: string; source: string };
}

export interface BrandRulesPageResponse {
  page: { title: string; subtitle: string };
  brands: Array<{ id: number; name: string; status: string; version: string; ruleCount: number }>;
  selectedBrand: { id: number; name: string };
  overview: Array<{ label: string; value: string | number; description: string }>;
  designRules: Array<{ title: string; description: string }>;
  layoutRules: Array<{ title: string; description: string }>;
  components: Array<{ title: string; description: string }>;
  promptTemplates: Array<{ title: string; description: string }>;
  emptyState: string;
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
  };
}

export interface DesignTasksPageResponse {
  page: { title: string; subtitle: string };
  brands: string[];
  taskTypes: string[];
  statuses: string[];
  filters: { brand: string; status: string; taskType: string; search: string };
  metrics: { total: number; running: number; success: number; failed: number };
  tasks: Array<{
    taskId: string;
    brand: string;
    product: string;
    taskType: string;
    status: string;
    createdAt?: string | null;
    completedAt?: string | null;
  }>;
}

export async function fetchDefaults(): Promise<DefaultsResponse> {
  return fetchJson("/api/config/defaults");
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

export async function fetchBrandRulesPage(): Promise<BrandRulesPageResponse> {
  return fetchJson("/api/pages/brand-rules");
}

export async function fetchBrandRulesPageWithFilters(filters: {
  brandId?: number;
}): Promise<BrandRulesPageResponse> {
  const params = new URLSearchParams();
  if (filters.brandId) params.set("brand_id", String(filters.brandId));
  const query = params.toString();
  return fetchJson(`/api/pages/brand-rules${query ? `?${query}` : ""}`);
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

export async function fetchWorkflowLogs(runId: string): Promise<WorkflowLogsResponse> {
  const response = await fetch(`${API_BASE}/api/workflows/${runId}/logs`, { cache: "no-store" });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `日志加载失败：${response.status}`);
  }
  return response.json();
}

export function artifactUrl(runId: string, name: string): string {
  return `${API_BASE}/api/workflows/${runId}/artifacts/${name}`;
}
