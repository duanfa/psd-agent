"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Download, FileText, Image as ImageIcon, Loader2, Sparkles, XCircle } from "lucide-react";
import {
  artifactUrl,
  cancelWorkflow,
  fetchBrandDetails,
  fetchDefaults,
  fetchRuleVersions,
  fetchRuns,
  fetchWorkflowLogs,
  generateWorkflow,
  type BrandRuleVersionRecord,
  type WorkflowPayload,
  type WorkflowResult,
  type WorkflowRunRecord,
} from "@/lib/api";
import { FALLBACK_STAGES } from "@/lib/stages";
import { AppShell } from "./AppShell";
import { useBrandSelection } from "./useBrandSelection";
import { EmptyState, PageSection, StatusBadge } from "./ui";
import { PipelineRibbon } from "../PipelineRibbon";
import { StageTimeline } from "../StageTimeline";

const OUTPUT_OPTIONS: Array<{ value: "detail_page" | "figma_page" | "psd_file"; label: string }> = [
  { value: "detail_page", label: "详情页" },
  { value: "figma_page", label: "Figma 页面" },
  { value: "psd_file", label: "PSD 兼容文件" },
];

export function CreateTaskPage() {
  const {
    brands,
    selectedBrand,
    selectedBrandId,
    loading,
    error,
    setSelectedBrandId,
    buildHref,
  } = useBrandSelection();
  const [payload, setPayload] = useState<WorkflowPayload | null>(null);
  const [ruleVersions, setRuleVersions] = useState<BrandRuleVersionRecord[]>([]);
  const [selectedRuleVersionId, setSelectedRuleVersionId] = useState<string | null>(null);
  const [historyRuns, setHistoryRuns] = useState<WorkflowRunRecord[]>([]);
  const [result, setResult] = useState<WorkflowResult | null>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [briefFiles, setBriefFiles] = useState<File[]>([]);
  const [referenceImages, setReferenceImages] = useState<File[]>([]);
  const [step, setStep] = useState(1);
  const [pageLoading, setPageLoading] = useState(true);
  const [taskLoading, setTaskLoading] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [currentRunId, setCurrentRunId] = useState<string | null>(null);
  const [workflowLogs, setWorkflowLogs] = useState<string[]>([]);
  const [workflowStatus, setWorkflowStatus] = useState("idle");
  const [currentStageId, setCurrentStageId] = useState<string | null>(null);
  const [liveStages, setLiveStages] = useState<WorkflowResult["stages"]>([]);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const loadDefaults = async () => {
      setPageLoading(true);
      try {
        const defaults = await fetchDefaults();
        if (!cancelled) {
          setPayload(defaults.payload);
        }
      } catch (err) {
        if (!cancelled) {
          setErrorMessage(err instanceof Error ? err.message : String(err));
        }
      } finally {
        if (!cancelled) setPageLoading(false);
      }
    };
    void loadDefaults();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!selectedBrandId || !payload) return;
    let cancelled = false;
    const loadBrandContext = async () => {
      try {
        const [detail, versions, runs] = await Promise.all([
          fetchBrandDetails(selectedBrandId),
          fetchRuleVersions(selectedBrandId),
          fetchRuns(selectedBrandId),
        ]);
        if (cancelled) return;
        const defaultRule = detail.current_rule_version?.id ?? versions[0]?.id ?? null;
        setRuleVersions(versions);
        setSelectedRuleVersionId(defaultRule);
        setHistoryRuns(runs.slice(0, 5));
        setPayload((current) =>
          current
            ? {
                ...current,
                brand_id: selectedBrandId,
                brand_name: detail.item.name,
                rule_version_id: defaultRule ?? undefined,
              }
            : current,
        );
      } catch (err) {
        if (!cancelled) {
          setErrorMessage(err instanceof Error ? err.message : String(err));
        }
      }
    };
    void loadBrandContext();
    return () => {
      cancelled = true;
    };
  }, [selectedBrandId, Boolean(payload)]);

  useEffect(() => {
    if (!currentRunId) return;
    let stopped = false;
    const loadLogs = async () => {
      try {
        const snapshot = await fetchWorkflowLogs(currentRunId);
        if (stopped) return;
        setWorkflowLogs(snapshot.logs);
        setLiveStages(snapshot.stages);
        setWorkflowStatus(snapshot.status);
        setCurrentStageId(snapshot.current_stage ?? null);
      } catch {
        // 日志轮询失败不影响主流程。
      }
    };
    void loadLogs();
    const timer = window.setInterval(loadLogs, 800);
    return () => {
      stopped = true;
      window.clearInterval(timer);
    };
  }, [currentRunId]);

  const setField = <K extends keyof WorkflowPayload>(key: K, value: WorkflowPayload[K]) =>
    setPayload((current) => (current ? { ...current, [key]: value } : current));

  const toggleOutput = (value: "detail_page" | "figma_page" | "psd_file") => {
    setPayload((current) => {
      if (!current) return current;
      return {
        ...current,
        output_types: current.output_types.includes(value)
          ? current.output_types.filter((item) => item !== value)
          : [...current.output_types, value],
      };
    });
  };

  const timelineStages = useMemo(
    () => (taskLoading || liveStages.length ? liveStages : result?.stages ?? []),
    [liveStages, result, taskLoading],
  );

  const previewUrl = result ? artifactUrl(result.run_id, "preview.svg") : null;

  const handleSubmit = async () => {
    if (!payload) return;
    const runId = crypto.randomUUID();
    const nextPayload = {
      ...payload,
      brand_id: selectedBrandId ?? payload.brand_id,
      rule_version_id: selectedRuleVersionId ?? undefined,
    };
    setPayload(nextPayload);
    setTaskLoading(true);
    setCancelling(false);
    setCurrentRunId(runId);
    setWorkflowLogs([]);
    setLiveStages([]);
    setCurrentStageId(null);
    setWorkflowStatus("running");
    setErrorMessage(null);
    setResult(null);
    try {
      const workflowResult = await generateWorkflow(nextPayload, files, runId, briefFiles, referenceImages);
      setResult(workflowResult);
      if (selectedBrandId) {
        setHistoryRuns((await fetchRuns(selectedBrandId)).slice(0, 5));
      }
      setStep(4);
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : String(err));
    } finally {
      setTaskLoading(false);
      setCancelling(false);
      setCurrentRunId(null);
    }
  };

  const handleCancel = async () => {
    if (!currentRunId || cancelling) return;
    setCancelling(true);
    try {
      await cancelWorkflow(currentRunId);
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : String(err));
    }
  };

  if (!payload) {
    return (
      <AppShell
        title="创建设计任务"
        subtitle="选择品牌和商品，配置生成参数后开始生成详情页"
        brands={brands}
        selectedBrand={selectedBrand}
        selectedBrandId={selectedBrandId}
        loadingBrands={loading}
        onBrandChange={setSelectedBrandId}
        buildHref={buildHref}
      >
        <div className="biz-loading">{pageLoading ? "正在加载任务配置..." : "任务配置加载失败"}</div>
      </AppShell>
    );
  }

  return (
    <AppShell
      title="创建设计任务"
      subtitle="选择品牌和商品，配置生成参数后开始生成详情页"
      brands={brands}
      selectedBrand={selectedBrand}
      selectedBrandId={selectedBrandId}
      loadingBrands={loading}
      onBrandChange={setSelectedBrandId}
      buildHref={buildHref}
      headerActions={<StatusBadge value={taskLoading ? "running" : "queued"} />}
    >
      {error || errorMessage ? <div className="error">{error ?? errorMessage}</div> : null}

      <section className="biz-steps">
        {["1 选择品牌", "2 选择商品", "3 配置任务", "4 确认提交"].map((label, index) => (
          <div className={`biz-step ${step === index + 1 ? "biz-step-active" : ""}`} key={label}>
            {label}
          </div>
        ))}
      </section>

      <PageSection title="基础信息" subtitle="任务创建的必要输入">
        <div className="biz-form-grid">
          <label className="field">
            <span className="field-label">所属品牌</span>
            <select value={selectedBrandId ?? ""} onChange={(event) => setSelectedBrandId(event.target.value)}>
              {brands.map((brand) => (
                <option key={brand.id} value={brand.id}>
                  {brand.name}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span className="field-label">关联商品</span>
            <input
              value={payload.product_name}
              placeholder="请输入商品名称"
              onChange={(event) => setField("product_name", event.target.value)}
            />
          </label>
          <label className="field">
            <span className="field-label">任务类型</span>
            <select
              value={payload.workflow_mode}
              onChange={(event) =>
                setField("workflow_mode", event.target.value as WorkflowPayload["workflow_mode"])
              }
            >
              <option value="smart_recommend">智能推荐模式</option>
              <option value="strict_brand">严格品牌规范模式</option>
            </select>
          </label>
          <label className="field">
            <span className="field-label">页面风格偏向</span>
            <input
              value={payload.reference_notes}
              placeholder="补充目标人群、使用场景和设计方向"
              onChange={(event) => setField("reference_notes", event.target.value)}
            />
          </label>
          <label className="field field-full">
            <span className="field-label">商品 Brief</span>
            <textarea
              value={payload.product_brief}
              placeholder="补充目标人群、使用场景和设计方向"
              onChange={(event) => setField("product_brief", event.target.value)}
            />
          </label>
        </div>
      </PageSection>

      <div className="biz-two-column">
        <PageSection title="生成配置" subtitle="任务级控制项">
          <div className="biz-form-grid">
            <label className="field">
              <span className="field-label">规则版本</span>
              <select
                value={selectedRuleVersionId ?? ""}
                onChange={(event) => {
                  setSelectedRuleVersionId(event.target.value);
                  setField("rule_version_id", event.target.value || undefined);
                }}
              >
                {ruleVersions.map((version) => (
                  <option key={version.id} value={version.id}>
                    {version.version_label}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span className="field-label">是否开启图片生成</span>
              <select
                value={payload.model_config.enable_vision ? "on" : "off"}
                onChange={(event) =>
                  setPayload((current) =>
                    current
                      ? {
                          ...current,
                          model_config: {
                            ...current.model_config,
                            enable_vision: event.target.value === "on",
                          },
                        }
                      : current,
                  )
                }
              >
                <option value="on">开启</option>
                <option value="off">关闭</option>
              </select>
            </label>
            <label className="field">
              <span className="field-label">输出分辨率</span>
              <input
                value={String(payload.layout.canvas_width)}
                onChange={(event) =>
                  setPayload((current) =>
                    current
                      ? {
                          ...current,
                          layout: { ...current.layout, canvas_width: Number(event.target.value) || 0 },
                        }
                      : current,
                  )
                }
              />
            </label>
            <div className="field">
              <span className="field-label">输出格式</span>
              <div className="biz-chip-row">
                {OUTPUT_OPTIONS.map((option) => (
                  <button
                    className={`biz-chip ${payload.output_types.includes(option.value) ? "biz-chip-active" : ""}`}
                    key={option.value}
                    type="button"
                    onClick={() => toggleOutput(option.value)}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </PageSection>

        <PageSection title="输出设置" subtitle="上传本次任务的输入素材">
          <div className="biz-upload-grid">
            <label className="biz-upload-card">
              <ImageIcon size={16} />
              <strong>商品主图 / 场景图</strong>
              <span>上传商品素材</span>
              <input hidden multiple type="file" onChange={(event) => setFiles(Array.from(event.target.files ?? []))} />
            </label>
            <label className="biz-upload-card">
              <FileText size={16} />
              <strong>商品 Brief</strong>
              <span>上传 Excel / CSV</span>
              <input
                hidden
                multiple
                type="file"
                accept=".xlsx,.xls,.xlsm,.csv"
                onChange={(event) => setBriefFiles(Array.from(event.target.files ?? []))}
              />
            </label>
            <label className="biz-upload-card">
              <ImageIcon size={16} />
              <strong>参考案例</strong>
              <span>上传参考页面图片</span>
              <input
                hidden
                multiple
                type="file"
                accept="image/*"
                onChange={(event) => setReferenceImages(Array.from(event.target.files ?? []))}
              />
            </label>
          </div>
          <div className="biz-file-summary">
            <span>素材 {files.length} 个</span>
            <span>Brief {briefFiles.length} 个</span>
            <span>参考图 {referenceImages.length} 个</span>
          </div>
          <p className="hint">任务提交后将进入异步执行，请在任务中心查看进度。</p>
        </PageSection>
      </div>

      <PageSection title="确认信息" subtitle="提交前再次确认本次任务输入">
        <div className="biz-confirm-card">
          <div>所属品牌：{selectedBrand?.name ?? "-"}</div>
          <div>关联商品：{payload.product_name || "未填写"}</div>
          <div>任务类型：{payload.workflow_mode}</div>
          <div>规则版本：{selectedRuleVersionId ?? "未选择"}</div>
        </div>
        <div className="biz-submit-row">
          <button className="btn ghost" type="button" onClick={() => setStep((current) => Math.max(1, current - 1))}>
            上一步
          </button>
          <button className="btn ghost" type="button" onClick={() => setStep((current) => Math.min(4, current + 1))}>
            下一步
          </button>
          <button className="btn primary" type="button" onClick={() => void handleSubmit()} disabled={taskLoading}>
            {taskLoading ? <Loader2 className="spin" size={14} /> : <Sparkles size={14} />}
            创建任务
          </button>
          <button className="btn ghost" type="button" disabled={!taskLoading} onClick={() => void handleCancel()}>
            {cancelling ? <Loader2 className="spin" size={14} /> : <XCircle size={14} />}
            取消
          </button>
        </div>
      </PageSection>

      <PageSection title="执行进度" subtitle="实时查看阶段状态和任务日志">
        <PipelineRibbon
          stages={FALLBACK_STAGES}
          results={timelineStages}
          running={taskLoading}
          currentStageId={currentStageId}
          selectedStageId={currentStageId}
        />
        {timelineStages.length ? <StageTimeline stages={timelineStages} /> : null}
        {(taskLoading || workflowLogs.length > 0) && (
          <div className="biz-code-block">
            <pre>{workflowLogs.length ? workflowLogs.join("\n\n") : "等待后台日志写入..."}</pre>
          </div>
        )}
        <div className="biz-list-meta">当前任务状态：{workflowStatus}</div>
      </PageSection>

      <div className="biz-two-column">
        <PageSection title="最近设计任务" subtitle="快速回看同品牌最近生成">
          {!historyRuns.length ? (
            <EmptyState title="当前还没有设计任务" description="去创建第一个任务。" />
          ) : (
            <div className="biz-list">
              {historyRuns.map((run) => (
                <article className="biz-list-card" key={run.id}>
                  <div className="biz-list-card-head">
                    <div>
                      <div className="biz-list-title">{run.project_name || run.product_name}</div>
                      <div className="biz-list-meta">{run.product_name}</div>
                    </div>
                    <StatusBadge value={run.status} />
                  </div>
                  <Link className="text-link" href={buildHref(`/tasks/detail?run=${run.id}`)}>
                    查看详情
                  </Link>
                </article>
              ))}
            </div>
          )}
        </PageSection>

        <PageSection title="任务结果" subtitle="生成完成后直接查看产物">
          {!result ? (
            <EmptyState title="暂未生成结果" description="创建任务后，这里会显示页面结构、文案和导出产物。" />
          ) : (
            <div className="biz-result-card">
              <p>{result.summary}</p>
              <div className="biz-inline-actions">
                <a className="btn ghost btn-small" href={artifactUrl(result.run_id, "preview.svg")} target="_blank" rel="noreferrer">
                  预览结果
                </a>
                <a className="btn ghost btn-small" href={artifactUrl(result.run_id, "design_spec.json")} target="_blank" rel="noreferrer">
                  <Download size={14} /> 设计 JSON
                </a>
                <a className="btn ghost btn-small" href={artifactUrl(result.run_id, "create_detail_page.jsx")} target="_blank" rel="noreferrer">
                  导出到 Figma
                </a>
              </div>
              {previewUrl ? <iframe className="preview-frame biz-preview-frame" src={previewUrl} title="结果预览" /> : null}
            </div>
          )}
        </PageSection>
      </div>
    </AppShell>
  );
}
