"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Download, ExternalLink, RefreshCw } from "lucide-react";
import { API_BASE, fetchRun, type WorkflowRunRecord } from "@/lib/api";
import { FALLBACK_STAGES } from "@/lib/stages";
import { formatDateTime } from "@/lib/format";
import { AppShell } from "./AppShell";
import { useBrandSelection } from "./useBrandSelection";
import { EmptyState, PageSection, StatusBadge } from "./ui";
import { PipelineRibbon } from "../PipelineRibbon";
import { StageTimeline } from "../StageTimeline";

export function TaskDetailPage({ runId }: { runId: string }) {
  const {
    brands,
    selectedBrand,
    selectedBrandId,
    loading,
    error,
    setSelectedBrandId,
    buildHref,
  } = useBrandSelection();
  const [run, setRun] = useState<WorkflowRunRecord | null>(null);
  const [pageLoading, setPageLoading] = useState(true);
  const [pageError, setPageError] = useState<string | null>(null);

  const loadRun = async () => {
    setPageLoading(true);
    setPageError(null);
    try {
      setRun(await fetchRun(runId));
    } catch (err) {
      setPageError(err instanceof Error ? err.message : String(err));
    } finally {
      setPageLoading(false);
    }
  };

  useEffect(() => {
    void loadRun();
  }, [runId]);

  const previewUrl = useMemo(
    () => (run ? `${API_BASE}/api/runs/${run.id}/artifacts/preview.svg` : null),
    [run],
  );

  return (
    <AppShell
      title="任务详情"
      subtitle="查看任务执行过程、中间结果和最终设计输出"
      brands={brands}
      selectedBrand={selectedBrand}
      selectedBrandId={selectedBrandId}
      loadingBrands={loading}
      onBrandChange={setSelectedBrandId}
      buildHref={buildHref}
      headerActions={
        <button className="btn ghost" type="button" onClick={() => void loadRun()}>
          <RefreshCw size={14} /> 刷新
        </button>
      }
    >
      {error || pageError ? <div className="error">{error ?? pageError}</div> : null}

      {pageLoading ? <div className="biz-loading">正在加载任务详情...</div> : null}
      {!pageLoading && !run ? (
        <EmptyState title="任务详情加载失败" description="请稍后刷新重试。" />
      ) : null}

      {run ? (
        <>
          <PageSection title="任务信息" subtitle="核心任务参数与状态概览">
            <div className="biz-detail-grid">
              <div className="biz-detail-card">
                <h3>{run.project_name || run.product_name}</h3>
                <div className="biz-detail-list">
                  <div>任务 ID：{run.id}</div>
                  <div>品牌：{selectedBrand?.name ?? run.brand_id ?? "-"}</div>
                  <div>商品：{run.product_name}</div>
                  <div>任务类型：{run.workflow_mode ?? "-"}</div>
                  <div>状态：<StatusBadge value={run.status} /></div>
                  <div>创建时间：{formatDateTime(run.run_started_at)}</div>
                  <div>完成时间：{formatDateTime(run.run_finished_at)}</div>
                </div>
              </div>
              <div className="biz-detail-card">
                <h3>确认操作</h3>
                <div className="biz-inline-actions">
                  <Link className="btn ghost btn-small" href={buildHref("/tasks")}>
                    返回任务列表
                  </Link>
                  <Link className="btn ghost btn-small" href={buildHref("/tasks/new")}>
                    重新生成整页
                  </Link>
                  <button className="btn ghost btn-small" type="button" disabled>
                    重新生成模块
                  </button>
                </div>
                <p className="hint">当前任务执行失败时，可查看日志并尝试重新执行。</p>
              </div>
            </div>
          </PageSection>

          <PageSection title="执行时间线" subtitle="查看每个阶段的处理状态和耗时">
            <PipelineRibbon
              stages={FALLBACK_STAGES}
              results={run.stage_results}
              running={run.status === "running"}
              currentStageId={run.current_stage}
              selectedStageId={run.current_stage}
            />
            <StageTimeline stages={run.stage_results} />
          </PageSection>

          <div className="biz-two-column">
            <PageSection title="商品理解结果" subtitle="任务输入摘要与商品信息">
              <div className="biz-detail-card">
                <div className="biz-detail-list">
                  <div>输入资产：{run.asset_names.join("、") || "-"}</div>
                  <div>规则版本：{run.rule_version_id ?? "-"}</div>
                  <div>输出格式：{run.output_types.join("、") || "-"}</div>
                </div>
              </div>
            </PageSection>

            <PageSection title="页面结构结果" subtitle="当前任务生成出的结构化阶段结果">
              {!run.stage_results.length ? (
                <EmptyState title="暂无阶段结果" description="任务尚未生成结构化阶段数据。" />
              ) : (
                <div className="biz-code-block">
                  <pre>{JSON.stringify(run.stage_results, null, 2)}</pre>
                </div>
              )}
            </PageSection>
          </div>

          <div className="biz-two-column">
            <PageSection title="布局结果" subtitle="预览生成页面和关键产物">
              {previewUrl ? (
                <iframe className="preview-frame biz-preview-frame" src={previewUrl} title="任务预览" />
              ) : (
                <EmptyState title="暂无预览结果" description="当前任务还没有可预览的页面结构。" />
              )}
            </PageSection>

            <PageSection title="Figma 输出" subtitle="当前版本先提供产物下载和占位入口">
              <div className="biz-inline-actions">
                {run.artifacts.preview_svg ? (
                  <a
                    className="btn ghost btn-small"
                    href={`${API_BASE}/api/runs/${run.id}/artifacts/preview.svg`}
                    target="_blank"
                    rel="noreferrer"
                  >
                    <ExternalLink size={14} /> 预览结果
                  </a>
                ) : null}
                {run.artifacts.design_spec ? (
                  <a
                    className="btn ghost btn-small"
                    href={`${API_BASE}/api/runs/${run.id}/artifacts/design_spec.json`}
                    target="_blank"
                    rel="noreferrer"
                  >
                    <Download size={14} /> 设计 JSON
                  </a>
                ) : null}
                {run.artifacts.photoshop_jsx ? (
                  <a
                    className="btn ghost btn-small"
                    href={`${API_BASE}/api/runs/${run.id}/artifacts/create_detail_page.jsx`}
                    target="_blank"
                    rel="noreferrer"
                  >
                    打开 Figma
                  </a>
                ) : null}
              </div>
              {!run.artifacts.preview_svg && !run.artifacts.design_spec ? (
                <EmptyState title="暂无导出结果" description="产物生成完成后可在这里下载。" />
              ) : null}
            </PageSection>
          </div>

          <PageSection title="图片生成结果" subtitle="本轮保留任务产物与日志回看，模块级编辑后续补齐">
            {run.logs.length ? (
              <div className="biz-code-block">
                <pre>{run.logs.join("\n\n")}</pre>
              </div>
            ) : (
              <EmptyState title="暂无日志输出" description="当前任务没有可展示的执行日志。" />
            )}
          </PageSection>
        </>
      ) : null}
    </AppShell>
  );
}
