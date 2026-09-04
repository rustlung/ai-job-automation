import { ChevronLeft, ChevronRight } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { RunStatusBadge } from "../components/RunStatusBadge";
import { EmptyState, ErrorState, LoadingState } from "../components/States";
import { useRuns } from "../hooks/useOrchestrator";
import { formatDateTime, formatDuration, formatTriggerSource } from "../lib/format";

const pageSize = 20;

export function RunsPage() {
  const [offset, setOffset] = useState(0);
  const runs = useRuns(pageSize, offset);
  const hasPreviousPage = offset > 0;
  const hasNextPage = Boolean(runs.data && offset + runs.data.count < runs.data.total);

  return <div className="space-y-7"><header><p className="text-sm font-medium text-zinc-500">История выполнения</p><h1 className="mt-1 text-2xl font-semibold">Runs</h1></header>{runs.isLoading ? <LoadingState /> : runs.isError ? <ErrorState message="Не удалось загрузить историю запусков." /> : !runs.data?.runs.length ? <EmptyState title="Запусков пока нет" detail="Новый запуск появится здесь сразу после принятия Orchestrator." /> : <section className="overflow-x-auto border border-line bg-white"><table className="w-full min-w-[780px] text-left text-sm"><thead className="border-b border-line bg-zinc-50 text-xs uppercase text-zinc-500"><tr><th className="px-4 py-3 font-medium">Дата</th><th className="px-4 py-3 font-medium">Run ID</th><th className="px-4 py-3 font-medium">Источник</th><th className="px-4 py-3 font-medium">Профили</th><th className="px-4 py-3 font-medium">Статус</th><th className="px-4 py-3 font-medium">Длительность</th></tr></thead><tbody>{runs.data.runs.map((run) => <tr key={run.run_id} className="border-b border-line last:border-0 hover:bg-zinc-50"><td className="whitespace-nowrap px-4 py-3 text-zinc-600">{formatDateTime(run.started_at)}</td><td className="px-4 py-3"><Link className="font-mono text-xs text-zinc-800 underline decoration-zinc-300 underline-offset-4 hover:decoration-zinc-900" to={`/runs/${run.run_id}`}>{run.run_id}</Link></td><td className="px-4 py-3">{formatTriggerSource(run.trigger_source)}</td><td className="max-w-64 px-4 py-3 text-zinc-600">{run.profile_ids.join(", ")}</td><td className="px-4 py-3"><RunStatusBadge status={run.status} /></td><td className="px-4 py-3 text-zinc-600">{formatDuration(run.started_at, run.completed_at)}</td></tr>)}</tbody></table></section>}{runs.data && runs.data.total > pageSize && <div className="flex items-center justify-end gap-2 text-sm text-zinc-500"><button type="button" onClick={() => setOffset((value) => Math.max(0, value - pageSize))} disabled={!hasPreviousPage} className="inline-flex size-8 items-center justify-center border border-line bg-white disabled:text-zinc-300" aria-label="Предыдущая страница"><ChevronLeft size={16} /></button><span>Показано {offset + 1}-{offset + runs.data.count} из {runs.data.total}</span><button type="button" onClick={() => setOffset((value) => value + pageSize)} disabled={!hasNextPage} className="inline-flex size-8 items-center justify-center border border-line bg-white disabled:text-zinc-300" aria-label="Следующая страница"><ChevronRight size={16} /></button></div>}</div>;
}
