import type { VacancyUserPriority } from "../types/api";

export function UserPriorityBadge({ priority }: { priority: VacancyUserPriority | null }) {
  return <span className={priority ? "inline-flex bg-violet-50 px-2 py-1 text-xs font-semibold text-violet-800" : "inline-flex border border-zinc-300 bg-white px-2 py-1 text-xs font-medium text-zinc-600"}>{priority ? `Мой: ${priority}` : "Не оценено"}</span>;
}
