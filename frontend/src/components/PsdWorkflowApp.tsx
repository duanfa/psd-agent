"use client";

import {
  BookOpen,
  Boxes,
  ClipboardCheck,
  Cpu,
  Download,
  FileText,
  Image as ImageIcon,
  Layers,
  Loader2,
  MessageSquare,
  Palette,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  Type,
  Upload,
  XCircle,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  API_BASE,
  artifactUrl,
  cancelWorkflow,
  createWorkflowFeedback,
  fetchBrandRuleOptions,
  fetchDefaults,
  fetchWorkflowFeedback,
  fetchWorkflowLogs,
  generateWorkflow,
  type AgentPrompts,
  type BrandRuleOption,
  type OutputType,
  type RequirementConstraints,
  type StageMeta,
  type WorkflowPayload,
  type WorkflowResult,
} from "@/lib/api";
import { PipelineRibbon } from "./PipelineRibbon";
import { ModelTestPanel } from "./ModelTestPanel";
import { Section } from "./Section";
import { StageTimeline } from "./StageTimeline";

const FALLBACK_STAGES: StageMeta[] = [
  { id: "product_understanding", title: "商品理解 Agent", icon: "eye" },
  { id: "product_brief", title: "Product Brief", icon: "layers" },
  { id: "brand_knowledge", title: "品牌知识库 / 规则版本", icon: "library" },
  { id: "page_planner", title: "页面规划 Agent", icon: "palette" },
  { id: "image_generation", title: "图片生成 Agent", icon: "image" },
  { id: "layout_engine", title: "Layout Engine", icon: "grid" },
  { id: "copy", title: "文案 Agent", icon: "type" },
  { id: "figma_psd", title: "Figma / PSD 生成 Agent", icon: "file-image" },
  { id: "design_score", title: "Design Score", icon: "check-circle" },
  { id: "output_review", title: "输出、审核与反馈", icon: "check-circle" },
];

const PROMPT_LABELS: Record<keyof AgentPrompts, string> = {
  system_prompt: "主控 System Prompt",
  vision_agent_prompt: "商品理解 Agent",
  structured_agent_prompt: "Product Brief Agent",
  brand_rag_agent_prompt: "品牌知识库与规则版本 Agent",
  design_agent_prompt: "页面规划 Agent",
  layout_agent_prompt: "Layout Engine Agent",
  copy_agent_prompt: "文案 Agent",
  psd_agent_prompt: "Figma / PSD 生成 Agent",
};

const OUTPUT_LABELS: Record<OutputType, string> = {
  detail_page: "商品详情页方案",
  figma_page: "Figma 页面",
  psd_file: "PSD 兼容文件",
  main_image: "主图设计稿",
  banner: "广告 Banner",
};

type ConfigSection =
  | "model_config"
  | "typography"
  | "layout"
  | "requirement_constraints"
  | "prompts";
type PageTab = "workflow" | "model-test";

const WORKFLOW_DRAFT_KEY = "brandos.workflow.createTaskDraft.v1";

interface WorkflowDraft {
  payload: WorkflowPayload;
  selectedCoreRuleId?: number | "";
  selectedDetailPageRuleId?: number | "";
  selectedBrandRuleId?: number | "";
  updatedAt: string;
}

function patchSection<K extends ConfigSection>(
  value: WorkflowPayload,
  section: K,
  patch: Partial<WorkflowPayload[K]>,
): WorkflowPayload {
  return { ...value, [section]: { ...value[section], ...patch } };
}

function readWorkflowDraft(): WorkflowDraft | null {
  try {
    const raw = window.localStorage.getItem(WORKFLOW_DRAFT_KEY);
    if (!raw) return null;
    const draft = JSON.parse(raw) as WorkflowDraft;
    return draft?.payload ? { ...draft, payload: sanitizeWorkflowDraft(draft.payload) } : null;
  } catch {
    return null;
  }
}

function sanitizeWorkflowDraft(payload: WorkflowPayload): WorkflowPayload {
  return {
    ...payload,
    model_config: {
      provider: "",
      model: "",
      vision_model: "",
      api_key: "",
      base_url: "",
      temperature: 0,
      max_tokens: 0,
      enable_deepagents: false,
      enable_vision: false,
      max_vision_images: 0,
    },
  };
}

function mergeWorkflowDraft(defaultPayload: WorkflowPayload, draftPayload: WorkflowPayload): WorkflowPayload {
  return {
    ...defaultPayload,
    ...draftPayload,
    model_config: { ...defaultPayload.model_config },
    typography: { ...defaultPayload.typography, ...draftPayload.typography },
    layout: { ...defaultPayload.layout, ...draftPayload.layout },
    requirement_constraints: {
      ...defaultPayload.requirement_constraints,
      ...draftPayload.requirement_constraints,
    },
    prompts: { ...defaultPayload.prompts, ...draftPayload.prompts },
    output_types: draftPayload.output_types?.length ? draftPayload.output_types : defaultPayload.output_types,
  };
}

