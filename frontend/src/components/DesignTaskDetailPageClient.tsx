"use client";

import { Download, FileText, Image as ImageIcon, RefreshCw } from "lucide-react";
import { useMemo, useState } from "react";
import {
  artifactUrl,
  createWorkflowFeedback,
  type ExportPreflight,
  type ExportReview,
  type ResultState,
  type WorkflowDetailResponse,
} from "@/lib/api";
import { StageTimeline } from "./StageTimeline";
import { WorkflowResultStateSummary } from "./WorkflowResultStateSummary";

const WORKFLOW_DRAFT_KEY = "brandos.workflow.createTaskDraft.v1";

function formatTime(value?: string | null) {
  if (!value) return "-";
  return new Date(value).toLocaleString("zh-CN", { hour12: false });
}

function statusClass(status: string) {
  if (status.includes("completed") || status.includes("成功")) return "success";
  if (status.includes("failed") || status.includes("失败") || status.includes("cancelled")) {
    return "failed";
  }
  if (status.includes("fallback")) return "warning";
  return "running";
}

function statusLabel(status: string) {
  const map: Record<string, string> = {
    completed: "生成成功",
    fallback_completed: "待审核",
    failed: "生成失败",
    running: "处理中",
    cancelling: "取消中",
    cancelled: "已取消",
  };
  return map[status] ?? status;
}

function buildArtifactLink(runId: string, absolutePath?: string | null) {
  if (!absolutePath) return "";
  const name = absolutePath.split(/[\\/]/).pop();
  return name ? artifactUrl(runId, name) : "";
}

function readStructuredObject<T>(value: unknown) {
  return value && typeof value === "object" ? (value as T) : null;
}

function exportStatusLabel(status?: string | null) {
  const map: Record<string, string> = {
    completed: "已完成正式导出",
    script_ready: "脚本导出就绪",
    review_only_bundle: "仅输出审稿包",
    blocked_review_bundle: "导出已阻断",
  };
  return map[status ?? ""] ?? (status || "-");
}

