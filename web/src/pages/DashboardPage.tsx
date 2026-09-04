import { ArrowRight, CirclePlay, List } from "lucide-react";
import { Link } from "react-router-dom";

import { HealthCard } from "../components/HealthCard";
import { EmptyState, ErrorState, LoadingState } from "../components/States";
import { RunStatusBadge } from "../components/RunStatusBadge";
import { useRuns, useSystemHealth } from "../hooks/useOrchestrator";
import { formatDateTime, formatTriggerSource } from "../lib/format";

export function DashboardPage() {
  const health = useSystemHealth();
  const runs = useRuns(1);
  const latestRun = runs.data?.runs[0];
  return <div className="space-y-8">
    <header className="flex flex-wrap items-start justify-between gap-4"><div><p className="text-sm font-medium text-zinc-500">Рабочая панель</p><h1 className="mt-1 text-2xl font-semibold">Dashboard</h1></div><div className="flex gap-2"><Link to="/runs" className="inline-flex items-center gap-2 border border-zinc-300 bg-white px-3 py-2 text-sm font-medium hover:bg-zinc-50"><List size={16} />Все запуски</Link><Link to="/runs/new" className="inline-flex items-center gap-2 bg-zinc-900 px-3 py-2 text-sm font-medium text-white hover:bg-zinc-700"><CirclePlay size={16} />Запустить поиск</Link></div></header>
    <section><div className="mb-3 flex items-baseline justify-between"><h2 className="text-base font-semibold">System health</h2><span className="text-xs text-zinc-500">Обновляется без GPU warm-up</span></div>{health.isLoading ? <LoadingState /> : health.isError ? <ErrorState /> : health.data ? <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4"><HealthCard title="Orchestrator" status={health.data.orchestrator.status} detail={health.data.orchestrator.available ? "API доступен" : "API недоступен"} /><HealthCard title="Worker" status={health.data.worker.status} detail={health.data.worker.available ? "Compute layer доступен" : "Compute layer недоступен"} /><HealthCard title="Ollama" status={health.data.ollama.status} detail={health.data.ollama.available ? "Модель доступна" : "Проверьте Ollama"} /><HealthCard title="Compute / GPU" status={health.data.compute_status} detail={health.data.compute_status === "unknown" ? "Последний статус неизвестен" : `Последний статус: ${health.data.compute_status}`} /></div> : null}</section>
    <section><div className="mb-3 flex items-center justify-between"><h2 className="text-base font-semibold">Последний запуск</h2><Link to="/runs" className="inline-flex items-center gap-1 text-sm font-medium text-zinc-700 hover:text-zinc-950">Открыть список <ArrowRight size={15} /></Link></div>{runs.isLoading ? <LoadingState /> : runs.isError ? <ErrorState /> : !latestRun ? <EmptyState title="Запусков пока нет" detail="Выберите поисковые профили и начните первый запуск." /> : <Link to={`/runs/${latestRun.run_id}`} className="block border border-line bg-white p-5 shadow-sm transition hover:border-zinc-400"><div className="flex flex-wrap items-start justify-between gap-3"><div><p className="font-mono text-sm text-zinc-600">{latestRun.run_id}</p><p className="mt-2 text-sm text-zinc-500">{formatTriggerSource(latestRun.trigger_source)} · {formatDateTime(latestRun.started_at)}</p></div><RunStatusBadge status={latestRun.status} /></div><p className="mt-4 text-sm text-zinc-700">{latestRun.profile_ids.join(", ") || "Профили не указаны"}</p></Link>}</section>
  </div>;
}
