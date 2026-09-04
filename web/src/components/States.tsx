import { CircleAlert, Inbox, LoaderCircle } from "lucide-react";

export function LoadingState({ label = "Загрузка…" }: { label?: string }) { return <div role="status" className="flex min-h-32 items-center justify-center gap-2 text-sm text-zinc-500"><LoaderCircle className="animate-spin" size={18} />{label}</div>; }
export function ErrorState({ message = "Не удалось загрузить данные." }: { message?: string }) { return <div role="alert" className="flex min-h-32 items-center justify-center gap-2 border border-red-200 bg-red-50 p-5 text-sm text-danger"><CircleAlert size={18} />{message}</div>; }
export function EmptyState({ title, detail }: { title: string; detail: string }) { return <div className="flex min-h-44 flex-col items-center justify-center border border-dashed border-zinc-300 bg-white p-6 text-center"><Inbox className="text-zinc-400" size={28} /><h2 className="mt-3 font-semibold">{title}</h2><p className="mt-1 max-w-md text-sm text-zinc-500">{detail}</p></div>; }
