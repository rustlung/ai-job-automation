import { useEffect, useMemo, useState, type Dispatch, type SetStateAction } from "react";
import { Download, RotateCcw } from "lucide-react";

import { ErrorState, LoadingState } from "../components/States";
import { useDownloadApplicationExport, useDownloadVacancyExport, useExportSchema, useSearchProfiles } from "../hooks/useOrchestrator";
import { applicationStatusLabels } from "../lib/applicationStatus";
import { downloadBlob, filenameFromContentDisposition } from "../lib/download";
import { vacancyStatusLabels } from "../lib/vacancyStatus";
import type { ApplicationExportFilters, ApplicationStatus, ExportColumnCategory, ExportColumnDefinition, ExportEntity, ExportFormat, ExportRequest, VacancyApplicationStatusFilter, VacancyExportFilters, VacancyPriority, VacancyProcessingFilter, VacancyStatusFilter, VacancyUserPriorityFilter } from "../types/api";

const entityOptions: Array<{ value: ExportEntity; label: string }> = [{ value: "vacancies", label: "Вакансии" }, { value: "applications", label: "Отклики" }];
const formatLabels: Record<ExportFormat, string> = { xlsx: "Excel (.xlsx)", csv: "CSV (.csv)" };
const categoryLabels: Record<ExportColumnCategory, string> = { business: "Основные", ai: "AI", technical: "Технические" };
const categoryOrder: ExportColumnCategory[] = ["business", "ai", "technical"];
const priorityOptions: VacancyPriority[] = ["P1", "P2", "P3", "ALT"];
const processingOptions: Array<{ value: VacancyProcessingFilter; label: string }> = [{ value: "working", label: "Рабочие" }, { value: "rejected", label: "Отклонённые" }, { value: "errors", label: "Ошибки обработки" }, { value: "all", label: "Все" }];
const applicationStatusOptions: Array<{ value: VacancyApplicationStatusFilter; label: string }> = [{ value: "none", label: "Без отклика" }, ...Object.entries(applicationStatusLabels).map(([value, label]) => ({ value: value as ApplicationStatus, label }))];
const vacancyStatusOptions: Array<{ value: VacancyStatusFilter; label: string }> = Object.entries(vacancyStatusLabels).map(([value, label]) => ({ value: value as VacancyStatusFilter, label }));
const userPriorityOptions: Array<{ value: VacancyUserPriorityFilter; label: string }> = [{ value: "P1", label: "P1" }, { value: "P2", label: "P2" }, { value: "P3", label: "P3" }, { value: "none", label: "Не оценено" }];
const emptyColumns: ExportColumnDefinition[] = [];
const emptyFormats: ExportFormat[] = [];

function defaults(columns: Array<{ key: string; default_enabled: boolean }>): string[] { return columns.filter((column) => column.default_enabled).map((column) => column.key); }
function defaultVacancyFilters(): VacancyExportFilters { return { priority: [], processing: "working", sort: "first_seen", sort_direction: "desc" }; }
function defaultApplicationFilters(): ApplicationExportFilters { return {}; }
function optional(value: string): string | undefined { return value || undefined; }

