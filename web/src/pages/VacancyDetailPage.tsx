import { ArrowLeft, ExternalLink } from "lucide-react";
import { Link, useLocation, useParams } from "react-router-dom";

import { VacancyDescription } from "../components/VacancyDescription";
import { EmptyState, ErrorState, LoadingState } from "../components/States";
import { ApiError } from "../api/client";
import { useSearchProfiles, useVacancyDetail } from "../hooks/useOrchestrator";
import { formatDate, formatDateTime } from "../lib/format";
import type { VacancyPriority } from "../types/api";

type ListLocation = { pathname: string; search: string };

const priorityClasses: Record<VacancyPriority, string> = {
  P1: "bg-emerald-50 text-emerald-800",
  P2: "bg-sky-50 text-sky-800",
  P3: "bg-zinc-100 text-zinc-700",
  ALT: "bg-amber-50 text-amber-800"
};

function profileLabel(profileId: string, profiles: Array<{ id: string; name: string }>): string {
  return profiles.find((profile) => profile.id === profileId)?.name ?? profileId;
}

function experienceLabel(minimum: number | null, maximum: number | null): string | null {
  if (minimum === null && maximum === null) return null;
  if (minimum !== null && maximum !== null) return `${minimum}–${maximum} лет`;
  if (minimum !== null) return `от ${minimum} лет`;
  return `до ${maximum} лет`;
}

function TechnicalLabels({ values }: { values: string[] }) {
  return values.length ? <div className="mt-2 flex flex-wrap gap-2">{values.map((value) => <span key={value} className="bg-zinc-100 px-2 py-1 text-xs text-zinc-700">{value.replaceAll("_", " ")}</span>)}</div> : <p className="mt-2 text-sm text-zinc-500">Нет</p>;
}

