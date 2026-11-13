import { X } from "lucide-react";
import type { ReactNode } from "react";

type ConfirmationDialogProps = {
  open: boolean;
  title: string;
  children: ReactNode;
  confirmLabel?: string;
  pending?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
};

export function ConfirmationDialog({ open, title, children, confirmLabel = "Удалить", pending = false, onConfirm, onCancel }: ConfirmationDialogProps) {
  if (!open) return null;
  return <div className="fixed inset-0 z-50 grid place-items-center bg-zinc-950/40 p-4" role="presentation">
    <section role="dialog" aria-modal="true" aria-labelledby="confirmation-dialog-title" className="w-full max-w-md border border-line bg-white p-5 shadow-xl">
      <div className="flex items-start justify-between gap-3"><h2 id="confirmation-dialog-title" className="text-lg font-semibold">{title}</h2><button type="button" aria-label="Закрыть" onClick={onCancel} disabled={pending} className="inline-flex size-8 items-center justify-center text-zinc-500 hover:text-zinc-950 disabled:opacity-50"><X size={18} /></button></div>
      <div className="mt-3 text-sm leading-6 text-zinc-600">{children}</div>
      <div className="mt-5 flex flex-wrap justify-end gap-2"><button type="button" onClick={onCancel} disabled={pending} className="border border-line bg-white px-3 py-2 text-sm font-medium text-zinc-700 disabled:opacity-50">Отмена</button><button type="button" onClick={onConfirm} disabled={pending} className="bg-danger px-3 py-2 text-sm font-medium text-white disabled:opacity-50">{pending ? "Удаление…" : confirmLabel}</button></div>
    </section>
  </div>;
}