export function ExportsPage() {
  const schema = useExportSchema();
  const profiles = useSearchProfiles();
  const vacancyDownload = useDownloadVacancyExport();
  const applicationDownload = useDownloadApplicationExport();
  const [entity, setEntity] = useState<ExportEntity>("vacancies");
  const [format, setFormat] = useState<ExportFormat>("xlsx");
  const [vacancyFilters, setVacancyFilters] = useState<VacancyExportFilters>(defaultVacancyFilters);
  const [applicationFilters, setApplicationFilters] = useState<ApplicationExportFilters>(defaultApplicationFilters);
  const [selectedColumns, setSelectedColumns] = useState<string[]>([]);
  const [downloadError, setDownloadError] = useState(false);
  const columns = schema.data?.[entity] ?? emptyColumns;
  const supportedFormats = schema.data?.formats ?? emptyFormats;
  const activeDownload = entity === "vacancies" ? vacancyDownload : applicationDownload;
  const enabledProfiles = profiles.data?.profiles.filter((profile) => profile.enabled) ?? [];
  const canDownload = selectedColumns.length > 0 && !activeDownload.isPending;

  useEffect(() => { if (schema.data) setSelectedColumns(defaults(schema.data[entity])); }, [entity, schema.data]);
  useEffect(() => { if (supportedFormats.length && !supportedFormats.includes(format)) setFormat(supportedFormats[0]); }, [format, supportedFormats]);

  const columnsByCategory = useMemo(() => categoryOrder.map((category) => ({ category, columns: columns.filter((column) => column.category === category) })).filter((group) => group.columns.length), [columns]);
  const toggleColumn = (key: string) => setSelectedColumns((current) => current.includes(key) ? current.filter((item) => item !== key) : [...current, key]);
  const togglePriority = (priority: VacancyPriority) => setVacancyFilters((current) => ({ ...current, priority: current.priority?.includes(priority) ? current.priority.filter((item) => item !== priority) : [...(current.priority ?? []), priority] }));
  const resetFilters = () => entity === "vacancies" ? setVacancyFilters(defaultVacancyFilters()) : setApplicationFilters(defaultApplicationFilters());
  const onDownload = async () => {
    if (!canDownload) return;
    setDownloadError(false);
    const request: ExportRequest = { format, period: "all", columns: selectedColumns, ...(entity === "vacancies" ? { vacancy_filters: vacancyFilters } : { application_filters: applicationFilters }) };
    try {
      const result = await activeDownload.mutateAsync(request);
      downloadBlob(result.blob, filenameFromContentDisposition(result.filename, `${entity}-export.${format}`));
    } catch { setDownloadError(true); }
  };

  if (schema.isLoading) return <LoadingState label="Загрузка параметров экспорта…" />;
  if (schema.isError || !schema.data) return <ErrorState message="Не удалось загрузить параметры экспорта." />;

  return <div className="space-y-6">
    <header><p className="text-sm font-medium text-zinc-500">Orchestrator DB</p><h1 className="mt-1 text-2xl font-semibold">Экспорт данных</h1><p className="mt-2 max-w-2xl text-sm text-zinc-600">Настройте выборку и скачайте все записи, соответствующие указанным фильтрам.</p></header>
    <section className="space-y-6 border border-line bg-white p-5">
      <fieldset><legend className="text-sm font-semibold text-zinc-900">Тип данных</legend><div className="mt-3 flex flex-wrap gap-2">{entityOptions.map((option) => <button key={option.value} type="button" aria-pressed={entity === option.value} onClick={() => setEntity(option.value)} className={`border px-3 py-2 text-sm font-medium ${entity === option.value ? "border-zinc-900 bg-zinc-900 text-white" : "border-line bg-white text-zinc-700"}`}>{option.label}</button>)}</div></fieldset>
      <fieldset className="border-y border-line py-5"><div className="flex flex-wrap items-center justify-between gap-3"><legend className="text-sm font-semibold text-zinc-900">Фильтры</legend><button type="button" onClick={resetFilters} className="inline-flex items-center gap-1 border border-line bg-white px-3 py-1.5 text-sm font-medium text-zinc-700"><RotateCcw size={14} />Сбросить фильтры</button></div>{entity === "vacancies" ? <VacancyFilterPanel filters={vacancyFilters} profiles={enabledProfiles} profilesUnavailable={profiles.isLoading || profiles.isError} onChange={setVacancyFilters} onTogglePriority={togglePriority} /> : <ApplicationFilterPanel filters={applicationFilters} onChange={setApplicationFilters} />}</fieldset>
      <fieldset><div className="flex flex-wrap items-center justify-between gap-3"><legend className="text-sm font-semibold text-zinc-900">Колонки</legend><div className="flex gap-2"><button type="button" onClick={() => setSelectedColumns(columns.map((column) => column.key))} className="border border-line bg-white px-3 py-1.5 text-sm font-medium text-zinc-700">Выбрать все</button><button type="button" onClick={() => setSelectedColumns(defaults(columns))} className="inline-flex items-center gap-1 border border-line bg-white px-3 py-1.5 text-sm font-medium text-zinc-700"><RotateCcw size={14} />По умолчанию</button></div></div><div className="mt-4 space-y-5">{columnsByCategory.map((group) => <div key={group.category}><h2 className="text-xs font-semibold uppercase text-zinc-500">{categoryLabels[group.category]}</h2><div className="mt-2 grid min-w-0 gap-2 sm:grid-cols-2 lg:grid-cols-3">{group.columns.map((column) => <label key={column.key} className="flex min-w-0 items-center gap-2 break-words text-sm text-zinc-700"><input type="checkbox" checked={selectedColumns.includes(column.key)} onChange={() => toggleColumn(column.key)} />{column.label}</label>)}</div></div>)}</div>{!selectedColumns.length ? <p role="alert" className="mt-3 text-sm text-danger">Выберите хотя бы одну колонку.</p> : null}</fieldset>
      <fieldset><legend className="text-sm font-semibold text-zinc-900">Формат</legend><div className="mt-3 flex flex-wrap gap-2">{supportedFormats.map((option) => <button key={option} type="button" aria-pressed={format === option} onClick={() => setFormat(option)} className={`border px-3 py-2 text-sm font-medium ${format === option ? "border-zinc-900 bg-zinc-900 text-white" : "border-line bg-white text-zinc-700"}`}>{formatLabels[option]}</button>)}</div></fieldset>
      {downloadError ? <p role="alert" className="text-sm text-danger">Не удалось сформировать выгрузку.</p> : null}<button type="button" disabled={!canDownload} onClick={onDownload} className="inline-flex items-center gap-2 bg-zinc-900 px-4 py-2.5 text-sm font-medium text-white disabled:cursor-not-allowed disabled:bg-zinc-400"><Download size={16} />{activeDownload.isPending ? "Формирование файла..." : "Скачать выгрузку"}</button>
    </section>
  </div>;
}

