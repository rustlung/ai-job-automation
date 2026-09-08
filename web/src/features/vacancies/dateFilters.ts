export type DatePreset = "today" | "3d" | "7d" | "14d" | "30d" | "all";

function localDateValue(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function dateRangeForPreset(preset: DatePreset, now = new Date()): { date_from?: string; date_to?: string } {
  if (preset === "all") return {};
  const days = preset === "today" ? 1 : Number.parseInt(preset, 10);
  const dateTo = localDateValue(now);
  const dateFrom = new Date(now);
  dateFrom.setDate(dateFrom.getDate() - days + 1);
  return { date_from: localDateValue(dateFrom), date_to: dateTo };
}

export function activeDatePreset(
  dateFrom: string | undefined,
  dateTo: string | undefined,
  now = new Date()
): DatePreset | undefined {
  if (!dateFrom && !dateTo) return "all";
  return (["today", "3d", "7d", "14d", "30d"] as DatePreset[]).find((preset) => {
    const range = dateRangeForPreset(preset, now);
    return range.date_from === dateFrom && range.date_to === dateTo;
  });
}
