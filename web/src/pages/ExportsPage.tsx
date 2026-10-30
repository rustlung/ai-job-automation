import { useEffect, useMemo, useState } from "react";
import { Download, RotateCcw } from "lucide-react";

import { ErrorState, LoadingState } from "../components/States";
import { useDownloadApplicationExport, useDownloadVacancyExport, useExportSchema } from "../hooks/useOrchestrator";
import { downloadBlob, filenameFromContentDisposition } from "../lib/download";
import type { ExportColumnCategory, ExportColumnDefinition, ExportEntity, ExportFormat, ExportPeriod, ExportRequest } from "../types/api";

const entityOptions: Array<{ value: ExportEntity; label: string }> = [
  { value: "vacancies", label: "Вакансии" },
  { value: "applications", label: "Отклики" }
];
const periodLabels: Record<ExportPeriod, string> = {
  all: "Всё время",
  "7d": "Последние 7 дней",
  "30d": "Последние 30 дней",
  custom: "Произвольный период"
};
const formatLabels: Record<ExportFormat, string> = {
  xlsx: "Excel (.xlsx)",
  csv: "CSV (.csv)"
};
const categoryLabels: Record<ExportColumnCategory, string> = {
  business: "Основные",
  ai: "AI",
  technical: "Технические"
};
const categoryOrder: ExportColumnCategory[] = ["business", "ai", "technical"];
const emptyColumns: ExportColumnDefinition[] = [];
const emptyPeriods: ExportPeriod[] = [];
const emptyFormats: ExportFormat[] = [];

function defaults(columns: Array<{ key: string; default_enabled: boolean }>): string[] {
  return columns.filter((column) => column.default_enabled).map((column) => column.key);
}

