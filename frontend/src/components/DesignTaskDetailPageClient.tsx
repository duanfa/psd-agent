"use client";

import { Download, FileText, Image as ImageIcon, RefreshCw } from "lucide-react";
import { useMemo, useState } from "react";
import {
  artifactUrl,
  createWorkflowFeedback,
  type WorkflowDetailResponse,
} from "@/lib/api";
import { StageTimeline } from "./StageTimeline";

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

export function DesignTaskDetailPageClient({ initialData }: { initialData: WorkflowDetailResponse }) {
  const [feedbackNotes, setFeedbackNotes] = useState("");
  const [feedbackAuthor, setFeedbackAuthor] = useState("designer");
  const [feedbackSaving, setFeedbackSaving] = useState(false);
  const [feedbackItems, setFeedbackItems] = useState(initialData.feedback);
  const [error, setError] = useState<string | null>(null);

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
          <div className="eyebrow">导出模式</div>
          <div className="big-metric detail-metric">{initialData.artifacts?.exportMode || "script"}</div>
          <div className="muted-text">
            {initialData.artifacts?.exportStatus || "fallback_script"}
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

      <section className="panel content-panel">
        <div className="card-label">导出产物</div>
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
