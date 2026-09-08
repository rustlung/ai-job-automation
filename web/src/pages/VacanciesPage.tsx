import { ChevronLeft, ChevronRight, RotateCcw, SlidersHorizontal } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";

import { EmptyState, ErrorState, LoadingState } from "../components/States";
import { useSearchProfiles, useVacancies } from "../hooks/useOrchestrator";
import { formatDate } from "../lib/format";
import type { VacancyFilters, VacancyPriority } from "../types/api";
import { dateRangeForPreset, type DatePreset } from "../features/vacancies/dateFilters";

const defaultPageSize = 25;
const priorityOptions: VacancyPriority[] = ["P1", "P2", "P3", "ALT"];
const presets: Array<{ id: DatePreset; label: string }> = [
  { id: "today", label: "Сегодня" },
  { id: "3d", label: "3 дня" },
  { id: "7d", label: "7 дней" },
  { id: "14d", label: "14 дней" },
  { id: "30d", label: "30 дней" },
  { id: "all", label: "Всё время" }
];

function readFilters(searchParams: URLSearchParams): VacancyFilters {
  const limit = Number(searchParams.get("limit")) || defaultPageSize;
  const offset = Number(searchParams.get("offset")) || 0;
  const sort = searchParams.get("sort");
  const direction = searchParams.get("sort_direction");
  return {
    date_from: searchParams.get("date_from") || undefined,
    date_to: searchParams.get("date_to") || undefined,
    priority: searchParams.getAll("priority") as VacancyPriority[],
    track: searchParams.get("track") || undefined,
    profile_id: searchParams.get("profile_id") || undefined,
    run_id: searchParams.get("run_id") || undefined,
    search: searchParams.get("search") || undefined,
    limit: [25, 50, 100].includes(limit) ? limit : defaultPageSize,
    offset: Math.max(0, offset),
    sort: sort === "final_score" || sort === "priority" ? sort : "first_seen",
    sort_direction: direction === "asc" ? "asc" : "desc"
  };
}

function profileLabel(profileId: string, profiles: Array<{ id: string; name: string }>): string {
  return profiles.find((profile) => profile.id === profileId)?.name ?? profileId;
}

