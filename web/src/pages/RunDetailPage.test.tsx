import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { RunDetailPage } from "./RunDetailPage";

const useRun = vi.fn();
const useCancelRun = vi.fn();

vi.mock("../hooks/useOrchestrator", () => ({ useRun: (...args: unknown[]) => useRun(...args), useCancelRun: () => useCancelRun() }));

afterEach(() => { cleanup(); useCancelRun.mockReturnValue({ mutateAsync: vi.fn(), isPending: false }); });
beforeEach(() => useCancelRun.mockReturnValue({ mutateAsync: vi.fn(), isPending: false }));

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
    error_code: status === "failed" ? "hh_auth_failed" : status === "completed_with_errors" ? "telegram_notification_failed" : null,
    error_summary: status === "failed" ? "HH session не подтверждена" : status === "completed_with_errors" ? "Не удалось отправить Telegram-уведомление." : null,
    started_at: "2026-10-30T08:00:00Z",
    completed_at: "2026-10-30T08:01:00Z",
    created_at: "2026-10-30T08:00:00Z",
    updated_at: "2026-10-30T08:01:00Z"
  };
}

describe("RunDetailPage diagnostics", () => {
  it("shows processing diagnostics and warnings for a completed run without an error block", () => {
    useRun.mockReturnValue({ isLoading: false, isError: false, data: run("completed", { warnings: [{ code: "semantic_fallback", count: 2, summary: "Semantic fallback" }], partial_failures: [{ code: "full_fetch_failed", count: 1, summary: "Не удалось загрузить карточку" }] }) });

    renderPage();

    expect(screen.getAllByText("Завершён")).not.toHaveLength(0);
    expect(screen.getByText("Предупреждения")).toBeInTheDocument();
    expect(screen.getByText("Semantic fallback")).toBeInTheDocument();
    expect(screen.getByText("Диагностика обработки")).toBeInTheDocument();
    expect(screen.getByText("Не удалось загрузить карточку")).toBeInTheDocument();
    expect(screen.queryByText("Ошибка")).not.toBeInTheDocument();
    expect(screen.queryByText("Ошибки интеграций")).not.toBeInTheDocument();
  });

  it("shows concrete integration errors for completed_with_errors", () => {
    useRun.mockReturnValue({ isLoading: false, isError: false, data: run("completed_with_errors", { integration_errors: [{ code: "telegram_notification_failed", count: 1, summary: "Не удалось отправить Telegram-уведомление." }] }) });

    renderPage();

    expect(screen.getByText("Завершён с ошибками")).toBeInTheDocument();
    expect(screen.getByText("Ошибки интеграций")).toBeInTheDocument();
    expect(screen.getByText("Не удалось отправить Telegram-уведомление.")).toBeInTheDocument();
  });

  it("shows a fatal error only for failed runs", () => {
    useRun.mockReturnValue({ isLoading: false, isError: false, data: run("failed") });

    renderPage();

    expect(screen.getAllByText("Ошибка")).not.toHaveLength(0);
    expect(screen.getByText("HH session не подтверждена")).toBeInTheDocument();
  });

  it("wraps long statistics and configuration values without shrinking sibling grid cells", () => {
    const longValue = JSON.stringify({ collection_stats: { nested: "x".repeat(600) }, duration_ms: 123456789 });
    useRun.mockReturnValue({
      isLoading: false,
      isError: false,
      data: { ...run("completed", { persistence_stats: longValue, duration_ms: longValue }), config_snapshot: { long_diagnostic_value: longValue } }
    });

    renderPage();

    expect(screen.getAllByTestId("run-stat-value").every((element) => element.classList.contains("min-w-0"))).toBe(true);
    expect(screen.getAllByText(longValue).every((element) => element.className.includes("break-words") && element.className.includes("[overflow-wrap:anywhere]"))).toBe(true);
  });

  it("shows persisted stage progress for a running run", () => {
    useRun.mockReturnValue({ isLoading: false, isError: false, data: { ...run("completed", { progress: { stage: "preliminary", current: 12, total: 20, percent: 60, message: "Предварительная фильтрация" } }), status: "running", completed_at: null } });

    renderPage();

    expect(screen.getByTestId("run-progress")).toHaveTextContent("Предварительная фильтрация: 12 из 20");
    expect(screen.getByText("60%")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Отменить запуск" })).toBeInTheDocument();
  });
});
