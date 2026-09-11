import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { StatisticsPage } from "./StatisticsPage";

const useStatistics = vi.fn();
vi.mock("../hooks/useOrchestrator", () => ({
  useStatistics: (...args: unknown[]) => useStatistics(...args)
}));

const statistics = {
  period: "30d" as const,
  date_from: "2026-08-14",
  date_to: "2026-09-12",
  found: 12,
  reviewed: 7,
  applications: 5,
  responses: 3,
  interviews: 2,
  rejections: 1,
  active_processes: 3,
  offers: 1,
  legacy_without_date: 2
};

function LocationProbe() {
  return <output data-testid="location">{useLocation().search}</output>;
}

function renderPage(entry = "/statistics") {
  return render(<MemoryRouter initialEntries={[entry]}><LocationProbe /><StatisticsPage /></MemoryRouter>);
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("StatisticsPage", () => {
  it("показывает все summary-метрики", () => {
    useStatistics.mockReturnValue({ data: statistics, isLoading: false, isError: false });
    renderPage();

    expect(screen.getByRole("heading", { name: "Статистика вакансий" })).toBeInTheDocument();
    expect(screen.getByText("Найдено")).toBeInTheDocument();
    expect(screen.getByText("Активные процессы")).toBeInTheDocument();
    expect(screen.getAllByText("1")).toHaveLength(2);
    expect(screen.getByText("Вакансий без надёжной даты cohort: 2. Они учитываются только за всё время.")).toBeInTheDocument();
  });

  it("синхронизирует выбранный период с URL", () => {
    useStatistics.mockReturnValue({ data: statistics, isLoading: false, isError: false });
    renderPage("/statistics?period=30d");

    fireEvent.change(screen.getByLabelText("Период"), { target: { value: "7d" } });

    expect(screen.getByTestId("location")).toHaveTextContent("?period=7d");
  });

  it("показывает custom range и валидирует порядок дат", () => {
    useStatistics.mockReturnValue({ data: undefined, isLoading: false, isError: false });
    renderPage("/statistics?period=custom");

    expect(screen.getByLabelText("Дата начала")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Дата начала"), { target: { value: "2026-09-12" } });
    fireEvent.change(screen.getByLabelText("Дата окончания"), { target: { value: "2026-09-11" } });

    expect(screen.getByRole("alert")).toHaveTextContent("Дата начала не может быть позже даты окончания.");
    expect(screen.getByTestId("location")).toHaveTextContent("period=custom");
    expect(screen.getByTestId("location")).toHaveTextContent("date_from=2026-09-12");
    expect(screen.getByTestId("location")).toHaveTextContent("date_to=2026-09-11");
  });

  it("показывает loading, error и zero state", () => {
    useStatistics.mockReturnValue({ data: undefined, isLoading: true, isError: false });
    const { rerender } = renderPage();
    expect(screen.getByText("Загрузка статистики…")).toBeInTheDocument();

    useStatistics.mockReturnValue({ data: undefined, isLoading: false, isError: true });
    rerender(<MemoryRouter><LocationProbe /><StatisticsPage /></MemoryRouter>);
    expect(screen.getByRole("alert")).toHaveTextContent("Не удалось загрузить статистику.");

    useStatistics.mockReturnValue({ data: { ...statistics, found: 0, legacy_without_date: 0 }, isLoading: false, isError: false });
    rerender(<MemoryRouter><LocationProbe /><StatisticsPage /></MemoryRouter>);
    expect(screen.getByText("За выбранный период вакансий нет")).toBeInTheDocument();
  });
});