export function VacancyDetailPage() {
  const { presentationKey = "" } = useParams();
  const location = useLocation();
  const detail = useVacancyDetail(presentationKey);
  const profiles = useSearchProfiles();
  const backTarget = ((location.state as { from?: ListLocation } | null)?.from) ?? { pathname: "/vacancies", search: "" };
  const profileMetadata = profiles.data?.profiles ?? [];

  if (detail.isLoading) return <LoadingState label="Загрузка вакансии…" />;
  if (detail.isError) {
    if (detail.error instanceof ApiError && detail.error.status === 404) {
      return <div className="space-y-5"><EmptyState title="Вакансия не найдена" detail="Эта logical vacancy больше недоступна в Orchestrator." /><Link to={backTarget} className="inline-flex items-center gap-2 border border-line bg-white px-3 py-2 text-sm font-medium text-zinc-700"><ArrowLeft size={16} />К вакансиям</Link></div>;
    }
    return <div className="space-y-5"><ErrorState message="Не удалось загрузить вакансию." /><Link to={backTarget} className="inline-flex items-center gap-2 border border-line bg-white px-3 py-2 text-sm font-medium text-zinc-700"><ArrowLeft size={16} />К вакансиям</Link></div>;
  }
  if (!detail.data) return null;

  const vacancy = detail.data;
  const experience = experienceLabel(vacancy.experience_min_years, vacancy.experience_max_years);

  return <div className="space-y-6">
    <header className="space-y-4">
      <Link to={backTarget} className="inline-flex items-center gap-2 text-sm font-medium text-zinc-600 hover:text-zinc-950"><ArrowLeft size={16} />Назад к вакансиям</Link>
      <div className="flex flex-wrap items-start justify-between gap-4"><div><p className="text-sm font-medium text-zinc-500">{vacancy.company}</p><h1 className="mt-1 max-w-4xl text-2xl font-semibold leading-tight">{vacancy.title}</h1></div><a href={vacancy.url} target="_blank" rel="noopener noreferrer" className="inline-flex shrink-0 items-center gap-2 bg-zinc-900 px-4 py-2.5 text-sm font-medium text-white hover:bg-zinc-700"><ExternalLink size={17} />Открыть оригинал</a></div>
    </header>

    <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_320px]">
      <main className="min-w-0 space-y-6"><VacancyDescription description={vacancy.description} />
        {vacancy.member_count > 1 && <section className="border border-line bg-white p-5"><h2 className="text-lg font-semibold">Региональные копии: {vacancy.member_count}</h2><ul className="mt-4 divide-y divide-line">{vacancy.members.map((member) => <li key={`${member.source}:${member.external_id}`} className="flex flex-wrap items-center justify-between gap-3 py-3 first:pt-0 last:pb-0"><div><p className="font-medium">{member.location ?? "Локация не указана"}{member.representative && <span className="ml-2 bg-zinc-900 px-2 py-0.5 text-xs font-semibold text-white">Представитель</span>}</p><p className="mt-1 font-mono text-xs text-zinc-500">{member.source}:{member.external_id}</p></div><a href={member.url} target="_blank" rel="noopener noreferrer" className="text-sm font-medium text-zinc-700 underline decoration-zinc-300 underline-offset-4 hover:decoration-zinc-900">Открыть</a></li>)}</ul></section>}
        <details className="border border-line bg-white p-5"><summary className="cursor-pointer text-sm font-semibold">Техническая информация</summary><dl className="mt-4 grid gap-3 text-sm md:grid-cols-2"><div><dt className="text-zinc-500">Presentation key</dt><dd className="mt-1 break-all font-mono text-xs">{vacancy.presentation_key}</dd></div><div><dt className="text-zinc-500">Run IDs</dt><dd className="mt-1 break-all font-mono text-xs">{vacancy.run_ids.join(", ") || "—"}</dd></div>{vacancy.query_variant_ids.length > 0 && <div><dt className="text-zinc-500">Query variants</dt><dd className="mt-1 break-all font-mono text-xs">{vacancy.query_variant_ids.join(", ")}</dd></div>}{vacancy.provenance_tracks.length > 0 && <div><dt className="text-zinc-500">Provenance tracks</dt><dd className="mt-1">{vacancy.provenance_tracks.join(", ")}</dd></div>}</dl></details>
      </main>

      <aside className="space-y-4"><section className="border border-line bg-white p-5"><div className="flex items-center justify-between gap-3"><h2 className="font-semibold">Оценка</h2>{vacancy.analysis.priority && <span className={`px-2 py-1 text-xs font-semibold ${priorityClasses[vacancy.analysis.priority]}`}>{vacancy.analysis.priority}</span>}</div><dl className="mt-4 space-y-3 text-sm"><div className="flex justify-between gap-3"><dt className="text-zinc-500">Score</dt><dd className="font-semibold">{vacancy.analysis.final_score ?? "—"}</dd></div><div className="flex justify-between gap-3"><dt className="text-zinc-500">Track</dt><dd>{vacancy.analysis.track ?? "—"}</dd></div></dl><div className="mt-4 border-t border-line pt-4"><p className="text-sm font-medium">Кратко</p><p className="mt-2 text-sm leading-6 text-zinc-700">{vacancy.analysis.summary}</p></div><div className="mt-4"><p className="text-sm font-medium">Почему</p><p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-zinc-700">{vacancy.analysis.reason}</p></div>{(vacancy.analysis.risks.length > 0 || vacancy.analysis.hard_blockers.length > 0) && <div className="mt-4 border-t border-line pt-4">{vacancy.analysis.risks.length > 0 && <div><p className="text-sm font-medium">Риски</p><TechnicalLabels values={vacancy.analysis.risks} /></div>}{vacancy.analysis.hard_blockers.length > 0 && <div className="mt-3"><p className="text-sm font-medium">Ограничения</p><TechnicalLabels values={vacancy.analysis.hard_blockers} /></div>}</div>}</section>
        <section className="border border-line bg-white p-5"><h2 className="font-semibold">Детали</h2><dl className="mt-4 space-y-3 text-sm"><div><dt className="text-zinc-500">Зарплата</dt><dd className="mt-1">{vacancy.salary_text ?? "—"}</dd></div><div><dt className="text-zinc-500">Локация</dt><dd className="mt-1">{vacancy.location ?? "—"}</dd></div>{vacancy.work_format && <div><dt className="text-zinc-500">Формат</dt><dd className="mt-1">{vacancy.work_format}</dd></div>}{vacancy.working_hours && <div><dt className="text-zinc-500">Рабочие часы</dt><dd className="mt-1">{vacancy.working_hours}</dd></div>}{experience && <div><dt className="text-zinc-500">Опыт</dt><dd className="mt-1">{experience}</dd></div>}<div><dt className="text-zinc-500">Опубликована</dt><dd className="mt-1">{formatDate(vacancy.published_at)}</dd></div><div><dt className="text-zinc-500">Обнаружена системой</dt><dd className="mt-1">{formatDateTime(vacancy.first_seen_at)}</dd></div><div><dt className="text-zinc-500">Последнее обнаружение</dt><dd className="mt-1">{formatDateTime(vacancy.last_seen_at)}</dd></div></dl>{vacancy.skills.length > 0 && <div className="mt-4 border-t border-line pt-4"><p className="text-sm font-medium">Стек</p><TechnicalLabels values={vacancy.skills} /></div>}</section>
        <section className="border border-line bg-white p-5"><h2 className="font-semibold">Профили поиска</h2><div className="mt-3 flex flex-wrap gap-2">{vacancy.profile_ids.map((profileId) => <span key={profileId} className="bg-zinc-100 px-2 py-1 text-xs text-zinc-700">{profileLabel(profileId, profileMetadata)}</span>)}</div></section>
        <section className="border border-dashed border-zinc-300 bg-zinc-50 p-5"><h2 className="font-semibold">Отклики</h2><p className="mt-2 text-sm text-zinc-500">Нет данных</p></section>
      </aside>
    </div>
  </div>;
}
