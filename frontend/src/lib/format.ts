export function formatDateTime(value?: string | null): string {
  if (!value) return "-";
  return value.replace("T", " ").slice(0, 19);
}

export function safeCount(value: unknown): number {
  return Array.isArray(value) ? value.length : 0;
}
