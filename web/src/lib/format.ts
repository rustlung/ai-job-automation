import type { PipelineRunStatus, PipelineRunTriggerSource } from "../types/api";

export const isTerminalRunStatus = (status: PipelineRunStatus): boolean =>
  ["completed", "completed_with_errors", "failed"].includes(status);

export const runPollingInterval = (status: PipelineRunStatus | undefined): number | false =>
  status && !isTerminalRunStatus(status) ? 4000 : false;

export function formatTriggerSource(source: PipelineRunTriggerSource): string {
  const labels: Record<PipelineRunTriggerSource, string> = {
    manual_n8n: "Manual n8n",
    web_ui: "Web UI",
    scheduled: "По расписанию"
  };
  return labels[source] ?? source;
}

export function formatDateTime(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat("ru-RU", {
    dateStyle: "medium",
    timeStyle: "short"
  }).format(date);
}

export function formatDuration(startedAt: string, completedAt: string | null): string {
  if (!completedAt) return "Выполняется";
  const milliseconds = new Date(completedAt).getTime() - new Date(startedAt).getTime();
  if (!Number.isFinite(milliseconds) || milliseconds < 0) return "—";
  const seconds = Math.round(milliseconds / 1000);
  if (seconds < 60) return `${seconds} с`;
  return `${Math.floor(seconds / 60)} мин ${seconds % 60} с`;
}
