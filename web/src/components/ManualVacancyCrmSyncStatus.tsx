import { CheckCircle2, Clock3, RefreshCw, TriangleAlert } from "lucide-react";

import { useRetryManualVacancyCrmSync } from "../hooks/useOrchestrator";
import type { ManualVacancyCrmSync } from "../types/api";

export function ManualVacancyCrmSyncStatus({ sync }: { sync: ManualVacancyCrmSync }) {
  const retry = useRetryManualVacancyCrmSync();

  if (sync.status === "synced") {
    return <div className="flex items-center gap-2 text-sm text-emerald-700"><CheckCircle2 size={16} />Строка CRM создана</div>;
  }
  if (sync.status === "pending") {
    return <div className="flex items-center gap-2 text-sm text-zinc-600"><Clock3 size={16} />Создание строки CRM ожидает выполнения</div>;
  }
  return (
    <div className="flex flex-wrap items-center gap-3 text-sm text-red-700">
      <span className="flex items-center gap-2"><TriangleAlert size={16} />Вакансия сохранена, строка CRM не создана</span>
      <button
        type="button"
        className="inline-flex items-center gap-2 border border-red-200 bg-white px-3 py-1.5 font-medium text-red-700 disabled:opacity-60"
        disabled={retry.isPending}
        onClick={() => retry.mutate(sync.presentation_key)}
      >
        <RefreshCw size={15} />{retry.isPending ? "Повтор…" : "Повторить синхронизацию"}
      </button>
    </div>
  );
}