function VacancyFilterPanel({ filters, profiles, profilesUnavailable, onChange, onTogglePriority }: { filters: VacancyExportFilters; profiles: Array<{ id: string; name: string }>; profilesUnavailable: boolean; onChange: Dispatch<SetStateAction<VacancyExportFilters>>; onTogglePriority: (priority: VacancyPriority) => void }) {
  return <div className="mt-4 grid min-w-0 gap-3 sm:grid-cols-2 lg:grid-cols-3">
    <label className="grid min-w-0 gap-1 text-sm font-medium text-zinc-700">Обработка<select aria-label="Обработка" value={filters.processing ?? "working"} onChange={(event) => onChange((current) => ({ ...current, processing: event.target.value as VacancyProcessingFilter }))} className="border border-line bg-white px-3 py-2 font-normal">{processingOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>
    <label className="grid min-w-0 gap-1 text-sm font-medium text-zinc-700">С даты<input aria-label="С даты вакансий" type="date" value={filters.date_from ?? ""} onChange={(event) => onChange((current) => ({ ...current, date_from: optional(event.target.value) }))} className="border border-line px-3 py-2 font-normal" /></label><label className="grid min-w-0 gap-1 text-sm font-medium text-zinc-700">По дату<input aria-label="По дату вакансий" type="date" value={filters.date_to ?? ""} onChange={(event) => onChange((current) => ({ ...current, date_to: optional(event.target.value) }))} className="border border-line px-3 py-2 font-normal" /></label>
    <label className="grid min-w-0 gap-1 text-sm font-medium text-zinc-700">Трек<input aria-label="Трек" value={filters.track ?? ""} onChange={(event) => onChange((current) => ({ ...current, track: optional(event.target.value) }))} className="border border-line px-3 py-2 font-normal" /></label><label className="grid min-w-0 gap-1 text-sm font-medium text-zinc-700">Профиль поиска<select aria-label="Профиль поиска" value={filters.profile_id ?? ""} onChange={(event) => onChange((current) => ({ ...current, profile_id: optional(event.target.value) }))} disabled={profilesUnavailable} className="border border-line bg-white px-3 py-2 font-normal"><option value="">Все профили</option>{profiles.map((profile) => <option key={profile.id} value={profile.id}>{profile.name}</option>)}</select></label>
    <label className="grid min-w-0 gap-1 text-sm font-medium text-zinc-700">Статус отклика<select aria-label="Статус отклика вакансий" value={filters.application_status ?? ""} onChange={(event) => onChange((current) => ({ ...current, application_status: optional(event.target.value) as VacancyApplicationStatusFilter | undefined }))} className="border border-line bg-white px-3 py-2 font-normal"><option value="">Все статусы</option>{applicationStatusOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>
    <label className="grid min-w-0 gap-1 text-sm font-medium text-zinc-700">Статус вакансии<select aria-label="Статус вакансии" value={filters.vacancy_status ?? ""} onChange={(event) => onChange((current) => ({ ...current, vacancy_status: optional(event.target.value) as VacancyStatusFilter | undefined }))} className="border border-line bg-white px-3 py-2 font-normal"><option value="">Все статусы</option>{vacancyStatusOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label><label className="grid min-w-0 gap-1 text-sm font-medium text-zinc-700">Мой приоритет<select aria-label="Мой приоритет" value={filters.user_priority ?? ""} onChange={(event) => onChange((current) => ({ ...current, user_priority: optional(event.target.value) as VacancyUserPriorityFilter | undefined }))} className="border border-line bg-white px-3 py-2 font-normal"><option value="">Все приоритеты</option>{userPriorityOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>
    <label className="grid min-w-0 gap-1 text-sm font-medium text-zinc-700">Run ID<input aria-label="Run ID" value={filters.run_id ?? ""} onChange={(event) => onChange((current) => ({ ...current, run_id: optional(event.target.value) }))} className="border border-line px-3 py-2 font-normal" /></label><label className="grid min-w-0 gap-1 text-sm font-medium text-zinc-700">Поиск<input aria-label="Поиск вакансий" value={filters.search ?? ""} onChange={(event) => onChange((current) => ({ ...current, search: optional(event.target.value) }))} className="border border-line px-3 py-2 font-normal" placeholder="Компания или вакансия" /></label>
    <label className="grid min-w-0 gap-1 text-sm font-medium text-zinc-700">Сортировка<select aria-label="Сортировка" value={filters.sort ?? "first_seen"} onChange={(event) => onChange((current) => ({ ...current, sort: event.target.value as VacancyExportFilters["sort"] }))} className="border border-line bg-white px-3 py-2 font-normal"><option value="first_seen">Дата обнаружения</option><option value="final_score">AI score</option><option value="priority">AI priority</option></select></label><label className="grid min-w-0 gap-1 text-sm font-medium text-zinc-700">Направление<select aria-label="Направление сортировки" value={filters.sort_direction ?? "desc"} onChange={(event) => onChange((current) => ({ ...current, sort_direction: event.target.value as VacancyExportFilters["sort_direction"] }))} className="border border-line bg-white px-3 py-2 font-normal"><option value="desc">По убыванию</option><option value="asc">По возрастанию</option></select></label>
    <div className="min-w-0 sm:col-span-2 lg:col-span-3"><span className="block text-sm font-medium text-zinc-700">AI приоритет</span><div className="mt-2 flex flex-wrap gap-3">{priorityOptions.map((priority) => <label key={priority} className="inline-flex items-center gap-2 text-sm text-zinc-700"><input type="checkbox" checked={filters.priority?.includes(priority) ?? false} onChange={() => onTogglePriority(priority)} />{priority}</label>)}</div></div>
  </div>;
}

function ApplicationFilterPanel({ filters, onChange }: { filters: ApplicationExportFilters; onChange: Dispatch<SetStateAction<ApplicationExportFilters>> }) {
  return <div className="mt-4 grid min-w-0 gap-3 sm:grid-cols-2 lg:grid-cols-3"><label className="grid min-w-0 gap-1 text-sm font-medium text-zinc-700">Статус отклика<select aria-label="Статус отклика" value={filters.status ?? ""} onChange={(event) => onChange((current) => ({ ...current, status: optional(event.target.value) as ApplicationStatus | undefined }))} className="border border-line bg-white px-3 py-2 font-normal"><option value="">Все статусы</option>{Object.entries(applicationStatusLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label><label className="grid min-w-0 gap-1 text-sm font-medium text-zinc-700">С даты<input aria-label="С даты откликов" type="date" value={filters.date_from ?? ""} onChange={(event) => onChange((current) => ({ ...current, date_from: optional(event.target.value) }))} className="border border-line px-3 py-2 font-normal" /></label><label className="grid min-w-0 gap-1 text-sm font-medium text-zinc-700">По дату<input aria-label="По дату откликов" type="date" value={filters.date_to ?? ""} onChange={(event) => onChange((current) => ({ ...current, date_to: optional(event.target.value) }))} className="border border-line px-3 py-2 font-normal" /></label><label className="grid min-w-0 gap-1 text-sm font-medium text-zinc-700">Платформа<input aria-label="Платформа" value={filters.platform ?? ""} onChange={(event) => onChange((current) => ({ ...current, platform: optional(event.target.value) }))} className="border border-line px-3 py-2 font-normal" placeholder="hh" /></label><label className="grid min-w-0 gap-1 text-sm font-medium text-zinc-700">Поиск<input aria-label="Поиск откликов" value={filters.search ?? ""} onChange={(event) => onChange((current) => ({ ...current, search: optional(event.target.value) }))} className="border border-line px-3 py-2 font-normal" placeholder="Компания или вакансия" /></label></div>;
}