export function ExportsPage() {
  const schema = useExportSchema();
  const vacancyDownload = useDownloadVacancyExport();
  const applicationDownload = useDownloadApplicationExport();
  const [entity, setEntity] = useState<ExportEntity>("vacancies");
  const [period, setPeriod] = useState<ExportPeriod>("all");
  const [format, setFormat] = useState<ExportFormat>("xlsx");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [selectedColumns, setSelectedColumns] = useState<string[]>([]);
  const [downloadError, setDownloadError] = useState(false);

  const columns = schema.data?.[entity] ?? emptyColumns;
  const supportedPeriods = schema.data?.periods ?? emptyPeriods;
  const supportedFormats = schema.data?.formats ?? emptyFormats;
  const activeDownload = entity === "vacancies" ? vacancyDownload : applicationDownload;
  const invalidRange = period === "custom" && (!dateFrom || !dateTo || dateFrom > dateTo);
  const canDownload = selectedColumns.length > 0 && !invalidRange && !activeDownload.isPending;

  useEffect(() => {
    if (schema.data) setSelectedColumns(defaults(schema.data[entity]));
  }, [entity, schema.data]);

  useEffect(() => {
    if (supportedFormats.length && !supportedFormats.includes(format)) setFormat(supportedFormats[0]);
  }, [format, supportedFormats]);

  const columnsByCategory = useMemo(() => categoryOrder.map((category) => ({
    category,
    columns: columns.filter((column) => column.category === category)
  })).filter((group) => group.columns.length), [columns]);

  const resetColumns = () => setSelectedColumns(defaults(columns));
  const toggleColumn = (key: string) => setSelectedColumns((current) => current.includes(key) ? current.filter((item) => item !== key) : [...current, key]);

  const onDownload = async () => {
    if (!canDownload) return;
    setDownloadError(false);
    const request: ExportRequest = {
      format,
      period,
      columns: selectedColumns,
      ...(period === "custom" ? { date_from: dateFrom, date_to: dateTo } : {})
    };
    try {
      const result = await activeDownload.mutateAsync(request);
      const fallback = `${entity}-export.${format}`;
      downloadBlob(result.blob, filenameFromContentDisposition(result.filename, fallback));
    } catch {
      setDownloadError(true);
    }
  };

  if (schema.isLoading) return <LoadingState label="Загрузка параметров экспорта…" />;
  if (schema.isError || !schema.data) return <ErrorState message="Не удалось загрузить параметры экспорта." />;

  return <div className="space-y-6">
    <header><p className="text-sm font-medium text-zinc-500">Orchestrator DB</p><h1 className="mt-1 text-2xl font-semibold">Экспорт данных</h1><p className="mt-2 max-w-2xl text-sm text-zinc-600">Сформируйте файл из текущих данных. Настройки действуют только для этой выгрузки.</p></header>

    <section className="space-y-6 border border-line bg-white p-5">
      <fieldset>
        <legend className="text-sm font-semibold text-zinc-900">Тип данных</legend>
        <div className="mt-3 flex flex-wrap gap-2">{entityOptions.map((option) => <button key={option.value} type="button" aria-pressed={entity === option.value} onClick={() => setEntity(option.value)} className={`border px-3 py-2 text-sm font-medium ${entity === option.value ? "border-zinc-900 bg-zinc-900 text-white" : "border-line bg-white text-zinc-700"}`}>{option.label}</button>)}</div>
      </fieldset>

      <fieldset>
        <legend className="text-sm font-semibold text-zinc-900">Период</legend>
        <div className="mt-3 flex flex-wrap gap-2">{supportedPeriods.map((option) => <button key={option} type="button" aria-pressed={period === option} onClick={() => setPeriod(option)} className={`border px-3 py-2 text-sm font-medium ${period === option ? "border-zinc-900 bg-zinc-900 text-white" : "border-line bg-white text-zinc-700"}`}>{periodLabels[option]}</button>)}</div>
        {period === "custom" ? <div className="mt-4 flex flex-wrap gap-3"><label className="grid gap-1 text-sm font-medium text-zinc-700">С даты<input aria-label="С даты" type="date" value={dateFrom} onChange={(event) => setDateFrom(event.target.value)} className="border border-line px-3 py-2 font-normal" /></label><label className="grid gap-1 text-sm font-medium text-zinc-700">По дату<input aria-label="По дату" type="date" value={dateTo} onChange={(event) => setDateTo(event.target.value)} className="border border-line px-3 py-2 font-normal" /></label></div> : null}
        {period === "custom" && invalidRange ? <p role="alert" className="mt-3 text-sm text-danger">Укажите корректный диапазон дат.</p> : null}
      </fieldset>

      <fieldset>
        <div className="flex flex-wrap items-center justify-between gap-3"><legend className="text-sm font-semibold text-zinc-900">Колонки</legend><div className="flex gap-2"><button type="button" onClick={() => setSelectedColumns(columns.map((column) => column.key))} className="border border-line bg-white px-3 py-1.5 text-sm font-medium text-zinc-700">Выбрать все</button><button type="button" onClick={resetColumns} className="inline-flex items-center gap-1 border border-line bg-white px-3 py-1.5 text-sm font-medium text-zinc-700"><RotateCcw size={14} />По умолчанию</button></div></div>
        <div className="mt-4 space-y-5">{columnsByCategory.map((group) => <div key={group.category}><h2 className="text-xs font-semibold uppercase text-zinc-500">{categoryLabels[group.category]}</h2><div className="mt-2 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">{group.columns.map((column) => <label key={column.key} className="flex items-center gap-2 text-sm text-zinc-700"><input type="checkbox" checked={selectedColumns.includes(column.key)} onChange={() => toggleColumn(column.key)} />{column.label}</label>)}</div></div>)}</div>
        {!selectedColumns.length ? <p role="alert" className="mt-3 text-sm text-danger">Выберите хотя бы одну колонку.</p> : null}
      </fieldset>

      <fieldset>
        <legend className="text-sm font-semibold text-zinc-900">Формат</legend>
        <div className="mt-3 flex flex-wrap gap-2">{supportedFormats.map((option) => <button key={option} type="button" aria-pressed={format === option} onClick={() => setFormat(option)} className={`border px-3 py-2 text-sm font-medium ${format === option ? "border-zinc-900 bg-zinc-900 text-white" : "border-line bg-white text-zinc-700"}`}>{formatLabels[option]}</button>)}</div>
      </fieldset>

      {downloadError ? <p role="alert" className="text-sm text-danger">Не удалось сформировать выгрузку.</p> : null}
      <button type="button" disabled={!canDownload} onClick={onDownload} className="inline-flex items-center gap-2 bg-zinc-900 px-4 py-2.5 text-sm font-medium text-white disabled:cursor-not-allowed disabled:bg-zinc-400"><Download size={16} />{activeDownload.isPending ? "Формирование файла..." : "Скачать"}</button>
    </section>
  </div>;
}
