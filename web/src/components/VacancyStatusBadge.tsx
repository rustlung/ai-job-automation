import type { VacancyStatus } from "../types/api";
import { vacancyStatusLabels } from "../lib/vacancyStatus";

const classes: Record<VacancyStatus, string> = {
  active: "bg-emerald-50 text-emerald-800",
  archived: "bg-amber-50 text-amber-800",
  closed: "bg-zinc-100 text-zinc-700"
};

export function VacancyStatusBadge({ status }: { status: VacancyStatus }) {
  return <span className={`inline-flex px-2 py-1 text-xs font-semibold ${classes[status]}`}>{vacancyStatusLabels[status]}</span>;
}
