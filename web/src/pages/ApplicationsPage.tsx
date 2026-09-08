import { ChevronLeft, ChevronRight, ChevronsLeft, RotateCcw } from "lucide-react";
import { useCallback } from "react";
import { Link, useLocation, useSearchParams } from "react-router-dom";

import { ApplicationStatusBadge } from "../components/ApplicationStatusBadge";
import { applicationStatusLabels } from "../lib/applicationStatus";
import { EmptyState, ErrorState, LoadingState } from "../components/States";
import { useApplications } from "../hooks/useOrchestrator";
import { formatDateTime } from "../lib/format";
import type { ApplicationFilters, ApplicationStatus } from "../types/api";

const defaultLimit = 25;

function filtersFromUrl(params: URLSearchParams): ApplicationFilters {
  const limit = Number(params.get("limit")) || defaultLimit;
  return {
    status: params.get("status") as ApplicationStatus | undefined,
    date_from: params.get("date_from") || undefined,
    date_to: params.get("date_to") || undefined,
    platform: params.get("platform") || undefined,
    search: params.get("search") || undefined,
    limit: [25, 50, 100].includes(limit) ? limit : defaultLimit,
    offset: Math.max(0, Number(params.get("offset")) || 0)
  };
}

export function ApplicationsPage() {
  const [params, setParams] = useSearchParams();
  const location = useLocation();
  const filters = filtersFromUrl(params);
  const applications = useApplications(filters);
  const update = useCallback((updates: Record<string, string | undefined>, resetOffset = true) => {
    const next = new URLSearchParams(params);
    Object.entries(updates).forEach(([key, value]) => { next.delete(key); if (value) next.set(key, value); });
    if (resetOffset) next.delete("offset");
    setParams(next);
  }, [params, setParams]);
  const hasPrevious = filters.offset > 0;
  const hasNext = Boolean(applications.data && filters.offset + applications.data.items.length < applications.data.total);

  return <div className="space-y-6"><header className="flex flex-wrap items-end justify-between gap-3"><div><p className="text-sm font-medium text-zinc-500">Процессы откликов</p><h1 className="mt-1 text-2xl font-semibold">Отклики</h1></div><button type="button" onClick={() => setParams(new URLSearchParams())} className="inline-flex items-center gap-2 border border-line bg-white px-3 py-2 text-sm font-medium text-zinc-700"><RotateCcw size={16} />Сбросить фильтры</button></header><section className="grid gap-3 border border-line bg-white p-4 md:grid-cols-2 xl:grid-cols-5"><label className="grid gap-1 text-sm font-medium text-zinc-700">Статус<select value={filters.status ?? ""} onChange={(event) => update({ status: event.target.value || undefined })} className="border border-line bg-white px-3 py-2 font-normal"><option value="">Все статусы</option>{Object.entries(applicationStatusLabels).map(([status, label]) => <option key={status} value={status}>{label}</option>)}</select></label><label className="grid gap-1 text-sm font-medium text-zinc-700">С даты<input type="date" value={filters.date_from ?? ""} onChange={(event) => update({ date_from: event.target.value || undefined })} className="border border-line px-3 py-2 font-normal" /></label><label className="grid gap-1 text-sm font-medium text-zinc-700">По дату<input type="date" value={filters.date_to ?? ""} onChange={(event) => update({ date_to: event.target.value || undefined })} className="border border-line px-3 py-2 font-normal" /></label><label className="grid gap-1 text-sm font-medium text-zinc-700">Платформа<input value={filters.platform ?? ""} onChange={(event) => update({ platform: event.target.value || undefined })} className="border border-line px-3 py-2 font-normal" placeholder="hh" /></label><label className="grid gap-1 text-sm font-medium text-zinc-700">Поиск<input value={filters.search ?? ""} onChange={(event) => update({ search: event.target.value || undefined })} className="border border-line px-3 py-2 font-normal" placeholder="Компания или вакансия" /></label></section>{applications.isLoading ? <LoadingState /> : applications.isError ? <ErrorState message="Не удалось загрузить отклики." /> : !applications.data?.items.length ? <EmptyState title="Откликов не найдено" detail="Измените фильтры или добавьте отклик из карточки вакансии." /> : <><section className="overflow-x-auto border border-line bg-white"><table className="w-full min-w-[900px] text-left text-sm"><thead className="border-b border-line bg-zinc-50 text-xs uppercase text-zinc-500"><tr><th className="px-4 py-3">Дата отклика</th><th className="px-4 py-3">Компания</th><th className="px-4 py-3">Вакансия</th><th className="px-4 py-3">Статус</th><th className="px-4 py-3">Платформа</th><th className="px-4 py-3">Обновлено</th></tr></thead><tbody>{applications.data.items.map((application) => <tr key={application.id} className="border-b border-line last:border-0 hover:bg-zinc-50"><td className="px-4 py-3 text-zinc-600">{formatDateTime(application.applied_at)}</td><td className="px-4 py-3 font-medium">{application.company}</td><td className="px-4 py-3"><Link to={`/vacancies/${encodeURIComponent(application.presentation_key)}`} state={{ from: { pathname: location.pathname, search: location.search } }} className="font-medium text-zinc-900 underline decoration-zinc-300 underline-offset-4">{application.title}</Link></td><td className="px-4 py-3"><ApplicationStatusBadge status={application.status} /></td><td className="px-4 py-3 text-zinc-600">{application.platform ?? "—"}</td><td className="px-4 py-3 text-zinc-600">{formatDateTime(application.updated_at)}</td></tr>)}</tbody></table></section><div className="flex flex-wrap items-center justify-between gap-3 text-sm text-zinc-500"><span>Показано {filters.offset + 1}-{filters.offset + applications.data.items.length} из {applications.data.total}</span><div className="flex items-center gap-2"><label>На странице <select value={filters.limit} onChange={(event) => update({ limit: event.target.value })} className="border border-line bg-white px-2 py-1"><option value="25">25</option><option value="50">50</option><option value="100">100</option></select></label><button type="button" aria-label="На первую страницу" disabled={!hasPrevious} onClick={() => update({ offset: undefined }, false)} className="inline-flex size-8 items-center justify-center border border-line bg-white disabled:text-zinc-300"><ChevronsLeft size={16} /></button><button type="button" aria-label="Предыдущая страница" disabled={!hasPrevious} onClick={() => update({ offset: filters.offset - filters.limit > 0 ? String(filters.offset - filters.limit) : undefined }, false)} className="inline-flex size-8 items-center justify-center border border-line bg-white disabled:text-zinc-300"><ChevronLeft size={16} /></button><button type="button" aria-label="Следующая страница" disabled={!hasNext} onClick={() => update({ offset: String(filters.offset + filters.limit) }, false)} className="inline-flex size-8 items-center justify-center border border-line bg-white disabled:text-zinc-300"><ChevronRight size={16} /></button></div></div></>}</div>;
}
