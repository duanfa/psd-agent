import { TaskDetailPage } from "@/components/business/TaskDetailPage";

export default async function Page({
  searchParams,
}: {
  searchParams: Promise<{ run?: string }>;
}) {
  const { run } = await searchParams;
  return <TaskDetailPage runId={run ?? ""} />;
}
