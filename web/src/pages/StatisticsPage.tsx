import { useSearchParams } from "react-router-dom";

import { EmptyState, ErrorState, LoadingState } from "../components/States";
import { useStatistics } from "../hooks/useOrchestrator";
import type { StatisticsPeriod } from "../types/api";

const periodOptions: Array<{ value: StatisticsPeriod; label: string }> = [
  { value: "today", label: "Сегодня" },
  { value: "7d", label: "7 дней" },
  { value: "14d", label: "14 дней" },
  { value: "30d", label: "30 дней" },
  { value: "all", label: "Всё время" },
  { value: "custom", label: "Свой период" }
];

const metricLabels = [
  ["found", "Найдено"],
  ["reviewed", "Рассмотрено"],
  ["applications", "Отклики"],
  ["responses", "Ответы"],
  ["interviews", "Интервью"],
  ["rejections", "Отказы"],
  ["active_processes", "Активные процессы"],
  ["offers", "Офферы"]
] as const;

function isPeriod(value: string | null): value is StatisticsPeriod {
  return periodOptions.some((option) => option.value === value);
}

export function StatisticsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const periodParameter = searchParams.get("period");
  const period: StatisticsPeriod = isPeriod(periodParameter) ? periodParameter : "30d";
  const dateFrom = searchParams.get("date_from") ?? "";
  const dateTo = searchParams.get("date_to") ?? "";
  const invalidRange = period === "custom" && Boolean(dateFrom && dateTo && dateFrom > dateTo);
  const statistics = useStatistics({
    period,
    date_from: period === "custom" ? dateFrom || undefined : undefined,
    date_to: period === "custom" ? dateTo || undefined : undefined
  });

  const updateParams = (next: { period?: StatisticsPeriod; dateFrom?: string; dateTo?: string }) => {
    const params = new URLSearchParams(searchParams);
    const nextPeriod = next.period ?? period;
    params.set("period", nextPeriod);
    if (nextPeriod === "custom") {
      const nextDateFrom = next.dateFrom ?? dateFrom;
      const nextDateTo = next.dateTo ?? dateTo;
      if (nextDateFrom) params.set("date_from", nextDateFrom); else params.delete("date_from");
      if (nextDateTo) params.set("date_to", nextDateTo); else params.delete("date_to");
    } else {
      params.delete("date_from");
      params.delete("date_to");
    }
    setSearchParams(params);
  };

  return <div className="space-y-6">
    <header className="flex flex-wrap items-end justify-between gap-4">
      <div><p className="text-sm font-medium text-zinc-500">Рабочая панель</p><h1 className="mt-1 text-2xl font-semibold">Статистика вакансий</h1></div>
      <label className="grid gap-1 text-sm font-medium text-zinc-700">Период
        <select aria-label="Период" value={period} onChange={(event) => updateParams({ period: event.target.value as StatisticsPeriod })} className="border border-zinc-300 bg-white px-3 py-2 text-sm">
          {periodOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
        </select>
      </label>
    </header>

    {period === "custom" ? <div className="flex flex-wrap gap-3 border-y border-line py-4">
      <label className="grid gap-1 text-sm font-medium text-zinc-700">Дата начала<input aria-label="Дата начала" type="date" value={dateFrom} onChange={(event) => updateParams({ dateFrom: event.target.value })} className="border border-zinc-300 bg-white px-3 py-2 text-sm" /></label>
      <label className="grid gap-1 text-sm font-medium text-zinc-700">Дата окончания<input aria-label="Дата окончания" type="date" value={dateTo} onChange={(event) => updateParams({ dateTo: event.target.value })} className="border border-zinc-300 bg-white px-3 py-2 text-sm" /></label>
      {invalidRange ? <p role="alert" className="self-end pb-2 text-sm text-danger">Дата начала не может быть позже даты окончания.</p> : null}
    </div> : null}

    {statistics.isLoading ? <LoadingState label="Загрузка статистики…" /> : null}
    {statistics.isError ? <ErrorState message="Не удалось загрузить статистику." /> : null}
    {statistics.data ? <>
      <section aria-label="Сводная статистика" className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {metricLabels.map(([key, label]) => <article key={key} className="border border-line bg-white p-4"><p className="text-sm text-zinc-500">{label}</p><p className="mt-2 text-2xl font-semibold tabular-nums">{statistics.data[key]}</p></article>)}
      </section>
      {statistics.data.found === 0 ? <EmptyState title="За выбранный период вакансий нет" detail="Выберите другой период или дождитесь следующего поиска." /> : null}
      {statistics.data.legacy_without_date > 0 ? <p className="text-sm text-zinc-500">Вакансий без надёжной даты cohort: {statistics.data.legacy_without_date}. Они учитываются только за всё время.</p> : null}
    </> : null}
  </div>;
}
