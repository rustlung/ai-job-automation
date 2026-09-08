import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../api/client";
import { VacancyDetailPage } from "./VacancyDetailPage";

const vacancy = {
  presentation_key: "business:abc123",
  vacancy_id: 1,
  source: "hh",
  external_id: "102",
  member_count: 2,
  company: "Example Company",
  title: "Python Developer",
  salary_text: "200 000 ₽",
  location: "Самара",
  work_format: "Удалённо",
  working_hours: "8 часов",
  experience_min_years: 1,
  experience_max_years: 3,
  published_at: "2026-09-01T10:00:00Z",
  first_seen_at: "2026-09-02T10:00:00Z",
  last_seen_at: "2026-09-03T10:00:00Z",
  url: "https://samara.hh.ru/vacancy/102",
  description: "Первый абзац вакансии.\n\nВторой абзац вакансии.",
  skills: ["Python", "FastAPI"],
  analysis: { priority: "P1" as const, final_score: 95, relevance: 9, track: "python", summary: "Релевантная backend роль", reason: "Есть Python и API интеграции.", risks: ["experience_stretch"], hard_blockers: [] },
  profile_ids: ["ai_automation_keywords"],
  query_variant_ids: ["ai-ru"],
  provenance_tracks: ["main"],
  run_ids: ["run-1"],
  members: [
    { source: "hh", external_id: "102", url: "https://samara.hh.ru/vacancy/102", title: "Python Developer", company: "Example Company", location: "Самара", representative: true },
    { source: "hh", external_id: "101", url: "https://kazan.hh.ru/vacancy/101", title: "Python Developer", company: "Example Company", location: "Казань", representative: false }
  ]
};

const useVacancyDetail = vi.fn();
const useSearchProfiles = vi.fn();
vi.mock("../hooks/useOrchestrator", () => ({
  useVacancyDetail: (...args: unknown[]) => useVacancyDetail(...args),
  useSearchProfiles: () => useSearchProfiles()
}));

function renderPage(entry: string | { pathname: string; state?: unknown } = "/vacancies/business%3Aabc123") {
  return render(<MemoryRouter initialEntries={[entry]}><Routes><Route path="/vacancies/:presentationKey" element={<VacancyDetailPage />} /><Route path="/vacancies" element={<p>Vacancies list</p>} /></Routes></MemoryRouter>);
}

describe("VacancyDetailPage", () => {
  beforeEach(() => {
    useVacancyDetail.mockReturnValue({ data: vacancy, isLoading: false, isError: false });
    useSearchProfiles.mockReturnValue({ data: { profiles: [{ id: "ai_automation_keywords", name: "AI Automation" }] }, isError: false });
  });
  afterEach(() => cleanup());

  it("renders a direct detail route with analysis, description and members", () => {
    renderPage();

    expect(useVacancyDetail).toHaveBeenLastCalledWith("business:abc123");
    expect(screen.getByRole("heading", { name: "Python Developer" })).toBeInTheDocument();
    expect(screen.getByText("200 000 ₽")).toBeInTheDocument();
    expect(screen.getByText("Первый абзац вакансии.")).toBeInTheDocument();
    expect(screen.getByText("Есть Python и API интеграции.")).toBeInTheDocument();
    expect(screen.getByText("AI Automation")).toBeInTheDocument();
    expect(screen.getByText("Региональные копии: 2")).toBeInTheDocument();
    expect(screen.getByText("Представитель")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Открыть оригинал" })).toHaveAttribute("href", vacancy.url);
  });

  it("falls back to raw profile ids when metadata is unavailable", () => {
    useSearchProfiles.mockReturnValue({ data: undefined, isError: true });
    renderPage();

    expect(screen.getByText("ai_automation_keywords")).toBeInTheDocument();
  });

  it("does not execute description HTML", () => {
    useVacancyDetail.mockReturnValue({ data: { ...vacancy, description: "<img src=x onerror=alert(1)>Безопасный текст" }, isLoading: false, isError: false });
    renderPage();

    expect(screen.getByText("<img src=x onerror=alert(1)>Безопасный текст")).toBeInTheDocument();
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
  });

  it("renders loading, not found and generic error states", () => {
    useVacancyDetail.mockReturnValue({ data: undefined, isLoading: true, isError: false });
    const { unmount } = renderPage();
    expect(screen.getByText("Загрузка вакансии…")).toBeInTheDocument();
    unmount();

    useVacancyDetail.mockReturnValue({ data: undefined, isLoading: false, isError: true, error: new ApiError("Not found", 404) });
    renderPage();
    expect(screen.getByText("Вакансия не найдена")).toBeInTheDocument();
    cleanup();

    useVacancyDetail.mockReturnValue({ data: undefined, isLoading: false, isError: true, error: new Error("network") });
    renderPage();
    expect(screen.getByText("Не удалось загрузить вакансию.")).toBeInTheDocument();
  });

  it("preserves a list back target when navigation state is present", () => {
    renderPage({ pathname: "/vacancies/business%3Aabc123", state: { from: { pathname: "/vacancies", search: "?priority=P1&offset=25" } } });

    expect(screen.getByRole("link", { name: "Назад к вакансиям" })).toHaveAttribute("href", "/vacancies?priority=P1&offset=25");
  });
});
