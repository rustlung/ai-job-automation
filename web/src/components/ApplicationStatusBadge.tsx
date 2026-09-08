import type { ApplicationStatus } from "../types/api";
import { applicationStatusLabels } from "../lib/applicationStatus";

const applicationStatusClasses: Record<ApplicationStatus, string> = {
  submitted: "bg-sky-50 text-sky-800",
  response_received: "bg-cyan-50 text-cyan-800",
  screening: "bg-indigo-50 text-indigo-800",
  test_task: "bg-violet-50 text-violet-800",
  interview: "bg-amber-50 text-amber-800",
  offer: "bg-emerald-50 text-emerald-800",
  rejected: "bg-rose-50 text-rose-800",
  withdrawn: "bg-zinc-100 text-zinc-700"
};

export function ApplicationStatusBadge({ status }: { status: ApplicationStatus | null }) {
  if (!status) return <span className="inline-flex border border-zinc-300 bg-white px-2 py-1 text-xs font-medium text-zinc-600">Без отклика</span>;
  return <span className={`inline-flex px-2 py-1 text-xs font-semibold ${applicationStatusClasses[status]}`}>{applicationStatusLabels[status]}</span>;
}