export function VacanciesPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const filters = readFilters(searchParams);
  const vacancies = useVacancies(filters);
  const profiles = useSearchProfiles();
  const selectableProfiles = profiles.data?.profiles.filter((profile) => profile.enabled && profile.user_selectable) ?? [];

  const updateFilters = (updates: Record<string, string | string[] | undefined>, resetOffset = true) => {
    const next = new URLSearchParams(searchParams);
    Object.entries(updates).forEach(([key, value]) => {
      next.delete(key);
      if (Array.isArray(value)) value.forEach((entry) => next.append(key, entry));
      else if (value) next.set(key, value);
    });
    if (resetOffset) next.delete("offset");
    setSearchParams(next);
  };

  const setPreset = (preset: DatePreset) => updateFilters(dateRangeForPreset(preset));
  const togglePriority = (priority: VacancyPriority) => {
    const next = filters.priority?.includes(priority)
      ? filters.priority.filter((value) => value !== priority)
      : [...(filters.priority ?? []), priority];
    updateFilters({ priority: next });
  };
  const hasPreviousPage = filters.offset > 0;
  const hasNextPage = Boolean(vacancies.data && filters.offset + vacancies.data.items.length < vacancies.data.total);

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div><p className="text-sm font-medium text-zinc-500">Логические вакансии</p><h1 className="mt-1 text-2xl font-semibold">Vacancies</h1></div>
        <button type="button" onClick={() => setSearchParams(new URLSearchParams())} className="inline-flex items-center gap-2 border border-line bg-white px-3 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-50"><RotateCcw size={16} />Сбросить фильтры</button>
      </header>

      <section className="space-y-4 border border-line bg-white p-4">
        <div><p className="text-sm font-medium text-zinc-800">Период первого обнаружения</p><div className="mt-2 flex flex-wrap gap-2">{presets.map((preset) => <button key={preset.id} type="button" onClick={() => setPreset(preset.id)} className="border border-line px-3 py-1.5 text-sm text-zinc-700 hover:border-zinc-500 hover:bg-zinc-50">{preset.label}</button>)}</div></div>
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <label className="grid gap-1 text-sm font-medium text-zinc-700">С даты<input type="date" value={filters.date_from ?? ""} onChange={(event) => updateFilters({ date_from: event.target.value || undefined })} className="border border-line px-3 py-2 font-normal" /></label>
          <label className="grid gap-1 text-sm font-medium text-zinc-700">По дату<input type="date" value={filters.date_to ?? ""} onChange={(event) => updateFilters({ date_to: event.target.value || undefined })} className="border border-line px-3 py-2 font-normal" /></label>
          <label className="grid gap-1 text-sm font-medium text-zinc-700">Профиль поиска<select value={filters.profile_id ?? ""} onChange={(event) => updateFilters({ profile_id: event.target.value || undefined })} className="border border-line bg-white px-3 py-2 font-normal"><option value="">Все профили</option>{selectableProfiles.map((profile) => <option key={profile.id} value={profile.id}>{profile.name}</option>)}</select></label>
          <label className="grid gap-1 text-sm font-medium text-zinc-700">Поиск по компании или вакансии<input value={filters.search ?? ""} onChange={(event) => updateFilters({ search: event.target.value || undefined })} className="border border-line px-3 py-2 font-normal" placeholder="Например, Python" /></label>
        </div>
        <fieldset><legend className="text-sm font-medium text-zinc-700">Приоритет</legend><div className="mt-2 flex flex-wrap gap-3">{priorityOptions.map((priority) => <label key={priority} className="inline-flex items-center gap-2 text-sm text-zinc-700"><input type="checkbox" checked={filters.priority?.includes(priority) ?? false} onChange={() => togglePriority(priority)} />{priority}</label>)}</div></fieldset>
        <details className="border-t border-line pt-3"><summary className="flex cursor-pointer items-center gap-2 text-sm font-medium text-zinc-700"><SlidersHorizontal size={16} />Дополнительные фильтры</summary><div className="mt-3 grid gap-3 md:grid-cols-3"><label className="grid gap-1 text-sm font-medium text-zinc-700">Track<input value={filters.track ?? ""} onChange={(event) => updateFilters({ track: event.target.value || undefined })} className="border border-line px-3 py-2 font-normal" placeholder="Например, main" /></label><label className="grid gap-1 text-sm font-medium text-zinc-700">Run ID<input value={filters.run_id ?? ""} onChange={(event) => updateFilters({ run_id: event.target.value || undefined })} className="border border-line px-3 py-2 font-normal" /></label><label className="grid gap-1 text-sm font-medium text-zinc-700">Сортировка<select value={`${filters.sort}:${filters.sort_direction}`} onChange={(event) => { const [sort, sort_direction] = event.target.value.split(":"); updateFilters({ sort, sort_direction }); }} className="border border-line bg-white px-3 py-2 font-normal"><option value="first_seen:desc">Сначала новые</option><option value="first_seen:asc">Сначала старые</option><option value="final_score:desc">Score: выше</option><option value="final_score:asc">Score: ниже</option><option value="priority:asc">Priority: выше</option><option value="priority:desc">Priority: ниже</option></select></label></div></details>
      </section>

      {vacancies.isLoading ? <LoadingState /> : vacancies.isError ? <ErrorState message="Не удалось загрузить список вакансий." /> : !vacancies.data?.items.length ? <EmptyState title="Вакансий не найдено" detail="За выбранный период или с указанными фильтрами вакансий нет." /> : <><section className="overflow-x-auto border border-line bg-white"><table className="w-full min-w-[980px] text-left text-sm"><thead className="border-b border-line bg-zinc-50 text-xs uppercase text-zinc-500"><tr><th className="px-4 py-3 font-medium">Дата</th><th className="px-4 py-3 font-medium">Компания</th><th className="px-4 py-3 font-medium">Вакансия</th><th className="px-4 py-3 font-medium">Зарплата</th><th className="px-4 py-3 font-medium">Priority</th><th className="px-4 py-3 font-medium">Score</th><th className="px-4 py-3 font-medium">Track</th><th className="px-4 py-3 font-medium">Профили поиска</th></tr></thead><tbody>{vacancies.data.items.map((vacancy) => <tr key={vacancy.presentation_key} className="border-b border-line last:border-0 hover:bg-zinc-50 focus-within:bg-zinc-50"><td className="whitespace-nowrap px-4 py-3 text-zinc-600">{formatDate(vacancy.first_seen_at)}</td><td className="px-4 py-3 font-medium">{vacancy.company}</td><td className="max-w-80 px-4 py-3"><Link className="font-medium text-zinc-900 underline decoration-zinc-300 underline-offset-4 hover:decoration-zinc-900" to={`/vacancies/${encodeURIComponent(vacancy.presentation_key)}`}>{vacancy.title}</Link>{vacancy.member_count > 1 && <span className="ml-2 text-xs text-zinc-500">{vacancy.member_count} copies</span>}</td><td className="px-4 py-3 text-zinc-600">{vacancy.salary_text ?? "—"}</td><td className="px-4 py-3">{vacancy.priority ?? "—"}</td><td className="px-4 py-3">{vacancy.final_score ?? "—"}</td><td className="px-4 py-3 text-zinc-600">{vacancy.track ?? "—"}</td><td className="max-w-64 px-4 py-3 text-zinc-600">{vacancy.profile_ids.map((id) => profileLabel(id, selectableProfiles)).join(", ") || "—"}</td></tr>)}</tbody></table></section><div className="flex flex-wrap items-center justify-between gap-3 text-sm text-zinc-500"><span>Показано {filters.offset + 1}-{filters.offset + vacancies.data.items.length} из {vacancies.data.total}</span><div className="flex items-center gap-2"><label className="inline-flex items-center gap-2">На странице<select value={filters.limit} onChange={(event) => updateFilters({ limit: event.target.value })} className="border border-line bg-white px-2 py-1"><option value="25">25</option><option value="50">50</option><option value="100">100</option></select></label><button type="button" onClick={() => updateFilters({ offset: String(Math.max(0, filters.offset - filters.limit)) }, false)} disabled={!hasPreviousPage} className="inline-flex size-8 items-center justify-center border border-line bg-white disabled:text-zinc-300" aria-label="Предыдущая страница"><ChevronLeft size={16} /></button><button type="button" onClick={() => updateFilters({ offset: String(filters.offset + filters.limit) }, false)} disabled={!hasNextPage} className="inline-flex size-8 items-center justify-center border border-line bg-white disabled:text-zinc-300" aria-label="Следующая страница"><ChevronRight size={16} /></button></div></div></>}
    </div>
  );
}
