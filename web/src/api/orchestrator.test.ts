import { afterEach, describe, expect, it, vi } from "vitest";

import { orchestratorApi } from "./orchestrator";

afterEach(() => vi.unstubAllGlobals());

describe("orchestratorApi.getVacancies", () => {
  it("sends the processing filter to the backend", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ items: [], total: 0, limit: 25, offset: 0 }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await orchestratorApi.getVacancies({ priority: [], processing: "rejected", limit: 25, offset: 0, sort: "first_seen", sort_direction: "desc" });

    expect(String(fetchMock.mock.calls[0][0])).toContain("processing=rejected");
  });

  it("serializes the current vacancy filters in the export payload", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response("file", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await orchestratorApi.downloadVacancyExport({
      format: "xlsx",
      period: "all",
      columns: [],
      vacancy_filters: { processing: "errors", priority: ["P1"], search: "Python", sort: "first_seen", sort_direction: "desc" }
    });

    expect(String(fetchMock.mock.calls[0][0])).toContain("/api/exports/vacancies");
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toMatchObject({
      vacancy_filters: { processing: "errors", priority: ["P1"], search: "Python" }
    });
  });
});
