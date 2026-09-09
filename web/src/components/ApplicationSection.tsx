import { Pencil, Plus, X } from "lucide-react";
import { useState } from "react";
import type { ReactNode } from "react";

import { ApplicationStatusBadge } from "./ApplicationStatusBadge";
import { useCreateApplication, useRetryApplicationCrmSync, useUpdateApplication } from "../hooks/useOrchestrator";
import { applicationStatusLabels } from "../lib/applicationStatus";
import { formatDateTime } from "../lib/format";
import type { Application, ApplicationCreateRequest, ApplicationPatchRequest, ApplicationStatus, VacancyApplicationDetail } from "../types/api";

type FormValues = {
  status: ApplicationStatus;
  applied_at: string;
  application_text: string;
  employer_response: string;
  response_received_at: string;
  interview_at: string;
  offer_at: string;
  notes: string;
  platform: string;
};

function toDateTimeInput(value: string | null): string {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const pad = (part: number) => String(part).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function currentDateTimeInput(): string {
  return toDateTimeInput(new Date().toISOString());
}

function formValues(application?: Application): FormValues {
  return {
    status: application?.status ?? "submitted",
    applied_at: application ? toDateTimeInput(application.applied_at) : currentDateTimeInput(),
    application_text: application?.application_text ?? "",
    employer_response: application?.employer_response ?? "",
    response_received_at: application ? toDateTimeInput(application.response_received_at) : "",
    interview_at: application ? toDateTimeInput(application.interview_at) : "",
    offer_at: application ? toDateTimeInput(application.offer_at) : "",
    notes: application?.notes ?? "",
    platform: application?.platform ?? "hh"
  };
}

function normalizedValue(value: string): string | null {
  return value.trim() || null;
}

function toPayload(values: FormValues): ApplicationCreateRequest {
  return {
    status: values.status,
    applied_at: values.applied_at ? new Date(values.applied_at).toISOString() : null,
    application_text: normalizedValue(values.application_text),
    employer_response: normalizedValue(values.employer_response),
    response_received_at: values.response_received_at ? new Date(values.response_received_at).toISOString() : null,
    interview_at: values.interview_at ? new Date(values.interview_at).toISOString() : null,
    offer_at: values.offer_at ? new Date(values.offer_at).toISOString() : null,
    notes: normalizedValue(values.notes),
    platform: normalizedValue(values.platform)
  };
}

function changedPayload(application: Application, values: FormValues): ApplicationPatchRequest {
  const next = toPayload(values);
  const previous: ApplicationCreateRequest = {
    status: application.status,
    applied_at: application.applied_at,
    application_text: application.application_text,
    employer_response: application.employer_response,
    response_received_at: application.response_received_at,
    interview_at: application.interview_at,
    offer_at: application.offer_at,
    notes: application.notes,
    platform: application.platform
  };
  return Object.fromEntries(Object.entries(next).filter(([key, value]) => previous[key as keyof ApplicationCreateRequest] !== value)) as ApplicationPatchRequest;
}

function FieldLabel({ children }: { children: ReactNode }) {
  return <label className="grid gap-1 text-sm font-medium text-zinc-700">{children}</label>;
}

function ApplicationForm({ vacancyId, application, onCancel, onSaved }: { vacancyId: number; application?: Application; onCancel: () => void; onSaved: () => void }) {
  const [values, setValues] = useState(() => formValues(application));
  const [message, setMessage] = useState<string | null>(null);
  const create = useCreateApplication();
  const update = useUpdateApplication();
  const pending = create.isPending || update.isPending;
  const error = create.error ?? update.error;

  const setValue = <K extends keyof FormValues>(key: K, value: FormValues[K]) => setValues((current) => ({ ...current, [key]: value }));
  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setMessage(null);
    try {
      if (application) {
        const payload = changedPayload(application, values);
        if (Object.keys(payload).length === 0) {
          onCancel();
          return;
        }
        await update.mutateAsync({ applicationId: application.id, payload });
      } else {
        await create.mutateAsync({ vacancyId, payload: toPayload(values) });
      }
      setMessage("Сохранено");
      onSaved();
    } catch {
      // The controlled form keeps its values so the user can correct and retry.
    }
  };

  return <form onSubmit={submit} className="space-y-4 border border-zinc-300 bg-zinc-50 p-4">
    <div className="grid gap-3 md:grid-cols-2"><FieldLabel>Статус<select value={values.status} onChange={(event) => setValue("status", event.target.value as ApplicationStatus)} className="border border-line bg-white px-3 py-2 font-normal">{Object.entries(applicationStatusLabels).map(([status, label]) => <option key={status} value={status}>{label}</option>)}</select></FieldLabel><FieldLabel>Дата отклика<input type="datetime-local" value={values.applied_at} onChange={(event) => setValue("applied_at", event.target.value)} className="border border-line bg-white px-3 py-2 font-normal" /></FieldLabel></div>
    <div className="grid gap-3 md:grid-cols-2"><FieldLabel>Платформа<input value={values.platform} onChange={(event) => setValue("platform", event.target.value)} className="border border-line bg-white px-3 py-2 font-normal" placeholder="hh" /></FieldLabel><FieldLabel>Дата ответа<input type="datetime-local" value={values.response_received_at} onChange={(event) => setValue("response_received_at", event.target.value)} className="border border-line bg-white px-3 py-2 font-normal" /></FieldLabel><FieldLabel>Дата интервью<input type="datetime-local" value={values.interview_at} onChange={(event) => setValue("interview_at", event.target.value)} className="border border-line bg-white px-3 py-2 font-normal" /></FieldLabel><FieldLabel>Дата оффера<input type="datetime-local" value={values.offer_at} onChange={(event) => setValue("offer_at", event.target.value)} className="border border-line bg-white px-3 py-2 font-normal" /></FieldLabel></div>
    <FieldLabel>Текст отклика<textarea value={values.application_text} onChange={(event) => setValue("application_text", event.target.value)} rows={4} className="border border-line bg-white px-3 py-2 font-normal" /></FieldLabel>
    <FieldLabel>Ответ работодателя<textarea value={values.employer_response} onChange={(event) => setValue("employer_response", event.target.value)} rows={4} className="border border-line bg-white px-3 py-2 font-normal" /></FieldLabel>
    <FieldLabel>Заметки<textarea value={values.notes} onChange={(event) => setValue("notes", event.target.value)} rows={3} className="border border-line bg-white px-3 py-2 font-normal" /></FieldLabel>
    {error && <p role="alert" className="text-sm text-rose-700">Не удалось сохранить отклик. Введённые данные сохранены в форме.</p>}{message && <p role="status" className="text-sm text-emerald-700">{message}</p>}
    <div className="flex flex-wrap gap-2"><button type="submit" disabled={pending} className="bg-zinc-900 px-3 py-2 text-sm font-medium text-white disabled:bg-zinc-400">{pending ? "Сохранение…" : "Сохранить"}</button><button type="button" onClick={onCancel} disabled={pending} className="inline-flex items-center gap-2 border border-line bg-white px-3 py-2 text-sm font-medium text-zinc-700"><X size={16} />Отмена</button></div>
  </form>;
}

