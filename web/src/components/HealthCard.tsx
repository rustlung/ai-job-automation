import { CircleAlert, CircleCheck, CircleHelp, WifiOff } from "lucide-react";

export interface HealthCardProps { title: string; status: string; detail: string; }

const styles: Record<string, { icon: typeof CircleCheck; className: string; label: string }> = {
  ok: { icon: CircleCheck, className: "text-success", label: "OK" },
  degraded: { icon: CircleAlert, className: "text-warning", label: "Degraded" },
  unavailable: { icon: WifiOff, className: "text-danger", label: "Unavailable" },
  unknown: { icon: CircleHelp, className: "text-zinc-500", label: "Unknown" }
};

export function HealthCard({ title, status, detail }: HealthCardProps) {
  const state = styles[status] ?? styles.unknown;
  const Icon = state.icon;
  return <section className="border border-line bg-white p-4 shadow-sm"><div className="flex items-start justify-between gap-3"><div><h2 className="text-sm font-medium text-zinc-600">{title}</h2><p className="mt-2 text-lg font-semibold text-ink">{state.label}</p></div><Icon className={state.className} aria-label={state.label} size={22} /></div><p className="mt-3 text-sm text-zinc-500">{detail}</p></section>;
}
