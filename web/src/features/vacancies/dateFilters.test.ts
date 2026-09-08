import { describe, expect, it } from "vitest";

import { activeDatePreset, dateRangeForPreset } from "./dateFilters";

describe("dateRangeForPreset", () => {
  const now = new Date(2026, 8, 8, 12);

  it("uses an inclusive rolling range", () => {
    expect(dateRangeForPreset("3d", now)).toEqual({ date_from: "2026-09-06", date_to: "2026-09-08" });
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
