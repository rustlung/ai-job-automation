import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, request } from "./client";

afterEach(() => vi.unstubAllGlobals());

describe("request", () => {
  it("returns typed JSON for successful responses", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ ok: true }), { status: 200 })));
    await expect(request<{ ok: boolean }>("/api/test")).resolves.toEqual({ ok: true });
  });

  it("turns structured backend errors into a safe ApiError", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: { error_code: "worker_unavailable" } }), { status: 503 })));
    await expect(request("/api/test")).rejects.toMatchObject({ status: 503, errorCode: "worker_unavailable" } satisfies Partial<ApiError>);
  });
});
