import type { PipelineRunStatus } from "../types/api";

const labels: Record<PipelineRunStatus, string> = {
  accepted: "Принят",
  running: "Выполняется",
  completed: "Завершён",
  completed_with_errors: "Завершён с ошибками",
  failed: "Не выполнен"
};
const classes: Record<PipelineRunStatus, string> = {
  accepted: "bg-zinc-100 text-zinc-700", running: "bg-sky-50 text-sky-800", completed: "bg-emerald-50 text-emerald-800", completed_with_errors: "bg-amber-50 text-amber-800", failed: "bg-red-50 text-red-800"
};

export function RunStatusBadge({ status }: { status: PipelineRunStatus }) {
  return <span className={`inline-flex rounded px-2 py-1 text-xs font-semibold ${classes[status]}`}>{labels[status]}</span>;
}
