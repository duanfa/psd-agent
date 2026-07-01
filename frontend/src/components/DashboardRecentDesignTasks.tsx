import Link from "next/link";
import { type DesignTaskSummaryListItem } from "@/lib/api";
import { WorkflowResultStateEntrySummary } from "./WorkflowResultStateEntrySummary";

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

function formatTime(value?: string | null) {
  if (!value) return "-";
  return new Date(value).toLocaleString("zh-CN", { hour12: false });
}

export function DashboardRecentDesignTasks({
  initialTasks,
}: {
  initialTasks: DesignTaskSummaryListItem[];
}) {
  if (!initialTasks.length) {
    return <div className="muted-text">当前品牌还没有设计任务。</div>;
  }

  return (
    <div className="record-list">
      {initialTasks.map((item) => (
        <div className="record-item record-item-compact" key={item.runId}>
          <div className="split-line">
            <div>
              <Link className="table-link" href={`/design-tasks/${item.runId}`}>
                {item.product || item.title || item.taskId}
              </Link>
              <div className="subtitle">
                {item.taskType} / {formatTime(item.createdAt)}
              </div>
            </div>
            <span className={`status-pill ${statusClass(item.status)}`}>{statusLabel(item.status)}</span>
          </div>
          <WorkflowResultStateEntrySummary
            runId={item.runId}
            summary={item.resultSummary}
            fallbackSummary={item.summary}
          />
        </div>
      ))}
    </div>
  );
}
