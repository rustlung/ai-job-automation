import { Pencil, X } from "lucide-react";
import { useState } from "react";

import { useUpdateVacancyUserState } from "../hooks/useOrchestrator";
import { VacancyStatusBadge } from "./VacancyStatusBadge";
import { vacancyStatusLabels } from "../lib/vacancyStatus";
import { UserPriorityBadge } from "./UserPriorityBadge";
import type { VacancyStatus, VacancyUserPriority, VacancyUserState } from "../types/api";

type Values = { user_priority: VacancyUserPriority | ""; vacancy_status: VacancyStatus; comment: string };
const statuses: VacancyStatus[] = ["active", "archived", "closed"];

function valuesFrom(state: VacancyUserState): Values {
  return { user_priority: state.user_priority ?? "", vacancy_status: state.vacancy_status, comment: state.comment ?? "" };
}

export function VacancyUserStateSection({ state }: { state: VacancyUserState }) {
  const [editing, setEditing] = useState(false);
  const [values, setValues] = useState(() => valuesFrom(state));
  const update = useUpdateVacancyUserState();
  const save = async (event: React.FormEvent) => {
    event.preventDefault();
    try {
      await update.mutateAsync({ presentationKey: state.presentation_key, payload: {
        user_priority: values.user_priority || null,
        vacancy_status: values.vacancy_status,
        comment: values.comment.trim() || null
      } });
      setEditing(false);
    } catch {
      // Controlled values stay available for correction and retry.
    }
  };
  const cancel = () => { setValues(valuesFrom(state)); setEditing(false); };

  if (editing) return <section className="border border-line bg-white p-5"><h2 className="text-lg font-semibold">Моя оценка</h2><form onSubmit={save} className="mt-4 space-y-4"><div className="grid gap-3 md:grid-cols-2"><label className="grid gap-1 text-sm font-medium text-zinc-700">Мой приоритет<select value={values.user_priority} onChange={(event) => setValues((current) => ({ ...current, user_priority: event.target.value as VacancyUserPriority | "" }))} className="border border-line bg-white px-3 py-2 font-normal"><option value="">Не оценено</option><option value="P1">P1</option><option value="P2">P2</option><option value="P3">P3</option></select></label><label className="grid gap-1 text-sm font-medium text-zinc-700">Статус вакансии<select value={values.vacancy_status} onChange={(event) => setValues((current) => ({ ...current, vacancy_status: event.target.value as VacancyStatus }))} className="border border-line bg-white px-3 py-2 font-normal">{statuses.map((status) => <option key={status} value={status}>{vacancyStatusLabels[status]}</option>)}</select></label></div><label className="grid gap-1 text-sm font-medium text-zinc-700">Комментарий<textarea rows={5} value={values.comment} onChange={(event) => setValues((current) => ({ ...current, comment: event.target.value }))} className="border border-line bg-white px-3 py-2 font-normal" /></label>{update.isError && <p role="alert" className="text-sm text-rose-700">Не удалось сохранить оценку. Введённый текст сохранён в форме.</p>}<div className="flex flex-wrap gap-2"><button type="submit" disabled={update.isPending} className="bg-zinc-900 px-3 py-2 text-sm font-medium text-white disabled:bg-zinc-400">{update.isPending ? "Сохранение…" : "Сохранить"}</button><button type="button" onClick={cancel} disabled={update.isPending} className="inline-flex items-center gap-2 border border-line bg-white px-3 py-2 text-sm font-medium text-zinc-700"><X size={16} />Отмена</button></div></form></section>;
  return <section className="border border-line bg-white p-5"><div className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="text-lg font-semibold">Моя оценка</h2><p className="mt-1 text-sm text-zinc-500">Пользовательская оценка не меняет AI score.</p></div><button type="button" onClick={() => { setValues(valuesFrom(state)); setEditing(true); }} className="inline-flex items-center gap-2 border border-line bg-white px-3 py-1.5 text-sm font-medium text-zinc-700"><Pencil size={15} />Изменить</button></div><dl className="mt-4 grid gap-4 text-sm md:grid-cols-2"><div><dt className="text-zinc-500">Мой приоритет</dt><dd className="mt-1"><UserPriorityBadge priority={state.user_priority} /></dd></div><div><dt className="text-zinc-500">Статус вакансии</dt><dd className="mt-1"><VacancyStatusBadge status={state.vacancy_status} /></dd></div></dl><div className="mt-4 border-t border-line pt-4"><p className="text-sm font-medium">Комментарий</p><p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-zinc-700">{state.comment ?? "Нет комментария"}</p></div></section>;
}
