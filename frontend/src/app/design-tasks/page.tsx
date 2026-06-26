import { DesignTasksPageClient } from "@/components/DesignTasksPageClient";
import { fetchDesignTasksPage } from "@/lib/api";

export default async function DesignTasksPage() {
  const data = await fetchDesignTasksPage();
  return <DesignTasksPageClient initialData={data} />;
}
