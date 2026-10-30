export type DatePreset = "today" | "3d" | "7d" | "14d" | "30d" | "all";

const samaraDateFormatter = new Intl.DateTimeFormat("en-CA", {
  timeZone: "Europe/Samara",
  year: "numeric",
  month: "2-digit",
  day: "2-digit"
});

function samaraCalendarDate(date: Date): { year: number; month: number; day: number } {
  const parts = samaraDateFormatter.formatToParts(date);
  const value = (type: Intl.DateTimeFormatPartTypes) => Number(parts.find((part) => part.type === type)?.value);
  return { year: value("year"), month: value("month"), day: value("day") };
}

function calendarDateValue(date: Date): string {
  const year = date.getUTCFullYear();
  const month = String(date.getUTCMonth() + 1).padStart(2, "0");
  const day = String(date.getUTCDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function dateRangeForPreset(preset: DatePreset, now = new Date()): { date_from?: string; date_to?: string } {
  if (preset === "all") return {};
  const days = preset === "today" ? 1 : Number.parseInt(preset, 10);
  const samara = samaraCalendarDate(now);
  const dateTo = new Date(Date.UTC(samara.year, samara.month - 1, samara.day));
  const dateFrom = new Date(dateTo);
  dateFrom.setUTCDate(dateFrom.getUTCDate() - days + 1);
  return { date_from: calendarDateValue(dateFrom), date_to: calendarDateValue(dateTo) };
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
