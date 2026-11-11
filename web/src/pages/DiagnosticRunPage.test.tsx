import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DiagnosticRunPage } from "./DiagnosticRunPage";

const useDiagnosticRun = vi.fn();
vi.mock("../hooks/useOrchestrator", () => ({ useDiagnosticRun: (...args: unknown[]) => useDiagnosticRun(...args) }));
afterEach(() => cleanup());

function report(overrides: Record<string, unknown> = {}) {
  const run = { run_id: "run-001", trigger_source: "web_ui", status: "completed", profile_ids: ["python"], config_snapshot: {}, stats_snapshot: { collection_stats: { unique_vacancy_count: 300 } }, error_code: null, error_summary: null, started_at: "2026-11-01T00:00:00Z", completed_at: "2026-11-01T00:01:00Z", created_at: "", updated_at: "" };
  return { run: { ...run, ...(overrides.run as object ?? {}) }, preliminary: { availability: "available", processed_count: 300, outcome_counts: {}, enrichment_selected_count: 247 }, enrichment: { availability: "available", analysis_count: 3, enriched_count: 3, processing_failed_count: 244 }, backlog: { availability: "available", total: 300, state_counts: {} }, failures: overrides.failures ?? {}, full_fetch_transport: { value: "httpx", source: "runtime_code/config" }, pagination: { availability: "unavailable" } };
}

function renderPage(data: ReturnType<typeof report>) {
  useDiagnosticRun.mockReturnValue({ isLoading: false, isError: false, data });
  return render(<MemoryRouter initialEntries={["/diagnostics/runs/run-001"]}><Routes><Route path="/diagnostics/runs/:runId" element={<DiagnosticRunPage />} /></Routes></MemoryRouter>);
}

describe("DiagnosticRunPage overview", () => {
  it("separates completed run without error from item failures", () => {
    renderPage(report({ failures: { full_fetch_failed: { count: 244, summary: "Safe", samples: [] } } }));
    expect(screen.getByText("Run error")).toBeInTheDocument();
    expect(screen.getByText("Нет")).toBeInTheDocument();
    expect(screen.getByText("244 full_fetch_failed")).toBeInTheDocument();
    expect(screen.getAllByText("Завершён")).not.toHaveLength(0);
  });

  it("shows concrete terminal error for failed run", () => {
    renderPage(report({ run: { status: "failed", error_code: "worker_recovery_timeout", error_summary: "Recovery window expired." } }));
    expect(screen.getByText("worker_recovery_timeout: Recovery window expired.")).toBeInTheDocument();
    expect(screen.getAllByText("Ошибка")).not.toHaveLength(0);
  });

  it("keeps unavailable distinct from a null run error and aggregates multiple groups", () => {
    renderPage(report({ run: { error_code: undefined, error_summary: undefined }, failures: { full_fetch_failed: { count: 244, summary: null, samples: [] }, normalization_failed: { count: 3, summary: null, samples: [] } } }));
    expect(screen.getAllByText("unavailable")).not.toHaveLength(0);
    expect(screen.getByText("247 issues: full_fetch_failed: 244, normalization_failed: 3")).toBeInTheDocument();
  });

  it("shows no processing issues when groups are empty", () => {
    renderPage(report());
    expect(screen.getAllByText("Нет")).not.toHaveLength(0);
  });
});
