"use client";

import { useEffect, useState } from "react";
import {
  fetchWorkflowDetail,
  type ExportPreflight,
  type ExportReview,
  type ResultState,
  type WorkflowDetailResponse,
  type WorkflowResultSummaryPayload,
} from "@/lib/api";
import { WorkflowResultStateCompactSummary } from "./WorkflowResultStateSummary";

const summaryCache = new Map<string, WorkflowResultSummaryPayload | null>();
const summaryRequestCache = new Map<string, Promise<WorkflowResultSummaryPayload | null>>();

function normalizeSummaryPayload(
  payload?: WorkflowResultSummaryPayload | null,
): WorkflowResultSummaryPayload | null {
  if (!payload) return null;
  const resultState = payload.resultState ?? null;
  const exportReview = payload.exportReview ?? null;
  const exportPreflight = payload.exportPreflight ?? resultState?.export_preflight ?? null;
  if (!resultState && !exportReview && !exportPreflight) return null;
  return { resultState, exportReview, exportPreflight };
}

function toSummaryPayload(detail: WorkflowDetailResponse): WorkflowResultSummaryPayload | null {
  return normalizeSummaryPayload({
    resultState: detail.resultState ?? null,
    exportReview: detail.exportReview ?? detail.artifacts?.exportReview ?? null,
    exportPreflight: detail.artifacts?.exportPreflight ?? detail.resultState?.export_preflight ?? null,
  });
}

async function loadWorkflowResultSummary(runId: string): Promise<WorkflowResultSummaryPayload | null> {
  if (summaryCache.has(runId)) return summaryCache.get(runId) ?? null;
  const existingRequest = summaryRequestCache.get(runId);
  if (existingRequest) return existingRequest;

  const request = fetchWorkflowDetail(runId)
    .then((detail) => {
      const payload = toSummaryPayload(detail);
      summaryCache.set(runId, payload);
      return payload;
    })
    .finally(() => {
      summaryRequestCache.delete(runId);
    });

  summaryRequestCache.set(runId, request);
  return request;
}

export function WorkflowResultStateEntrySummary({
  runId,
  summary,
  fallbackSummary,
  className = "",
}: {
  runId: string;
  summary?: WorkflowResultSummaryPayload | null;
  fallbackSummary?: string | null;
  className?: string;
}) {
  const [payload, setPayload] = useState<WorkflowResultSummaryPayload | null>(() => {
    const directPayload = normalizeSummaryPayload(summary);
    if (directPayload) return directPayload;
    return summaryCache.get(runId) ?? null;
  });
  const [loading, setLoading] = useState(() => {
    if (normalizeSummaryPayload(summary)) return false;
    return !summaryCache.has(runId);
  });

  useEffect(() => {
    let cancelled = false;
    const directPayload = normalizeSummaryPayload(summary);
    if (directPayload) {
      summaryCache.set(runId, directPayload);
      setPayload(directPayload);
      setLoading(false);
      return () => {
        cancelled = true;
      };
    }

    setPayload(summaryCache.get(runId) ?? null);
    setLoading(!summaryCache.has(runId));

    void loadWorkflowResultSummary(runId)
      .then((nextPayload) => {
        if (!cancelled) setPayload(nextPayload);
      })
      .catch(() => {
        if (!cancelled) setPayload(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [runId, summary]);

  if (payload) {
    return (
      <WorkflowResultStateCompactSummary
        className={className}
        exportPreflight={payload.exportPreflight}
        exportReview={payload.exportReview}
        resultState={payload.resultState}
      />
    );
  }

  return (
    <div className={`result-state-inline-placeholder ${className}`.trim()}>
      {loading ? "正在同步结果判定..." : fallbackSummary || "暂无结构化结果摘要"}
    </div>
  );
}
