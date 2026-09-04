import { ChevronDown, CirclePlay } from "lucide-react";
import { FormEvent, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { ErrorState, LoadingState } from "../components/States";
import { useSearchProfiles, useStartRun } from "../hooks/useOrchestrator";
import { emptyOverrides, parseOptionalLimit, profileIdsFromSelection, type ProfileSelection } from "../features/run-start/selection";

export function StartRunPage() {
  const navigate = useNavigate();
  const profilesQuery = useSearchProfiles();
  const startRun = useStartRun();
  const [selection, setSelection] = useState<ProfileSelection>({});
  const [showOverrides, setShowOverrides] = useState(false);
  const [limits, setLimits] = useState({ max_pages_override: "", max_filter_items_override: "", max_enrich_items_override: "" });
  const profiles = useMemo(() => profilesQuery.data?.profiles.filter((profile) => profile.enabled) ?? [], [profilesQuery.data]);
  const selectedProfileIds = useMemo(() => profileIdsFromSelection(selection, profiles), [selection, profiles]);
  const canSubmit = selectedProfileIds.length > 0 && !startRun.isPending;

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canSubmit) return;
    startRun.mutate({ profile_ids: selectedProfileIds, overrides: {
      ...emptyOverrides,
      max_pages_override: parseOptionalLimit(limits.max_pages_override),
      max_filter_items_override: parseOptionalLimit(limits.max_filter_items_override),
      max_enrich_items_override: parseOptionalLimit(limits.max_enrich_items_override)
    } }, { onSuccess: ({ run }) => navigate(`/runs/${run.run_id}`) });
  }

  return <div className="max-w-3xl space-y-7"><header><p className="text-sm font-medium text-zinc-500">Новый запуск</p><h1 className="mt-1 text-2xl font-semibold">Запуск поиска</h1></header>{profilesQuery.isLoading ? <LoadingState label="Загрузка поисковых профилей…" /> : profilesQuery.isError ? <ErrorState message="Не удалось загрузить поисковые профили." /> : <form onSubmit={submit} className="space-y-5"><section className="border border-line bg-white p-5"><fieldset><legend className="text-base font-semibold">Search profiles</legend><div className="mt-4 space-y-2">{profiles.map((profile) => <label key={profile.id} className="flex cursor-pointer items-start gap-3 border border-line p-3 hover:border-zinc-400"><input type="checkbox" className="mt-1 size-4 accent-zinc-900" checked={selection[profile.id] === true} onChange={(event) => setSelection((current) => ({ ...current, [profile.id]: event.target.checked }))} /><span><span className="block text-sm font-medium">{profile.name}</span><span className="text-xs text-zinc-500">{profile.track === "main" ? "Main" : "Alternative"} · {profile.source_type === "expanded_search" ? "Public search" : "Resume recommendations"}</span></span></label>)}</div></fieldset></section>
    <section className="border border-line bg-white"><button type="button" onClick={() => setShowOverrides((value) => !value)} className="flex w-full items-center justify-between px-5 py-4 text-left text-sm font-medium"><span>Дополнительные параметры</span><ChevronDown className={showOverrides ? "rotate-180 transition" : "transition"} size={18} /></button>{showOverrides && <div className="grid gap-4 border-t border-line p-5 md:grid-cols-3">{([ ["max_pages_override", "Макс. страниц"], ["max_filter_items_override", "Макс. фильтр"], ["max_enrich_items_override", "Макс. enrichment"] ] as const).map(([name, label]) => <label key={name} className="text-sm font-medium text-zinc-700">{label}<input inputMode="numeric" min="1" value={limits[name]} onChange={(event) => setLimits((current) => ({ ...current, [name]: event.target.value }))} className="mt-2 block w-full border border-zinc-300 px-3 py-2 text-sm focus:border-zinc-900 focus:outline-none" /></label>)}</div>}</section>
    {!selectedProfileIds.length && <p role="status" className="text-sm text-warning">Выберите хотя бы один поисковый профиль.</p>}{startRun.isError && <ErrorState message="Не удалось запустить workflow. Проверьте доступность Orchestrator и n8n." />}<button type="submit" disabled={!canSubmit} className="inline-flex items-center gap-2 bg-zinc-900 px-4 py-2.5 text-sm font-medium text-white enabled:hover:bg-zinc-700 disabled:cursor-not-allowed disabled:bg-zinc-300"><CirclePlay size={17} />{startRun.isPending ? "Запуск…" : "Запустить поиск"}</button>
  </form>}</div>;
}