function splitLines(value: string): string[] {
  return value
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function joinLines(value: string[] | undefined): string {
  return (value ?? []).join("\n");
}

function formatDraftTime(value: string | null) {
  if (!value) return "尚未保存草稿";
  return `草稿已保存 ${new Date(value).toLocaleString("zh-CN", { hour12: false })}`;
}

export function PsdWorkflowApp() {
  const [payload, setPayload] = useState<WorkflowPayload | null>(null);
  const [stages, setStages] = useState<StageMeta[]>(FALLBACK_STAGES);
  const [files, setFiles] = useState<File[]>([]);
  const [briefFiles, setBriefFiles] = useState<File[]>([]);
  const [referenceImages, setReferenceImages] = useState<File[]>([]);
  const [result, setResult] = useState<WorkflowResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [currentRunId, setCurrentRunId] = useState<string | null>(null);
  const [currentStageId, setCurrentStageId] = useState<string | null>(null);
  const [selectedStageId, setSelectedStageId] = useState<string | null>(null);
  const [liveStages, setLiveStages] = useState<WorkflowResult["stages"]>([]);
  const [workflowLogs, setWorkflowLogs] = useState<string[]>([]);
  const [workflowLogStatus, setWorkflowLogStatus] = useState<string>("idle");
  const [workflowFailureReason, setWorkflowFailureReason] = useState<string | null>(null);
  const [brandRules, setBrandRules] = useState<BrandRuleOption[]>([]);
  const [brandRulesLoading, setBrandRulesLoading] = useState(false);
  const [brandRulesError, setBrandRulesError] = useState<string | null>(null);
  const [selectedCoreRuleId, setSelectedCoreRuleId] = useState<number | "">("");
  const [selectedDetailPageRuleId, setSelectedDetailPageRuleId] = useState<number | "">("");
  const [draftReady, setDraftReady] = useState(false);
  const [draftMessage, setDraftMessage] = useState("正在检查草稿箱...");
  const [activeTab, setActiveTab] = useState<PageTab>("workflow");
  const [feedbackNotes, setFeedbackNotes] = useState("");
  const [feedbackAuthor, setFeedbackAuthor] = useState("designer");
  const [feedbackSaving, setFeedbackSaving] = useState(false);
  const [feedbackItems, setFeedbackItems] = useState<
    Array<{ id: number; notes: string; author: string; createdAt?: string | null }>
  >([]);
  const draftSaveTimer = useRef<number | null>(null);
  const skipNextDraftSave = useRef(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchDefaults()
      .then((defaults) => {
        const draft = readWorkflowDraft();
        setPayload(draft ? mergeWorkflowDraft(defaults.payload, draft.payload) : defaults.payload);
        setSelectedCoreRuleId(draft?.selectedCoreRuleId ?? draft?.selectedBrandRuleId ?? "");
        setSelectedDetailPageRuleId(draft?.selectedDetailPageRuleId ?? "");
        setDraftMessage(draft ? formatDraftTime(draft.updatedAt) : "暂无草稿，编辑后会自动保存");
        setDraftReady(true);
        if (defaults.stages?.length) setStages(defaults.stages);
      })
      .catch((err) => setError(err instanceof Error ? err.message : String(err)));
  }, []);

  useEffect(() => {
    if (!draftReady || !payload) return;
    if (skipNextDraftSave.current) {
      skipNextDraftSave.current = false;
      return;
    }
    if (draftSaveTimer.current) window.clearTimeout(draftSaveTimer.current);
    draftSaveTimer.current = window.setTimeout(() => {
      const updatedAt = new Date().toISOString();
      try {
        window.localStorage.setItem(
          WORKFLOW_DRAFT_KEY,
          JSON.stringify({
            payload: sanitizeWorkflowDraft(payload),
            selectedCoreRuleId,
            selectedDetailPageRuleId,
            updatedAt,
          }),
        );
        setDraftMessage(formatDraftTime(updatedAt));
      } catch {
        setDraftMessage("草稿保存失败，请检查浏览器存储空间");
      }
    }, 300);
    return () => {
      if (draftSaveTimer.current) window.clearTimeout(draftSaveTimer.current);
    };
  }, [draftReady, payload, selectedCoreRuleId, selectedDetailPageRuleId]);

  useEffect(() => {
    setBrandRulesLoading(true);
    fetchBrandRuleOptions()
      .then((data) => {
        setBrandRules(data.rules);
        setBrandRulesError(null);
      })
      .catch((err) => setBrandRulesError(err instanceof Error ? err.message : String(err)))
      .finally(() => setBrandRulesLoading(false));
  }, []);

  const previewUrl = useMemo(
    () => (result?.run_id ? artifactUrl(result.run_id, "preview.svg") : null),
    [result],
  );

  const selectedStage = useMemo(
    () => stages.find((stage) => stage.id === selectedStageId),
    [selectedStageId, stages],
  );

  const timelineStages = loading || liveStages.length ? liveStages : result?.stages ?? [];

  const selectedCoreRule = useMemo(
    () => brandRules.find((rule) => rule.id === selectedCoreRuleId),
    [brandRules, selectedCoreRuleId],
  );
  const selectedDetailPageRule = useMemo(
    () => brandRules.find((rule) => rule.id === selectedDetailPageRuleId),
    [brandRules, selectedDetailPageRuleId],
  );
  const coreRules = useMemo(
    () => brandRules.filter((rule) => rule.targetKey === "brand_core"),
    [brandRules],
  );
  const detailPageRules = useMemo(
    () =>
      brandRules.filter(
        (rule) =>
          rule.targetKey === "detail_page_layout" &&
          (!selectedCoreRuleId || rule.brandId === selectedCoreRule?.brandId),
      ),
    [brandRules, selectedCoreRule, selectedCoreRuleId],
  );

  useEffect(() => {
    if (selectedDetailPageRuleId === "") return;
    const detailRule = brandRules.find((rule) => rule.id === selectedDetailPageRuleId);
    if (!detailRule || detailRule.targetKey !== "detail_page_layout") {
      setSelectedDetailPageRuleId("");
      return;
    }
    if (selectedCoreRule && detailRule.brandId !== selectedCoreRule.brandId) {
      setSelectedDetailPageRuleId("");
    }
  }, [brandRules, selectedCoreRule, selectedDetailPageRuleId]);

  useEffect(() => {
    if (!currentRunId) return;
    let stopped = false;

    const loadLogs = async () => {
      try {
        const snapshot = await fetchWorkflowLogs(currentRunId);
        if (stopped) return;
        setWorkflowLogs(snapshot.logs);
        setLiveStages(snapshot.stages);
        setWorkflowLogStatus(snapshot.status);
        setCurrentStageId(snapshot.current_stage ?? null);
      } catch {
        // 日志轮询不能影响主生成链路。
      }
    };

    void loadLogs();
    const timer = window.setInterval(loadLogs, 800);
    return () => {
      stopped = true;
      window.clearInterval(timer);
    };
  }, [currentRunId]);

  useEffect(() => {
    if (loading && currentStageId && !selectedStageId) {
      setSelectedStageId(currentStageId);
    }
  }, [currentStageId, loading, selectedStageId]);

  if (!payload) {
    return (
      <main className="page">
        <div className="boot">
          <Loader2 className="spin" size={22} /> 正在加载工作流配置…
          {error ? <div className="error">{error}</div> : null}
        </div>
      </main>
    );
  }

  const setField = <K extends keyof WorkflowPayload>(
    key: K,
    value: WorkflowPayload[K],
  ) => setPayload((current) => (current ? { ...current, [key]: value } : current));

  const setModel = (key: keyof WorkflowPayload["model_config"], value: unknown) =>
    setPayload((c) =>
      c
        ? patchSection(c, "model_config", {
            [key]: value,
          } as Partial<WorkflowPayload["model_config"]>)
        : c,
    );

  const setTypo = (key: keyof WorkflowPayload["typography"], value: unknown) =>
    setPayload((c) =>
      c
        ? patchSection(c, "typography", {
            [key]: value,
          } as Partial<WorkflowPayload["typography"]>)
        : c,
    );

  const setLayout = (key: keyof WorkflowPayload["layout"], value: unknown) =>
    setPayload((c) =>
      c
        ? patchSection(c, "layout", {
            [key]: value,
          } as Partial<WorkflowPayload["layout"]>)
        : c,
    );

  const setRequirementConstraint = (
    key: keyof RequirementConstraints,
    value: RequirementConstraints[keyof RequirementConstraints],
  ) =>
    setPayload((c) =>
      c
        ? patchSection(c, "requirement_constraints", {
            [key]: value,
          } as Partial<RequirementConstraints>)
        : c,
    );

  const setPrompt = (key: keyof AgentPrompts, value: string) =>
    setPayload((c) =>
      c ? patchSection(c, "prompts", { [key]: value } as Partial<AgentPrompts>) : c,
    );

  const applySelectedBrandRule = () => {
    if (!selectedCoreRule && !selectedDetailPageRule) return;
    const sections = [
      selectedCoreRule ? `## 品牌核心规则\n\n${selectedCoreRule.markdown}` : "",
      selectedDetailPageRule ? `## 商品详情页规则\n\n${selectedDetailPageRule.markdown}` : "",
    ].filter(Boolean);
    setPayload((current) =>
      current
        ? {
            ...current,
            brand_name: selectedCoreRule?.brandName ?? selectedDetailPageRule?.brandName ?? current.brand_name,
            brand_guidelines: sections.join("\n\n---\n\n"),
          }
        : current,
    );
  };

  const toggleOutput = (type: OutputType) =>
    setPayload((c) => {
      if (!c) return c;
      const exists = c.output_types.includes(type);
      return {
        ...c,
        output_types: exists
          ? c.output_types.filter((item) => item !== type)
          : [...c.output_types, type],
      };
    });

  const handleGenerate = async () => {
    const runId = crypto.randomUUID();
    const workflowPayload: WorkflowPayload = {
      ...payload,
      selected_core_rule_id: typeof selectedCoreRuleId === "number" ? selectedCoreRuleId : null,
      selected_detail_page_rule_id:
        typeof selectedDetailPageRuleId === "number" ? selectedDetailPageRuleId : null,
    };
    setCurrentRunId(runId);
    setCurrentStageId(null);
    setSelectedStageId(null);
    setLiveStages([]);
    setWorkflowLogs([]);
    setWorkflowLogStatus("running");
    setWorkflowFailureReason(null);
    setFeedbackItems([]);
    setLoading(true);
    setCancelling(false);
    setError(null);
    setResult(null);
    try {
      const workflowResult = await generateWorkflow(
        workflowPayload,
        files,
        runId,
        briefFiles,
        referenceImages,
      );
      setResult(workflowResult);
      const snapshot = await fetchWorkflowLogs(runId);
      setWorkflowLogs(snapshot.logs);
      setLiveStages(snapshot.stages);
      setWorkflowLogStatus(snapshot.status);
      setWorkflowFailureReason(snapshot.failure_reason ?? null);
      setCurrentStageId(snapshot.current_stage ?? null);
      const feedback = await fetchWorkflowFeedback(runId);
      setFeedbackItems(feedback.items);
    } catch (err) {
      try {
        const snapshot = await fetchWorkflowLogs(runId);
        setWorkflowLogs(snapshot.logs);
        setLiveStages(snapshot.stages);
        setWorkflowLogStatus(snapshot.status);
        setWorkflowFailureReason(snapshot.failure_reason ?? null);
        setCurrentStageId(snapshot.current_stage ?? null);
      } catch {
        // ignore
      }
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
      setCancelling(false);
      setCurrentRunId(null);
    }
  };

  const handleSaveFeedback = async () => {
    if (!result?.run_id || !feedbackNotes.trim()) return;
    setFeedbackSaving(true);
    setError(null);
    try {
      const item = await createWorkflowFeedback({
        runId: result.run_id,
        feedbackType: "designer_edit",
        author: feedbackAuthor,
        changes: [
          {
            type: "notes",
            source: "result_panel",
            trackedChanges: ["字体字号调整", "颜色调整", "布局调整", "文案修改", "图片替换"],
          },
        ],
        notes: feedbackNotes,
      });
      setFeedbackItems((current) => [item, ...current]);
      setFeedbackNotes("");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setFeedbackSaving(false);
    }
  };

  const handleCancel = async () => {
    if (!currentRunId || cancelling) return;
    setCancelling(true);
    setError("正在请求中断当前生成任务，后端会在当前模型调用结束后的检查点停止。");
    try {
      await cancelWorkflow(currentRunId);
    } catch (err) {
      setCancelling(false);
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  return (
    <main className="page">
      <header className="hero">
        <div className="hero-text">
          <div className="eyebrow">
            <Sparkles size={14} /> BrandOS AI Design Operating System
          </div>
          <h1>BrandOS AI 电商设计平台</h1>
          <p>
            围绕「品牌资产 → 品牌知识库 → 规则版本 → Product Brief → 页面规划 → Layout
            Engine → Figma / PSD → 评分与反馈」编排。当前页面是可运行的 MVP 控制台，对齐新版
            PRD 与静态原型的核心链路。
          </p>
        </div>
        <div className="hero-side">
          <span className={`pill ${payload.model_config.enable_deepagents ? "pill-on" : "pill-off"}`}>
            <Cpu size={14} />
            {payload.model_config.enable_deepagents ? "DeepAgents 开启" : "规则降级"}
          </span>
          <span className="pill pill-ghost">{draftMessage}</span>
          <span className="pill pill-ghost">{API_BASE}</span>
        </div>
      </header>

      <section className="ribbon-wrap">
        <PipelineRibbon
          stages={stages}
          results={timelineStages}
          running={loading}
          currentStageId={currentStageId}
          selectedStageId={selectedStageId}
          onStageClick={setSelectedStageId}
        />
      </section>

      <section className="brandos-overview">
        <OverviewCard
          icon={<BookOpen size={17} />}
          label="品牌知识库"
          title="Core / Derived / Asset Memory"
          text="核心规则不可自动覆盖，新资产先进入训练池并生成变更建议。"
        />
        <OverviewCard
          icon={<ShieldCheck size={17} />}
          label="规则版本"
          title="V1.1 Draft → 审批发布"
          text="支持 Diff、审批、回滚和审计思路，避免持续上传导致品牌漂移。"
        />
        <OverviewCard
          icon={<Layers size={17} />}
          label="页面中间结构"
          title="Layout JSON First"
          text="详情页不是一张图，先生成模块、组件和图层结构，再映射设计稿。"
        />
        <OverviewCard
          icon={<ClipboardCheck size={17} />}
          label="评分与反馈"
          title="Design Score + Human Feedback"
          text="输出评分解释和设计师修改记录，但本阶段不自动改写品牌规则。"
        />
      </section>

      <section className="tab-switch" aria-label="工作台功能切换">
        <button
          className={`tab-switch-button ${activeTab === "workflow" ? "active" : ""}`}
          type="button"
          onClick={() => setActiveTab("workflow")}
        >
          <Layers size={16} /> 工作流配置
        </button>
        <button
          className={`tab-switch-button ${activeTab === "model-test" ? "active" : ""}`}
          type="button"
          onClick={() => setActiveTab("model-test")}
        >
          <MessageSquare size={16} /> 模型测试
        </button>
      </section>

      {activeTab === "workflow" ? (
        <div className="shell">
        <section className="panel config-panel">
          <div className="panel-header">
            <div className="panel-title">
              <Layers size={18} /> 工作流配置
            </div>
          </div>

          <div className="panel-scroll">
            <Section
              title="任务基础信息"
              description="品牌、商品、Product Brief、Brief Excel 与参考案例"
              icon={<FileText size={16} />}
              defaultOpen
            >
              <div className="grid-2">
                <Field label="项目名称">
                  <input
                    value={payload.project_name}
                    onChange={(e) => setField("project_name", e.target.value)}
                  />
                </Field>
                <Field label="品牌名称">
                  <input
                    value={payload.brand_name}
                    onChange={(e) => setField("brand_name", e.target.value)}
                  />
                </Field>
                <Field label="商品名称">
                  <input
                    value={payload.product_name}
                    onChange={(e) => setField("product_name", e.target.value)}
                  />
                </Field>
                <Field label="工作流模式">
                  <select
                    value={payload.workflow_mode}
                    onChange={(e) =>
                      setField(
                        "workflow_mode",
                        e.target.value as WorkflowPayload["workflow_mode"],
                      )
                    }
                  >
                    <option value="smart_recommend">智能推荐模式</option>
                    <option value="strict_brand">严格品牌规范模式</option>
                  </select>
                </Field>
              </div>
              <Field label="Product Brief / 商品信息">
                <textarea
                  value={payload.product_brief}
                  onChange={(e) => setField("product_brief", e.target.value)}
                />
              </Field>
              <Field label="品牌规范 / Core Rule + 详情页规则">
                <div className="brand-rule-picker">
                  <select
                    value={selectedCoreRuleId}
                    disabled={brandRulesLoading || coreRules.length === 0}
                    onChange={(e) =>
                      setSelectedCoreRuleId(e.target.value ? Number(e.target.value) : "")
                    }
                  >
                    <option value="">
                      {brandRulesLoading
                        ? "正在加载品牌规则版本..."
                        : coreRules.length
                          ? "选择品牌设计规范 / Core Rule"
                          : "暂无已训练品牌核心规则"}
                    </option>
                    {coreRules.map((rule) => (
                      <option key={rule.id} value={rule.id}>
                        {rule.label}
                      </option>
                    ))}
                  </select>
                  <select
                    value={selectedDetailPageRuleId}
                    disabled={brandRulesLoading || detailPageRules.length === 0}
                    onChange={(e) =>
                      setSelectedDetailPageRuleId(e.target.value ? Number(e.target.value) : "")
                    }
                  >
                    <option value="">
                      {brandRulesLoading
                        ? "正在加载详情页规则..."
                        : detailPageRules.length
                          ? "选择商品详情页 Derived Rule（可选）"
                          : "暂无详情页布局规则"}
                    </option>
                    {detailPageRules.map((rule) => (
                      <option key={rule.id} value={rule.id}>
                        {rule.label}
                      </option>
                    ))}
                  </select>
                  <button
                    className="btn ghost brand-rule-apply"
                    disabled={!selectedCoreRule && !selectedDetailPageRule}
                    type="button"
                    onClick={applySelectedBrandRule}
                  >
                    组合应用
                  </button>
                </div>
                {selectedCoreRule || selectedDetailPageRule ? (
                  <p className="hint">
                    生成时会结构化注入
                    {selectedCoreRule
                      ? ` ${selectedCoreRule.brandName} / ${selectedCoreRule.version} 的 Core Rule`
                      : ""}
                    {selectedDetailPageRule
                      ? ` ${selectedCoreRule ? "和" : ""} ${selectedDetailPageRule.brandName} / ${selectedDetailPageRule.version} 的详情页规则`
                      : ""}
                    ；点击“组合应用”只会把规则摘要填入当前输入框，方便你继续人工补充说明。
                  </p>
                ) : brandRulesError ? (
                  <p className="hint">{brandRulesError}</p>
                ) : null}
                <textarea
                  className="brand-guidelines-textarea"
                  value={payload.brand_guidelines}
                  onChange={(e) => setField("brand_guidelines", e.target.value)}
                />
              </Field>
              <Field label="参考案例 / Asset Memory">
                <textarea
                  value={payload.reference_notes}
                  onChange={(e) => setField("reference_notes", e.target.value)}
                />
              </Field>
              <div className="grid-2">
                <Field label="Brief Excel 文件">
                  <label className="mini-dropzone">
                    <Upload size={16} />
                    <span>上传商品 brief Excel</span>
                    <input
                      multiple
                      accept=".xlsx,.xls,.xlsm,.csv"
                      style={{ display: "none" }}
                      type="file"
                      onChange={(e) => setBriefFiles(Array.from(e.target.files ?? []))}
                    />
                  </label>
                  {briefFiles.length ? (
                    <div className="chips">
                      {briefFiles.map((file) => (
                        <span className="chip-static" key={`${file.name}-${file.size}`}>
                          <FileText size={13} />
                          {file.name}
                        </span>
                      ))}
                    </div>
                  ) : (
                    <p className="hint">生成时会解析 Excel，并追加到 Product Brief 中参考。</p>
                  )}
                </Field>
                <Field label="参考案例图片">
                  <label className="mini-dropzone">
                    <ImageIcon size={16} />
                    <span>上传参考页面 / 案例图</span>
                    <input
                      multiple
                      accept="image/*"
                      style={{ display: "none" }}
                      type="file"
                      onChange={(e) => setReferenceImages(Array.from(e.target.files ?? []))}
                    />
                  </label>
                  {referenceImages.length ? (
                    <div className="chips">
                      {referenceImages.map((file) => (
                        <span className="chip-static" key={`${file.name}-${file.size}`}>
                          <ImageIcon size={13} />
                          {file.name}
                        </span>
                      ))}
                    </div>
                  ) : (
                    <p className="hint">参考案例图片进入 Asset Memory，不作为商品图识别。</p>
                  )}
                </Field>
              </div>
            </Section>

            <Section
              title="品牌资产与输出"
              description="上传品牌规范、参考案例、商品图、字体"
              icon={<Upload size={16} />}
              badge={files.length ? `${files.length} 个文件` : undefined}
              defaultOpen
            >
              <label className="dropzone">
                <Upload size={18} />
                <span>点击选择资产文件（可多选）</span>
                <input
                  multiple
                  style={{ display: "none" }}
                  type="file"
                  onChange={(e) => setFiles(Array.from(e.target.files ?? []))}
                />
              </label>
              {files.length ? (
                <div className="chips">
                  {files.map((file) => (
                    <span className="chip-static" key={`${file.name}-${file.size}`}>
                      <ImageIcon size={13} />
                      {file.name} · {(file.size / 1024).toFixed(0)} KB
                    </span>
                  ))}
                </div>
              ) : (
                <p className="hint">未选择文件时，将基于文本、默认规则版本和示例 Asset Memory 生成。</p>
              )}
              <div className="section-subtitle">输出类型</div>
              <div className="chips">
                {(Object.keys(OUTPUT_LABELS) as OutputType[]).map((type) => (
                  <label
                    className={`chip-toggle ${
                      payload.output_types.includes(type) ? "chip-active" : ""
                    }`}
                    key={type}
                  >
                    <input
                      checked={payload.output_types.includes(type)}
                      type="checkbox"
                      onChange={() => toggleOutput(type)}
                    />
                    {OUTPUT_LABELS[type]}
                  </label>
                ))}
              </div>
            </Section>

            <Section
              title="模型参数"
              description="统一由后端配置文件管理，页面内只读展示"
              icon={<Cpu size={16} />}
            >
              <div className="grid-2">
                <Field label="Provider">
                  <input
                    disabled
                    value={payload.model_config.provider}
                    onChange={(e) => setModel("provider", e.target.value)}
                  />
                </Field>
                <Field label="文本模型">
                  <input
                    disabled
                    value={payload.model_config.model}
                    onChange={(e) => setModel("model", e.target.value)}
                  />
                </Field>
                <Field label="视觉模型（多模态）">
                  <input
                    disabled
                    value={payload.model_config.vision_model}
                    onChange={(e) => setModel("vision_model", e.target.value)}
                  />
                </Field>
                <Field label={`视觉最多读图 · ${payload.model_config.max_vision_images}`}>
                  <input
                    disabled
                    max={12}
                    min={1}
                    type="range"
                    value={payload.model_config.max_vision_images}
                    onChange={(e) =>
                      setModel("max_vision_images", Number(e.target.value))
                    }
                  />
                </Field>
                <Field label="Base URL">
                  <input
                    disabled
                    value={payload.model_config.base_url ?? ""}
                    placeholder="OpenAI compatible 可选"
                    onChange={(e) => setModel("base_url", e.target.value)}
                  />
                </Field>
                <Field label="API Key">
                  <input
                    disabled
                    type="password"
                    value={payload.model_config.api_key ?? ""}
                    placeholder="可留空，后端读环境变量"
                    onChange={(e) => setModel("api_key", e.target.value)}
                  />
                </Field>
                <Field label={`Temperature · ${payload.model_config.temperature}`}>
                  <input
                    disabled
                    max={2}
                    min={0}
                    step={0.1}
                    type="range"
                    value={payload.model_config.temperature}
                    onChange={(e) => setModel("temperature", Number(e.target.value))}
                  />
                </Field>
                <Field label="Max Tokens">
                  <input
                    disabled
                    min={512}
                    step={512}
                    type="number"
                    value={payload.model_config.max_tokens}
                    onChange={(e) => setModel("max_tokens", Number(e.target.value))}
                  />
                </Field>
              </div>
              <p className="hint">
                当前页面不会修改系统模型配置，所有大模型调用统一读取
                `config/workflow-defaults.json` /
                `config/workflow-defaults.local.json` 的 `model_config`，
                若存在 `config/workflow-gpt.json` 则会再覆盖其同名字段。
              </p>
              <label className="switch">
                <input
                  disabled
                  checked={payload.model_config.enable_deepagents}
                  type="checkbox"
                  onChange={(e) => setModel("enable_deepagents", e.target.checked)}
                />
                <span className="switch-track" />
                使用 DeepAgents 执行多 Agent 链路（关闭则全程规则生成）
              </label>
              <label className="switch">
                <input
                  disabled
                  checked={payload.model_config.enable_vision}
                  type="checkbox"
                  onChange={(e) => setModel("enable_vision", e.target.checked)}
                />
                <span className="switch-track" />
                视觉理解阶段用多模态模型真正读取上传图片
              </label>
            </Section>

            <Section title="品牌字体与字号" description="Core Rule 中的字体约束" icon={<Type size={16} />}>
              <div className="grid-2">
                <Field label="主标题字体">
                  <input
                    value={payload.typography.title_font}
                    onChange={(e) => setTypo("title_font", e.target.value)}
                  />
                </Field>
                <Field label="正文字体">
                  <input
                    value={payload.typography.body_font}
                    onChange={(e) => setTypo("body_font", e.target.value)}
                  />
                </Field>
                <Field label="英文字体">
                  <input
                    value={payload.typography.english_font}
                    onChange={(e) => setTypo("english_font", e.target.value)}
                  />
                </Field>
                <Field label="字重">
                  <select
                    value={payload.typography.font_weight}
                    onChange={(e) =>
                      setTypo(
                        "font_weight",
                        e.target.value as WorkflowPayload["typography"]["font_weight"],
                      )
                    }
                  >
                    <option value="Regular">Regular</option>
                    <option value="Medium">Medium</option>
                    <option value="Bold">Bold</option>
                  </select>
                </Field>
                <Field label="主标题字号">
                  <input
                    type="number"
                    value={payload.typography.title_size}
                    onChange={(e) => setTypo("title_size", Number(e.target.value))}
                  />
                </Field>
                <Field label="正文字号">
                  <input
                    type="number"
                    value={payload.typography.body_size}
                    onChange={(e) => setTypo("body_size", Number(e.target.value))}
                  />
                </Field>
                <Field label={`行距 · ${payload.typography.line_height}`}>
                  <input
                    max={3}
                    min={0.8}
                    step={0.1}
                    type="range"
                    value={payload.typography.line_height}
                    onChange={(e) => setTypo("line_height", Number(e.target.value))}
                  />
                </Field>
                <Field label="文字颜色">
                  <input
                    className="color"
                    type="color"
                    value={payload.typography.text_color}
                    onChange={(e) => setTypo("text_color", e.target.value)}
                  />
                </Field>
              </div>
              <label className="switch">
                <input
                  checked={payload.typography.lock_brand_typography}
                  type="checkbox"
                  onChange={(e) => setTypo("lock_brand_typography", e.target.checked)}
                />
                <span className="switch-track" />
                严格锁定品牌字体规范
              </label>
            </Section>

            <Section title="Layout Engine 参数" description="画布、标准模块与配色" icon={<Palette size={16} />}>
              <div className="grid-2">
                <Field label="画布宽度">
                  <input
                    type="number"
                    value={payload.layout.canvas_width}
                    onChange={(e) => setLayout("canvas_width", Number(e.target.value))}
                  />
                </Field>
                <Field label={`模块数量 · ${payload.layout.module_count}`}>
                  <input
                    max={12}
                    min={1}
                    type="range"
                    value={payload.layout.module_count}
                    onChange={(e) => setLayout("module_count", Number(e.target.value))}
                  />
                </Field>
                <Field label="主视觉高度">
                  <input
                    type="number"
                    value={payload.layout.hero_height}
                    onChange={(e) => setLayout("hero_height", Number(e.target.value))}
                  />
                </Field>
                <Field label="普通模块高度">
                  <input
                    type="number"
                    value={payload.layout.module_height}
                    onChange={(e) => setLayout("module_height", Number(e.target.value))}
                  />
                </Field>
                <Field label="背景色">
                  <input
                    className="color"
                    type="color"
                    value={payload.layout.background_color}
                    onChange={(e) => setLayout("background_color", e.target.value)}
                  />
                </Field>
                <Field label="强调色">
                  <input
                    className="color"
                    type="color"
                    value={payload.layout.accent_color}
                    onChange={(e) => setLayout("accent_color", e.target.value)}
                  />
                </Field>
              </div>
            </Section>

            <Section
              title="结构化需求约束"
              description="让生成优先遵守你的模块顺序、视觉要求和历史反馈"
              icon={<ClipboardCheck size={16} />}
            >
              <div className="grid-2">
                <Field label="偏好模块顺序（每行一个，如 Hero / Scenario / CTA）">
                  <textarea
                    value={joinLines(payload.requirement_constraints.preferred_module_order)}
                    onChange={(e) =>
                      setRequirementConstraint(
                        "preferred_module_order",
                        splitLines(e.target.value),
                      )
                    }
                  />
                </Field>
                <Field label="必须保留的模块（每行一个）">
                  <textarea
                    value={joinLines(payload.requirement_constraints.required_modules)}
                    onChange={(e) =>
                      setRequirementConstraint("required_modules", splitLines(e.target.value))
                    }
                  />
                </Field>
                <Field label="禁止出现的模块（每行一个）">
                  <textarea
                    value={joinLines(payload.requirement_constraints.forbidden_modules)}
                    onChange={(e) =>
                      setRequirementConstraint("forbidden_modules", splitLines(e.target.value))
                    }
                  />
                </Field>
                <Field label="参考对齐说明">
                  <textarea
                    value={payload.requirement_constraints.reference_alignment}
                    onChange={(e) =>
                      setRequirementConstraint("reference_alignment", e.target.value)
                    }
                  />
                </Field>
                <Field label="布局约束（每行一个）">
                  <textarea
                    value={joinLines(payload.requirement_constraints.layout_constraints)}
                    onChange={(e) =>
                      setRequirementConstraint("layout_constraints", splitLines(e.target.value))
                    }
                  />
                </Field>
                <Field label="视觉约束（每行一个）">
                  <textarea
                    value={joinLines(payload.requirement_constraints.visual_constraints)}
                    onChange={(e) =>
                      setRequirementConstraint("visual_constraints", splitLines(e.target.value))
                    }
                  />
                </Field>
                <Field label="文案约束（每行一个）">
                  <textarea
                    value={joinLines(payload.requirement_constraints.copy_constraints)}
                    onChange={(e) =>
                      setRequirementConstraint("copy_constraints", splitLines(e.target.value))
                    }
                  />
                </Field>
                <Field label="素材约束（每行一个）">
                  <textarea
                    value={joinLines(payload.requirement_constraints.asset_constraints)}
                    onChange={(e) =>
                      setRequirementConstraint("asset_constraints", splitLines(e.target.value))
                    }
                  />
                </Field>
                <Field label="负面约束 / 禁止项（每行一个）">
                  <textarea
                    value={joinLines(payload.requirement_constraints.negative_constraints)}
                    onChange={(e) =>
                      setRequirementConstraint("negative_constraints", splitLines(e.target.value))
                    }
                  />
                </Field>
                <Field label="反馈约束来源">
                  <select
                    value={payload.requirement_constraints.feedback_scope}
                    onChange={(e) =>
                      setRequirementConstraint(
                        "feedback_scope",
                        e.target.value as RequirementConstraints["feedback_scope"],
                      )
                    }
                  >
                    <option value="none">不注入历史反馈</option>
                    <option value="same_product">注入同品牌同商品历史反馈</option>
                    <option value="same_brand">注入同品牌最近反馈</option>
                    <option value="run">仅注入指定 Run ID 反馈</option>
                  </select>
                </Field>
                <Field label="反馈 Run ID（可选）">
                  <input
                    value={payload.requirement_constraints.feedback_run_id ?? ""}
                    placeholder="指定历史 run_id 时填写"
                    onChange={(e) =>
                      setRequirementConstraint(
                        "feedback_run_id",
                        e.target.value.trim() || null,
                      )
                    }
                  />
                </Field>
              </div>
              <label className="switch">
                <input
                  checked={payload.requirement_constraints.apply_feedback_constraints}
                  type="checkbox"
                  onChange={(e) =>
                    setRequirementConstraint("apply_feedback_constraints", e.target.checked)
                  }
                />
                <span className="switch-track" />
                将历史反馈自动转成下一次生成约束
              </label>
              <p className="hint">
                `strict_brand` 模式下，如果结构化约束与已选规则冲突，系统会直接报错，不再静默回退到默认模板。
              </p>
            </Section>

            <Section
              title="Agent 提示词"
              description="品牌知识库、页面规划、Layout 与设计稿生成提示词"
              icon={<Boxes size={16} />}
            >
              {(Object.keys(payload.prompts) as Array<keyof AgentPrompts>).map((key) => (
                <Field label={PROMPT_LABELS[key]} key={key}>
                  <textarea
                    className="prompt"
                    value={payload.prompts[key]}
                    onChange={(e) => setPrompt(key, e.target.value)}
                  />
                </Field>
              ))}
            </Section>
          </div>

          <div className="actions">
            <button
              className="btn ghost"
              type="button"
              onClick={() => {
                setResult(null);
                setError(null);
                skipNextDraftSave.current = true;
                setSelectedCoreRuleId("");
                setSelectedDetailPageRuleId("");
                window.localStorage.removeItem(WORKFLOW_DRAFT_KEY);
                setDraftMessage("草稿已清空，将使用默认配置");
                fetchDefaults().then((d) => setPayload(d.payload)).catch(() => {});
              }}
            >
              <RefreshCw size={15} /> 重置
            </button>
            <button
              className={`btn ${loading ? "danger" : "primary"}`}
              type="button"
              onClick={loading ? handleCancel : handleGenerate}
            >
              {loading ? (
                cancelling ? (
                  <Loader2 className="spin" size={16} />
                ) : (
                  <XCircle size={16} />
                )
              ) : (
                <Sparkles size={16} />
              )}
              {loading ? (cancelling ? "正在结束…" : "结束生成") : "运行 BrandOS 任务"}
            </button>
          </div>
        </section>

        <aside className="panel result-panel">
          <div className="panel-header">
            <div className="panel-title">
              <Sparkles size={18} /> 生成结果
            </div>
            {result ? (
              <span className={`pill ${result.used_deepagents ? "pill-on" : "pill-off"}`}>
                {result.used_deepagents ? "模型链路" : "规则链路"}
              </span>
            ) : null}
          </div>

          <div className="panel-scroll">
            {error ? <div className="error">{error}</div> : null}

            {!result && !error && !loading ? (
              <div className="placeholder">
                <Sparkles size={28} />
                <p>
                  配置好参数后点击「运行 BrandOS 任务」，这里会显示品牌规则、页面结构、
                  详情页预览图、设计评分和可下载的设计 JSON / Figma 脚本 / PSD 脚本。
                </p>
              </div>
            ) : null}

            {loading ? (
              <div className="placeholder">
                <Loader2 className="spin" size={28} />
                <p>正在依次执行商品理解 → 品牌知识库 → 页面规划 → 图片生成 → Layout → Figma/PSD → 评分反馈…</p>
              </div>
            ) : null}

            {loading && timelineStages.length ? (
              <div className="stages-card live-stages-card">
                <div className="card-label">Agent 执行时间线（实时）</div>
                <StageTimeline stages={timelineStages} />
              </div>
            ) : null}

            {(loading || workflowLogs.length > 0) && selectedStageId ? (
              <div className="log-card">
                <div className="card-label">
                  {selectedStage?.title ?? "阶段"} 日志
                  <span className="log-status">任务状态：{workflowLogStatus}</span>
                </div>
                <pre className="workflow-log">
                  {workflowLogs.length
                    ? workflowLogs.join("\n\n")
                    : "等待后台日志写入..."}
                </pre>
              </div>
            ) : null}

            {result ? (
              <div className="result">
                <p className="result-summary">{result.summary}</p>
                {workflowFailureReason ? <div className="error">故障分类：{workflowFailureReason}</div> : null}
                {result.artifacts.export_status ? (
                  <p className="hint">
                    导出状态：{result.artifacts.export_status}
                    {result.artifacts.export_mode ? ` / ${result.artifacts.export_mode}` : ""}
                    {result.artifacts.export_error ? ` / ${result.artifacts.export_error}` : ""}
                  </p>
                ) : null}

                <div className="downloads">
                  <a
                    className="download"
                    href={artifactUrl(result.run_id, "preview.svg")}
                    rel="noreferrer"
                    target="_blank"
                  >
                    <ImageIcon size={14} /> 预览 SVG
                  </a>
                  <a
                    className="download"
                    href={artifactUrl(result.run_id, "design_spec.json")}
                    rel="noreferrer"
                    target="_blank"
                  >
                    <Download size={14} /> 设计 JSON
                  </a>
                  <a
                    className="download"
                    href={artifactUrl(result.run_id, "create_detail_page.jsx")}
                    rel="noreferrer"
                    target="_blank"
                  >
                    <Download size={14} /> PSD 兼容 JSX
                  </a>
                  {result.artifacts.figma_url ? (
                    <a
                      className="download"
                      href={result.artifacts.figma_url}
                      rel="noreferrer"
                      target="_blank"
                    >
                      <Download size={14} /> 打开 Figma 页面
                    </a>
                  ) : (
                    <a
                      className="download"
                      href={artifactUrl(result.run_id, "create_figma_page.ts")}
                      rel="noreferrer"
                      target="_blank"
                    >
                      <Download size={14} /> Figma 插件 TS
                    </a>
                  )}
                  <a
                    className="download"
                    href={artifactUrl(result.run_id, "editable_detail_page.html")}
                    rel="noreferrer"
                    target="_blank"
                  >
                    <FileText size={14} /> 可编辑 HTML
                  </a>
                  <a
                    className="download"
                    href={artifactUrl(result.run_id, "README.md")}
                    rel="noreferrer"
                    target="_blank"
                  >
                    <FileText size={14} /> README
                  </a>
                  <a className="download" href={`/design-tasks/${result.run_id}`}>
                    <BookOpen size={14} /> 任务详情
                  </a>
                </div>

                <div className="result-grid">
                  <div className="preview-card">
                    <div className="card-label">详情页结构预览</div>
                    {previewUrl ? (
                      <iframe className="preview-frame" src={previewUrl} title="详情页预览" />
                    ) : null}
                  </div>
                  <div className="stages-card">
                    <div className="card-label">Agent 执行时间线</div>
                    <StageTimeline stages={timelineStages} />
                  </div>
                </div>

                {result.warnings.length ? (
                  <details className="warnings">
                    <summary>降级 / 提示信息（{result.warnings.length}）</summary>
                    <pre>{result.warnings.join("\n")}</pre>
                  </details>
                ) : null}

                <div className="feedback-card">
                  <div className="card-label">设计反馈沉淀</div>
                  <p className="hint">
                    只记录设计师修改与审核意见，不自动强化学习、不自动覆盖品牌规则。
                  </p>
                  <div className="grid-2">
                    <Field label="记录人">
                      <input
                        value={feedbackAuthor}
                        onChange={(event) => setFeedbackAuthor(event.target.value)}
                      />
                    </Field>
                    <Field label="反馈类型">
                      <input disabled value="designer_edit" />
                    </Field>
                  </div>
                  <textarea
                    className="feedback-textarea"
                    placeholder="例如：首屏标题缩小到 44px；第三屏图片改为正面细节；CTA 颜色降低饱和度。"
                    value={feedbackNotes}
                    onChange={(event) => setFeedbackNotes(event.target.value)}
                  />
                  <div className="split-line">
                    <span className="hint">已记录 {feedbackItems.length} 条反馈</span>
                    <button
                      className="btn ghost"
                      disabled={feedbackSaving || !feedbackNotes.trim()}
                      type="button"
                      onClick={handleSaveFeedback}
                    >
                      {feedbackSaving ? "保存中..." : "保存反馈"}
                    </button>
                  </div>
                  {feedbackItems.length ? (
                    <div className="record-list">
                      {feedbackItems.slice(0, 3).map((item) => (
                        <div className="record-item" key={item.id}>
                          <strong>{item.author}</strong>
                          <div className="subtitle">{item.notes}</div>
                        </div>
                      ))}
                    </div>
                  ) : null}
                </div>
              </div>
            ) : null}
          </div>
        </aside>
        </div>
      ) : (
        <ModelTestPanel />
      )}
    </main>
  );
}

function OverviewCard({
  icon,
  label,
  title,
  text,
}: {
  icon: React.ReactNode;
  label: string;
  title: string;
  text: string;
}) {
  return (
    <article className="overview-card">
      <div className="overview-icon">{icon}</div>
      <div>
        <div className="overview-label">{label}</div>
        <div className="overview-title">{title}</div>
        <p>{text}</p>
      </div>
    </article>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="field">
      <span className="field-label">{label}</span>
      {children}
    </div>
  );
}