export function DesignTaskDetailPageClient({ initialData }: { initialData: WorkflowDetailResponse }) {
  const [feedbackNotes, setFeedbackNotes] = useState("");
  const [feedbackAuthor, setFeedbackAuthor] = useState("designer");
  const [feedbackSaving, setFeedbackSaving] = useState(false);
  const [feedbackItems, setFeedbackItems] = useState(initialData.feedback);
  const [error, setError] = useState<string | null>(null);
  const resultState = useMemo(
    () =>
      initialData.resultState ??
      readStructuredObject<ResultState>(initialData.designSpec?.result_state),
    [initialData.resultState, initialData.designSpec],
  );
  const exportReview = useMemo(
    () =>
      initialData.exportReview ??
      initialData.artifacts?.exportReview ??
      readStructuredObject<ExportReview>(initialData.designSpec?.export_review),
    [initialData.artifacts?.exportReview, initialData.designSpec, initialData.exportReview],
  );
  const exportPreflight = useMemo(
    () =>
      initialData.artifacts?.exportPreflight ??
      resultState?.export_preflight ??
      readStructuredObject<ExportPreflight>(
        readStructuredObject<ResultState>(initialData.designSpec?.result_state)?.export_preflight,
      ) ??
      null,
    [initialData.artifacts?.exportPreflight, initialData.designSpec, resultState],
  );
  const inputLayers = initialData.inputLayers ?? null;

  const previewUrl = useMemo(
    () =>
      initialData.artifacts?.previewSvg
        ? buildArtifactLink(initialData.runId, initialData.artifacts.previewSvg)
        : "",
    [initialData],
  );
  const designSpecUrl = useMemo(
    () =>
      initialData.artifacts?.designSpec
        ? buildArtifactLink(initialData.runId, initialData.artifacts.designSpec)
        : "",
    [initialData],
  );
  const photoshopUrl = useMemo(
    () =>
      initialData.artifacts?.photoshopJsx
        ? buildArtifactLink(initialData.runId, initialData.artifacts.photoshopJsx)
        : "",
    [initialData],
  );
  const figmaScriptUrl = useMemo(
    () =>
      initialData.artifacts?.figmaPlugin
        ? buildArtifactLink(initialData.runId, initialData.artifacts.figmaPlugin)
        : "",
    [initialData],
  );
  const editableHtmlUrl = useMemo(
    () =>
      initialData.artifacts?.editableHtml
        ? buildArtifactLink(initialData.runId, initialData.artifacts.editableHtml)
        : "",
    [initialData],
  );
  const readmeUrl = useMemo(
    () =>
      initialData.artifacts?.readme
        ? buildArtifactLink(initialData.runId, initialData.artifacts.readme)
        : "",
    [initialData],
  );
  const outputMetadataUrl = useMemo(
    () =>
      initialData.artifacts?.outputMetadata
        ? buildArtifactLink(initialData.runId, initialData.artifacts.outputMetadata)
        : "",
    [initialData],
  );

  const handleSaveFeedback = async () => {
    if (!feedbackNotes.trim()) return;
    setFeedbackSaving(true);
    setError(null);
    try {
      const item = await createWorkflowFeedback({
        runId: initialData.runId,
        feedbackType: "designer_edit",
        author: feedbackAuthor,
        changes: [
          {
            type: "notes",
            source: "task_detail",
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

  const handleReuseConfig = () => {
    try {
      const payload = initialData.requestPayload ?? {};
      window.localStorage.setItem(
        WORKFLOW_DRAFT_KEY,
        JSON.stringify({
          payload,
          selectedCoreRuleId:
            typeof payload.selected_core_rule_id === "number" ? payload.selected_core_rule_id : "",
          selectedDetailPageRuleId:
            typeof payload.selected_detail_page_rule_id === "number"
              ? payload.selected_detail_page_rule_id
              : "",
          updatedAt: new Date().toISOString(),
        }),
      );
      window.location.href = "/create-task";
    } catch (err) {
      setError(err instanceof Error ? err.message : "复制配置失败");
    }
  };

  return (
    <div className="data-page">
      <div className="topbar">
        <div className="topbar-left">
          <h1>{initialData.productName || initialData.taskCode}</h1>
          <div className="subtitle">
            {initialData.brandName} / {initialData.taskType} / {initialData.taskCode}
          </div>
        </div>
        <div className="topbar-right">
          <button className="btn ghost" type="button" onClick={handleReuseConfig}>
            <RefreshCw size={14} />
            复制配置到创建设计任务
          </button>
        </div>
      </div>

      <section className="summary-grid">
        <article className="info-card">
          <div className="eyebrow">任务状态</div>
          <div className={`status-pill ${statusClass(initialData.status)}`}>{statusLabel(initialData.status)}</div>
          <div className="muted-text">{initialData.summary || "暂无摘要"}</div>
        </article>
        <article className="info-card">
          <div className="eyebrow">创建时间</div>
          <div className="big-metric detail-metric">{formatTime(initialData.createdAt)}</div>
          <div className="muted-text">任务发起时间</div>
        </article>
        <article className="info-card">
          <div className="eyebrow">完成时间</div>
          <div className="big-metric detail-metric">{formatTime(initialData.completedAt)}</div>
          <div className="muted-text">任务完成或终止时间</div>
        </article>
        <article className="info-card">
          <div className="eyebrow">结果等级</div>
          <div className="big-metric detail-metric">{String(resultState?.tier || "-")}</div>
          <div className="muted-text">
            {resultState?.delivery_status ? `交付判定：${String(resultState.delivery_status)}` : "暂无"}
            {resultState?.error_code ? ` / ${String(resultState.error_code)}` : ""}
          </div>
        </article>
      </section>

      {initialData.failureReason ? (
        <section className="panel content-panel">
          <div className="error">故障分类：{initialData.failureReason}</div>
        </section>
      ) : null}

      {initialData.warnings.length ? (
        <section className="panel content-panel">
          <details className="warnings" open>
            <summary>降级 / 提示信息（{initialData.warnings.length}）</summary>
            <pre>{initialData.warnings.join("\n")}</pre>
          </details>
        </section>
      ) : null}

      {error ? (
        <section className="panel content-panel">
          <div className="error">{error}</div>
        </section>
      ) : null}

      <WorkflowResultStateSummary
        exportPreflight={exportPreflight}
        exportReview={exportReview}
        resultState={resultState}
      />

      <section className="panel content-panel">
        <div className="card-label">导出产物</div>
        <p className="hint">
          导出状态：{exportStatusLabel(initialData.artifacts?.exportStatus)}
          {initialData.artifacts?.exportMode ? ` / ${initialData.artifacts.exportMode}` : ""}
          {initialData.artifacts?.exportError ? ` / ${initialData.artifacts.exportError}` : ""}
        </p>
        {exportReview?.message ? (
          <p className="hint">
            导出建议：{String(exportReview.message)}
            {Array.isArray(exportReview.recommended_actions) && exportReview.recommended_actions.length
              ? ` / 下一步：${String(exportReview.recommended_actions[0])}`
              : ""}
          </p>
        ) : null}
        <div className="downloads">
          {previewUrl ? (
            <a className="download" href={previewUrl} rel="noreferrer" target="_blank">
              <ImageIcon size={14} /> 预览 SVG
            </a>
          ) : null}
          {designSpecUrl ? (
            <a className="download" href={designSpecUrl} rel="noreferrer" target="_blank">
              <Download size={14} /> 设计 JSON
            </a>
          ) : null}
          {initialData.artifacts?.figmaUrl ? (
            <a className="download" href={initialData.artifacts.figmaUrl} rel="noreferrer" target="_blank">
              <Download size={14} /> 打开 Figma 页面
            </a>
          ) : figmaScriptUrl ? (
            <a className="download" href={figmaScriptUrl} rel="noreferrer" target="_blank">
              <Download size={14} /> Figma 插件 TS
            </a>
          ) : null}
          {photoshopUrl ? (
            <a className="download" href={photoshopUrl} rel="noreferrer" target="_blank">
              <Download size={14} /> PSD 兼容 JSX
            </a>
          ) : null}
          {editableHtmlUrl ? (
            <a className="download" href={editableHtmlUrl} rel="noreferrer" target="_blank">
              <FileText size={14} /> 可编辑 HTML
            </a>
          ) : null}
          {readmeUrl ? (
            <a className="download" href={readmeUrl} rel="noreferrer" target="_blank">
              <FileText size={14} /> README
            </a>
          ) : null}
          {outputMetadataUrl ? (
            <a className="download" href={outputMetadataUrl} rel="noreferrer" target="_blank">
              <Download size={14} /> 输出元数据
            </a>
          ) : null}
        </div>
      </section>

      <div className="result-grid">
        <section className="preview-card">
          <div className="card-label">详情页结构预览</div>
          {previewUrl ? (
            <iframe className="preview-frame" src={previewUrl} title="详情页预览" />
          ) : (
            <div className="placeholder">
              <p>当前任务没有预览产物。</p>
            </div>
          )}
        </section>
        <section className="stages-card">
          <div className="card-label">Agent 执行时间线</div>
          {resultState ? (
            <p className="hint">
              布局校验：{String(resultState.layout_validation_status || "-")} / Asset Guard：
              {String(resultState.asset_guard_status || "-")}
              {typeof resultState.slot_match_rate === "number"
                ? ` / 槽位命中率：${Math.round(Number(resultState.slot_match_rate) * 100)}%`
                : ""}
            </p>
          ) : null}
          <StageTimeline stages={initialData.stages} />
        </section>
      </div>

      <div className="detail-grid">
        <section className="log-card">
          <div className="card-label">任务日志</div>
          <pre className="workflow-log">
            {initialData.logs.length
              ? initialData.logs.map((item) => item.message).join("\n\n")
              : "当前没有日志。"}
          </pre>
        </section>
        <section className="log-card">
          <div className="card-label">输入快照</div>
          <pre className="workflow-log">{JSON.stringify(initialData.requestPayload, null, 2)}</pre>
        </section>
      </div>

      {inputLayers ? (
        <section className="panel content-panel">
          <div className="card-label">输入分层</div>
          <p className="hint">
            来源：{inputLayers.source} / brief 资产：{inputLayers.brief_asset_count} / wireframe 资产：
            {inputLayers.wireframe_asset_count}
            {inputLayers.raw_wireframe_dump_truncated
              ? ` / raw dump 已裁剪（原始 ${inputLayers.raw_wireframe_dump_chars} 字符）`
              : ""}
          </p>
          {inputLayers.brief_summary ? (
            <details open>
              <summary>brief_summary</summary>
              <pre className="workflow-log">{inputLayers.brief_summary}</pre>
            </details>
          ) : null}
          {inputLayers.layout_reference ? (
            <details open>
              <summary>layout_reference</summary>
              <pre className="workflow-log">{inputLayers.layout_reference}</pre>
            </details>
          ) : null}
          {inputLayers.raw_wireframe_dump ? (
            <details>
              <summary>raw_wireframe_dump</summary>
              <pre className="workflow-log">{inputLayers.raw_wireframe_dump}</pre>
            </details>
          ) : null}
        </section>
      ) : null}

      <section className="panel content-panel">
        <div className="card-label">设计反馈沉淀</div>
        <p className="hint">支持在历史任务上继续记录反馈，并复用到下一次创建设计任务。</p>
        <div className="grid-2">
          <div className="field">
            <span className="field-label">记录人</span>
            <input value={feedbackAuthor} onChange={(event) => setFeedbackAuthor(event.target.value)} />
          </div>
          <div className="field">
            <span className="field-label">反馈类型</span>
            <input disabled value="designer_edit" />
          </div>
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
            {feedbackItems.map((item) => (
              <div className="record-item" key={item.id}>
                <strong>{item.author}</strong>
                <div className="subtitle">{item.notes}</div>
                <div className="subtitle">{formatTime(item.createdAt)}</div>
              </div>
            ))}
          </div>
        ) : null}
      </section>
    </div>
  );
}