function ApplicationCard({ item }: { item: VacancyApplicationDetail }) {
  const [editing, setEditing] = useState(false);
  const retry = useRetryApplicationCrmSync();
  const application = item.application;
  const sync = item.crm_sync ?? { status: "pending" as const, error_message_safe: null };
  if (editing) return <ApplicationForm key={application.id} vacancyId={application.vacancy_id} application={application} onCancel={() => setEditing(false)} onSaved={() => setEditing(false)} />;
  return <article className="border border-line bg-white p-4"><div className="flex flex-wrap items-start justify-between gap-3"><div className="flex flex-wrap items-center gap-2"><ApplicationStatusBadge status={application.status} />{item.current && <span className="text-xs font-medium text-zinc-500">Текущий отклик</span>}</div><button type="button" onClick={() => setEditing(true)} className="inline-flex items-center gap-2 border border-line bg-white px-3 py-1.5 text-sm font-medium text-zinc-700"><Pencil size={15} />Изменить</button></div>{item.current && <div className="mt-3 flex flex-wrap items-center gap-2 text-xs"><span className={sync.status === "synced" ? "text-emerald-700" : sync.status === "failed" ? "text-rose-700" : "text-zinc-500"}>{sync.status === "synced" ? "Синхронизировано с CRM" : sync.status === "failed" ? "Ошибка синхронизации CRM" : "Ожидает синхронизации CRM"}</span>{sync.status === "failed" && <button type="button" disabled={retry.isPending} onClick={() => retry.mutate(application.id)} className="border border-line bg-white px-2 py-1 text-xs font-medium">Повторить синхронизацию</button>}</div>}<p className="mt-3 text-xs text-zinc-500">{item.source}:{item.external_id}{item.representative_member ? " · вакансия-представитель" : ""}</p><dl className="mt-3 grid gap-3 text-sm md:grid-cols-2"><div><dt className="text-zinc-500">Дата отклика</dt><dd>{formatDateTime(application.applied_at)}</dd></div><div><dt className="text-zinc-500">Платформа</dt><dd>{application.platform ?? "—"}</dd></div>{application.response_received_at && <div><dt className="text-zinc-500">Ответ получен</dt><dd>{formatDateTime(application.response_received_at)}</dd></div>}{application.interview_at && <div><dt className="text-zinc-500">Интервью</dt><dd>{formatDateTime(application.interview_at)}</dd></div>}{application.offer_at && <div><dt className="text-zinc-500">Оффер</dt><dd>{formatDateTime(application.offer_at)}</dd></div>}</dl>{application.application_text && <div className="mt-4"><p className="text-sm font-medium">Текст отклика</p><p className="mt-1 whitespace-pre-wrap text-sm leading-6 text-zinc-700">{application.application_text}</p></div>}{application.employer_response && <div className="mt-4"><p className="text-sm font-medium">Ответ работодателя</p><p className="mt-1 whitespace-pre-wrap text-sm leading-6 text-zinc-700">{application.employer_response}</p></div>}{application.notes && <div className="mt-4"><p className="text-sm font-medium">Заметки</p><p className="mt-1 whitespace-pre-wrap text-sm leading-6 text-zinc-700">{application.notes}</p></div>}</article>;
}

export function ApplicationSection({ applications, vacancyId }: { applications: VacancyApplicationDetail[]; vacancyId: number }) {
  const [creating, setCreating] = useState(false);
  const applicationItems = applications ?? [];
  return <section className="space-y-4"><div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="text-lg font-semibold">Отклики</h2><p className="mt-1 text-sm text-zinc-500">Отклики хранятся для конкретной source vacancy.</p></div><button type="button" onClick={() => setCreating(true)} className="inline-flex items-center gap-2 bg-zinc-900 px-3 py-2 text-sm font-medium text-white"><Plus size={16} />{applicationItems.length ? "Добавить ещё" : "Добавить отклик"}</button></div>{applicationItems.length === 0 && !creating && <div className="border border-dashed border-zinc-300 bg-zinc-50 p-4 text-sm text-zinc-600">Отклик не отправлен</div>}{creating && <ApplicationForm vacancyId={vacancyId} onCancel={() => setCreating(false)} onSaved={() => setCreating(false)} />}{applicationItems.map((item) => <ApplicationCard key={item.application.id} item={item} />)}</section>;
}
