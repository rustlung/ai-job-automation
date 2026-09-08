import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { VacanciesPage } from "./VacanciesPage";

const vacancy = {
  presentation_key: "business:abc123",
  vacancy_id: 1,
  source: "hh",
  external_id: "101",
  company: "Example Company",
  title: "Python Developer",
  salary_text: "200 000 ₽",
  location: "Самара",
  published_at: null,
  first_seen_at: "2026-09-08T10:00:00Z",
  url: "https://samara.hh.ru/vacancy/101",
  priority: "P1" as const,
  final_score: 95,
  track: "main",
  summary: "summary",
  profile_ids: ["ai_automation_keywords"],
  run_id: "run-1",
  member_count: 2
};

const useVacancies = vi.fn();
vi.mock("../hooks/useOrchestrator", () => ({
  useVacancies: (...args: unknown[]) => useVacancies(...args),
  useSearchProfiles: () => ({ data: { profiles: [{ id: "ai_automation_keywords", name: "AI Automation", enabled: true, user_selectable: true }] } })
}));

function LocationProbe() {
  return <output data-testid="location">{useLocation().search}</output>;
}

function renderPage(initialEntry = "/vacancies") {
  return render(<MemoryRouter initialEntries={[initialEntry]}><LocationProbe /><Routes><Route path="/vacancies" element={<VacanciesPage />} /><Route path="/vacancies/:presentationKey" element={<p>Detail route</p>} /></Routes></MemoryRouter>);
}

describe("VacanciesPage", () => {
  afterEach(() => cleanup());

  it("renders grouped rows with profile display names and preserves URL filters", () => {
    useVacancies.mockReturnValue({ data: { items: [vacancy], total: 1, limit: 25, offset: 0 }, isLoading: false, isError: false });
    renderPage("/vacancies?priority=P1");

    expect(screen.getByText("Example Company")).toBeInTheDocument();
    expect(screen.getAllByText("AI Automation")).toHaveLength(2);
    expect(screen.getByRole("checkbox", { name: "P1" })).toBeChecked();
    fireEvent.click(screen.getByRole("button", { name: "7 дней" }));
    expect(screen.getByTestId("location")).toHaveTextContent("date_from=");
    fireEvent.click(screen.getByText("Python Developer"));
    expect(screen.getByText("Detail route")).toBeInTheDocument();
  });

  it("renders an empty state and resets filters", () => {
    useVacancies.mockReturnValue({ data: { items: [], total: 0, limit: 25, offset: 0 }, isLoading: false, isError: false });
    renderPage("/vacancies?search=none");

    expect(screen.getByText("Вакансий не найдено")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Сбросить фильтры" }));
    expect(screen.getByTestId("location")).toHaveTextContent("");
  });

  it("renders loading and error states without hiding pagination behavior", () => {
    useVacancies.mockReturnValue({ data: undefined, isLoading: true, isError: false });
    const { unmount } = renderPage();
    expect(screen.getByText("Загрузка…")).toBeInTheDocument();
    unmount();

    useVacancies.mockReturnValue({ data: { items: [vacancy], total: 50, limit: 25, offset: 0 }, isLoading: false, isError: false });
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: "Следующая страница" }));
    expect(screen.getByTestId("location")).toHaveTextContent("offset=25");
    cleanup();

    useVacancies.mockReturnValue({ data: undefined, isLoading: false, isError: true });
    renderPage();
    expect(screen.getByText("Не удалось загрузить список вакансий.")).toBeInTheDocument();
  });
});
