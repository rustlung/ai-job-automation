import { Link, useParams } from "react-router-dom";

import { RunStatusBadge } from "../components/RunStatusBadge";
import { LegacyCrmKeyMigrationStatus } from "../components/LegacyCrmKeyMigrationStatus";
import { ErrorState, LoadingState } from "../components/States";
import { useRun } from "../hooks/useOrchestrator";
import { formatDateTime, formatTriggerSource, isTerminalRunStatus } from "../lib/format";
import type { PipelineRunDiagnostic } from "../types/api";

function StatValue({ label, value }: { label: string; value: unknown }) { return <div><dt className="text-xs font-medium uppercase text-zinc-500">{label}</dt><dd className="mt-1 text-sm text-zinc-800">{typeof value === "number" || typeof value === "string" ? value : "—"}</dd></div>; }

function DiagnosticList({ items }: { items: PipelineRunDiagnostic[] }) {
  return <ul className="mt-3 space-y-2 text-sm text-zinc-700">{items.map((item) => <li key={`${item.code}-${item.summary}`}><span className="font-medium">{item.summary}</span>{item.count > 1 ? `: ${item.count}` : ""}</li>)}</ul>;
}

export function RunDetailPage() {
  const { runId = "" } = useParams();
  const run = useRun(runId);
  if (run.isLoading) return <LoadingState label="Загрузка статуса запуска…" />;
  if (run.isError || !run.data) return <ErrorState message="Запуск не найден или недоступен." />;
  const stats = run.data.stats_snapshot ?? {};
  const warnings = Array.isArray(stats.warnings) ? stats.warnings : [];
  const partialFailures = Array.isArray(stats.partial_failures) ? stats.partial_failures : [];
  const statsEntries = Object.entries(stats).filter(([key]) => !["legacy_crm_key_matches", "warnings", "partial_failures"].includes(key));
  const isTerminal = isTerminalRunStatus(run.data.status);
  const fatalError = run.data.status === "failed" ? run.data.error_summary ?? run.data.error_code : null;
  return <div className="max-w-4xl space-y-7"><header className="flex flex-wrap items-start justify-between gap-4"><div><Link to="/runs" className="text-sm text-zinc-600 underline underline-offset-4">Runs</Link><h1 className="mt-3 break-all font-mono text-xl font-semibold">{run.data.run_id}</h1><p className="mt-2 text-sm text-zinc-500">{formatTriggerSource(run.data.trigger_source)}</p></div><RunStatusBadge status={run.data.status} /></header>{!isTerminal && <p role="status" className="border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-900">Статус обновляется автоматически каждые 4 секунды.</p>}<section className="border border-line bg-white p-5"><h2 className="text-base font-semibold">Состояние</h2><dl className="mt-4 grid gap-5 sm:grid-cols-2 lg:grid-cols-3"><StatValue label="Начат" value={formatDateTime(run.data.started_at)} /><StatValue label="Завершён" value={formatDateTime(run.data.completed_at)} /><StatValue label="Профили" value={run.data.profile_ids.join(", ")} />{fatalError && <StatValue label="Ошибка" value={fatalError} />}</dl></section>{partialFailures.length > 0 && <section className="border border-amber-200 bg-amber-50 p-5"><h2 className="text-base font-semibold text-amber-950">Частичные ошибки</h2><DiagnosticList items={partialFailures} /></section>}{warnings.length > 0 && <section className="border border-sky-200 bg-sky-50 p-5"><h2 className="text-base font-semibold text-sky-950">Предупреждения</h2><DiagnosticList items={warnings} /></section>}<LegacyCrmKeyMigrationStatus matches={stats.legacy_crm_key_matches} /><section className="border border-line bg-white p-5"><h2 className="text-base font-semibold">Статистика</h2>{statsEntries.length ? <dl className="mt-4 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">{statsEntries.map(([key, value]) => <StatValue key={key} label={key.replaceAll("_", " ")} value={typeof value === "object" ? JSON.stringify(value) : value} />)}</dl> : <p className="mt-3 text-sm text-zinc-500">Статистика появится после обработки Worker.</p>}</section><section className="border border-line bg-white p-5"><h2 className="text-base font-semibold">Конфигурация запуска</h2><dl className="mt-4 grid gap-5 sm:grid-cols-2">{Object.entries(run.data.config_snapshot).map(([key, value]) => <StatValue key={key} label={key.replaceAll("_", " ")} value={Array.isArray(value) ? value.join(", ") : typeof value === "object" ? JSON.stringify(value) : value} />)}</dl></section></div>;
}
