import { describe, expect, it } from "vitest";

import { formatDateTime, formatTriggerSource, isTerminalRunStatus, runPollingInterval } from "./format";

describe("run status helpers", () => {
  it("distinguishes terminal states and stops polling", () => {
    expect(isTerminalRunStatus("running")).toBe(false);
    expect(runPollingInterval("accepted")).toBe(4000);
    expect(runPollingInterval("completed")).toBe(false);
    expect(runPollingInterval("failed")).toBe(false);
  });

  it("formats trigger source and valid dates", () => {
    expect(formatTriggerSource("manual_n8n")).toBe("Manual n8n");
    expect(formatDateTime("2026-09-04T12:30:00Z")).not.toBe("—");
    expect(formatDateTime(null)).toBe("—");
  });
});
