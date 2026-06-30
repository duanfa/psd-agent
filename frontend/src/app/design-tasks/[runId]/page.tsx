import { DesignTaskDetailPageClient } from "@/components/DesignTaskDetailPageClient";
import { fetchWorkflowDetail } from "@/lib/api";

export default async function DesignTaskDetailPage({
  params,
}: {
  params: Promise<{ runId: string }>;
}) {
  const { runId } = await params;
  const data = await fetchWorkflowDetail(runId);
  return <DesignTaskDetailPageClient initialData={data} />;
}
