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
});
