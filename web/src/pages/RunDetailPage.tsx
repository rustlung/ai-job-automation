import { Link, useParams } from "react-router-dom";
import { useState } from "react";

import { RunStatusBadge } from "../components/RunStatusBadge";
import { ErrorState, LoadingState } from "../components/States";
import { useCancelRun, useRun } from "../hooks/useOrchestrator";
import { formatDateTime, formatTriggerSource, isTerminalRunStatus } from "../lib/format";
import type { PipelineRunDiagnostic } from "../types/api";

function StatValue({ label, value }: { label: string; value: unknown }) {
  return <div className="min-w-0" data-testid="run-stat-value"><dt className="text-xs font-medium uppercase text-zinc-500">{label}</dt><dd className="mt-1 min-w-0 whitespace-pre-wrap break-words text-sm text-zinc-800 [overflow-wrap:anywhere]">{typeof value === "number" || typeof value === "string" ? value : "—"}</dd></div>;
}

function DiagnosticList({ items }: { items: PipelineRunDiagnostic[] }) {
  return <ul className="mt-3 space-y-2 text-sm text-zinc-700">{items.map((item) => <li key={`${item.code}-${item.summary}`}><span className="font-medium">{item.summary}</span>{item.count > 1 ? `: ${item.count}` : ""}</li>)}</ul>;
}

const stageLabels: Record<string, string> = {
  queued: "В очереди", collection: "Сбор вакансий", discovery: "Сохранение найденных вакансий",
  preliminary: "Предварительная фильтрация", enrichment: "Обогащение вакансий", persistence: "Сохранение результатов",
  post_processing: "Завершение", recovery: "Восстановление", completed: "Завершено", failed: "Ошибка", cancelled: "Отменено"
};

const stageDescriptions: Record<string, string> = {
  queued: "Запуск ожидает начала обработки",
  collection: "Поиск и сбор вакансий на HH",
  discovery: "Сохранение найденных вакансий",
  preliminary: "Вакансии проходят предварительный AI-отбор",
  enrichment: "Загрузка полной карточки и AI-анализ",
  persistence: "Сохранение результатов обработки",
  post_processing: "Завершение обработки запуска",
  recovery: "Worker восстанавливает обработку после перезапуска",
  completed: "Запуск успешно завершён",
  failed: "Запуск завершился с ошибкой",
  cancelled: "Запуск отменён пользователем"
};

export function RunDetailPage() {
  const { runId = "" } = useParams();
  const run = useRun(runId);
  const cancel = useCancelRun();
  const [cancelling, setCancelling] = useState(false);
  if (run.isLoading) return <LoadingState label="Загрузка статуса запуска…" />;
  if (run.isError || !run.data) return <ErrorState message="Запуск не найден или недоступен." />;
  const stats = run.data.stats_snapshot ?? {};
  const warnings = Array.isArray(stats.warnings) ? stats.warnings : [];
  const partialFailures = Array.isArray(stats.partial_failures) ? stats.partial_failures : [];
  const integrationErrors = Array.isArray(stats.integration_errors) ? stats.integration_errors : [];
  const statsEntries = Object.entries(stats).filter(([key]) => !["legacy_crm_key_matches", "warnings", "partial_failures", "integration_errors", "progress"].includes(key));
  const isTerminal = isTerminalRunStatus(run.data.status);
  const fatalError = run.data.status === "failed" ? run.data.error_summary ?? run.data.error_code : null;
  const progress = stats.progress;
  const progressStage = progress?.stage ?? (isTerminal ? run.data.status : null);
  const progressMessage = progress?.message ?? (progressStage ? stageDescriptions[progressStage] : null);
  const cancellable = ["accepted", "running"].includes(run.data.status);
  const requestCancel = async () => {
    if (!window.confirm("Отменить запуск? Обработка остановится на ближайшей безопасной границе.")) return;
    setCancelling(true);
    try { await cancel.mutateAsync(run.data.run_id); } finally { setCancelling(false); }
  };
  return <div className="max-w-4xl space-y-7"><header className="flex flex-wrap items-start justify-between gap-4"><div><Link to="/runs" className="text-sm text-zinc-600 underline underline-offset-4">Runs</Link><h1 className="mt-3 break-all font-mono text-xl font-semibold">{run.data.run_id}</h1><p className="mt-2 text-sm text-zinc-500">{formatTriggerSource(run.data.trigger_source)}</p></div><div className="flex flex-wrap items-center gap-3"><Link to={`/diagnostics/runs/${run.data.run_id}`} className="border border-line bg-white px-3 py-2 text-sm">Открыть диагностику</Link>{cancellable && <button type="button" onClick={requestCancel} disabled={cancelling || cancel.isPending} className="border border-red-300 bg-white px-3 py-2 text-sm text-red-800 disabled:opacity-50">{cancelling || cancel.isPending ? "Отмена…" : "Отменить запуск"}</button>}<RunStatusBadge status={run.data.status} /></div></header>{!isTerminal && <p role="status" className="border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-900">Статус обновляется автоматически каждые 4 секунды.</p>}{progressStage && <section className="border border-line bg-white p-5" data-testid="run-progress"><h2 className="text-base font-semibold">Прогресс</h2><p className="mt-3 text-sm font-medium">{stageLabels[progressStage] ?? progressStage}</p>{progressMessage && <p className="mt-1 text-sm text-zinc-600">{progressMessage}</p>}</section>}<section className="border border-line bg-white p-5"><h2 className="text-base font-semibold">Состояние</h2><dl className="mt-4 grid gap-5 sm:grid-cols-2 lg:grid-cols-3"><StatValue label="Начат" value={formatDateTime(run.data.started_at)} /><StatValue label="Завершён" value={formatDateTime(run.data.completed_at)} /><StatValue label="Профили" value={run.data.profile_ids.join(", ")} />{fatalError && <StatValue label="Ошибка" value={fatalError} />}</dl></section>{integrationErrors.length > 0 && <section className="border border-amber-200 bg-amber-50 p-5"><h2 className="text-base font-semibold text-amber-950">Ошибки интеграций</h2><DiagnosticList items={integrationErrors} /></section>}{partialFailures.length > 0 && <section className="border border-zinc-200 bg-zinc-50 p-5"><h2 className="text-base font-semibold text-zinc-900">Диагностика обработки</h2><DiagnosticList items={partialFailures} /></section>}{warnings.length > 0 && <section className="border border-sky-200 bg-sky-50 p-5"><h2 className="text-base font-semibold text-sky-950">Предупреждения</h2><DiagnosticList items={warnings} /></section>}<section className="border border-line bg-white p-5"><h2 className="text-base font-semibold">Статистика</h2>{statsEntries.length ? <dl className="mt-4 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">{statsEntries.map(([key, value]) => <StatValue key={key} label={key.replaceAll("_", " ")} value={typeof value === "object" ? JSON.stringify(value) : value} />)}</dl> : <p className="mt-3 text-sm text-zinc-500">Статистика появится после обработки Worker.</p>}</section><section className="border border-line bg-white p-5"><h2 className="text-base font-semibold">Конфигурация запуска</h2><dl className="mt-4 grid gap-5 sm:grid-cols-2">{Object.entries(run.data.config_snapshot).map(([key, value]) => <StatValue key={key} label={key.replaceAll("_", " ")} value={Array.isArray(value) ? value.join(", ") : typeof value === "object" ? JSON.stringify(value) : value} />)}</dl></section></div>;
}
