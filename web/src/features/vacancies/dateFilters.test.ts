import { describe, expect, it } from "vitest";

import { activeDatePreset, dateRangeForPreset } from "./dateFilters";

describe("dateRangeForPreset", () => {
  const now = new Date(2026, 8, 8, 12);

  it("uses an inclusive rolling range", () => {
    expect(dateRangeForPreset("3d", now)).toEqual({ date_from: "2026-09-06", date_to: "2026-09-08" });
  });

  it("uses Europe/Samara rather than the browser timezone near UTC midnight", () => {
    const utcEvening = new Date("2026-10-30T21:30:00.000Z");

    expect(dateRangeForPreset("7d", utcEvening)).toEqual({ date_from: "2026-10-25", date_to: "2026-10-31" });
  });

  it("clears dates for all time", () => {
    expect(dateRangeForPreset("all", now)).toEqual({});
  });

  it("derives an active preset only for matching ranges", () => {
    expect(activeDatePreset(undefined, undefined, now)).toBe("all");
    expect(activeDatePreset("2026-09-06", "2026-09-08", now)).toBe("3d");
    expect(activeDatePreset("2026-09-01", "2026-09-08", now)).toBeUndefined();
  });
});
