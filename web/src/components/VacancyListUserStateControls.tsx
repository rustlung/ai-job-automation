import { Check, MessageSquare, X } from "lucide-react";
import { useState } from "react";

import { useUpdateVacancyUserState } from "../hooks/useOrchestrator";
import { vacancyStatusLabels } from "../lib/vacancyStatus";
import type { VacancyStatus, VacancyUserPriority } from "../types/api";

const statuses: VacancyStatus[] = ["active", "archived", "closed"];
const priorities: Array<VacancyUserPriority | ""> = ["", "P1", "P2", "P3"];

function InlineSelect({
  label,
  value,
  options,
  onChange,
  pending
}: {
  label: string;
  value: string;
  options: Array<{ value: string; label: string }>;
  onChange: (value: string) => void;
  pending: boolean;
}) {
  return <select aria-label={label} value={value} disabled={pending} onChange={(event) => onChange(event.target.value)} className="border border-line bg-white px-2 py-1 text-xs font-medium disabled:cursor-wait disabled:bg-zinc-100">
    {options.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
  </select>;
}

export function VacancyListUserStateControls({
  presentationKey,
  vacancyStatus,
  userPriority,
  comment
}: {
  presentationKey: string;
  vacancyStatus: VacancyStatus;
  userPriority: VacancyUserPriority | null;
  comment: string | null;
}) {
  const update = useUpdateVacancyUserState();
  const [editingComment, setEditingComment] = useState(false);
  const [commentValue, setCommentValue] = useState(comment ?? "");
  const save = (payload: { vacancy_status?: VacancyStatus; user_priority?: VacancyUserPriority | null; comment?: string | null }) => {
    update.mutate({ presentationKey, payload });
  };
  const saveComment = () => {
    const nextComment = commentValue.trim() || null;
    if (nextComment === comment) {
      setEditingComment(false);
      return;
    }
    update.mutate({ presentationKey, payload: { comment: nextComment } }, { onSuccess: () => setEditingComment(false) });
  };
  const cancelComment = () => {
    setCommentValue(comment ?? "");
    setEditingComment(false);
  };

  return <>
    <td className="px-4 py-3"><InlineSelect label="Изменить статус вакансии" value={vacancyStatus} pending={update.isPending} onChange={(value) => save({ vacancy_status: value as VacancyStatus })} options={statuses.map((status) => ({ value: status, label: vacancyStatusLabels[status] }))} /></td>
    <td className="px-4 py-3"><InlineSelect label="Изменить мой приоритет" value={userPriority ?? ""} pending={update.isPending} onChange={(value) => save({ user_priority: (value || null) as VacancyUserPriority | null })} options={priorities.map((priority) => ({ value: priority, label: priority || "Не оценено" }))} /></td>
    <td className="min-w-56 max-w-80 px-4 py-3">{editingComment ? <div className="grid gap-2"><textarea aria-label="Мой комментарий" rows={3} value={commentValue} disabled={update.isPending} onChange={(event) => setCommentValue(event.target.value)} className="w-full border border-line bg-white px-2 py-1 text-xs leading-5" /><div className="flex gap-1"><button type="button" aria-label="Сохранить комментарий" disabled={update.isPending} onClick={saveComment} className="inline-flex size-7 items-center justify-center bg-zinc-900 text-white disabled:bg-zinc-400"><Check size={14} /></button><button type="button" aria-label="Отменить комментарий" disabled={update.isPending} onClick={cancelComment} className="inline-flex size-7 items-center justify-center border border-line bg-white"><X size={14} /></button></div></div> : <button type="button" aria-label="Изменить комментарий" disabled={update.isPending} onClick={() => setEditingComment(true)} className="flex max-w-full items-center gap-2 text-left text-xs text-zinc-700 hover:text-zinc-950 disabled:cursor-wait"><MessageSquare size={14} className="shrink-0" /><span className="truncate">{comment ?? "Добавить комментарий"}</span></button>}{update.isError && <p role="alert" className="mt-1 text-xs text-rose-700">Не сохранено</p>}</td>
  </>;
}
