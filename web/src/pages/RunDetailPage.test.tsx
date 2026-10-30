import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { RunDetailPage } from "./RunDetailPage";

const useRun = vi.fn();

vi.mock("../hooks/useOrchestrator", () => ({ useRun: (...args: unknown[]) => useRun(...args) }));

afterEach(() => cleanup());

function renderPage() {
  return render(<MemoryRouter initialEntries={["/runs/run-001"]}><Routes><Route path="/runs/:runId" element={<RunDetailPage />} /></Routes></MemoryRouter>);
}

function run(status: "completed" | "completed_with_errors" | "failed", statsSnapshot: Record<string, unknown> = {}) {
  return {
    run_id: "run-001",
    trigger_source: "web_ui" as const,
    status,
    profile_ids: ["profile"],
    config_snapshot: {},
    stats_snapshot: statsSnapshot,
    error_code: status === "failed" ? "hh_auth_failed" : status === "completed_with_errors" ? "partial_failures" : null,
    error_summary: status === "failed" ? "HH session не подтверждена" : status === "completed_with_errors" ? "Partial failures" : null,
    started_at: "2026-10-30T08:00:00Z",
    completed_at: "2026-10-30T08:01:00Z",
    created_at: "2026-10-30T08:00:00Z",
    updated_at: "2026-10-30T08:01:00Z"
  };
}

describe("RunDetailPage diagnostics", () => {
  it("shows warnings for a completed run without an empty fatal error block", () => {
    useRun.mockReturnValue({ isLoading: false, isError: false, data: run("completed", { warnings: [{ code: "semantic_fallback", count: 2, summary: "Semantic fallback" }] }) });

    renderPage();

    expect(screen.getAllByText("Завершён")).not.toHaveLength(0);
    expect(screen.getByText("Предупреждения")).toBeInTheDocument();
    expect(screen.getByText("Semantic fallback")).toBeInTheDocument();
    expect(screen.queryByText("Ошибка")).not.toBeInTheDocument();
  });

  it("shows structured partial failures for completed_with_errors", () => {
    useRun.mockReturnValue({ isLoading: false, isError: false, data: run("completed_with_errors", { partial_failures: [{ code: "full_fetch_failed", count: 3, summary: "Не удалось загрузить карточку" }] }) });

    renderPage();

    expect(screen.getByText("Завершён с ошибками")).toBeInTheDocument();
    expect(screen.getByText("Частичные ошибки")).toBeInTheDocument();
    expect(screen.getByText("Не удалось загрузить карточку")).toBeInTheDocument();
  });

  it("shows a fatal error only for failed runs", () => {
    useRun.mockReturnValue({ isLoading: false, isError: false, data: run("failed") });

    renderPage();

    expect(screen.getAllByText("Ошибка")).not.toHaveLength(0);
    expect(screen.getByText("HH session не подтверждена")).toBeInTheDocument();
  });
});
