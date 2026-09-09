import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
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
  applications: [],
  members: [
    { source: "hh", external_id: "102", url: "https://samara.hh.ru/vacancy/102", title: "Python Developer", company: "Example Company", location: "Самара", representative: true },
    { source: "hh", external_id: "101", url: "https://kazan.hh.ru/vacancy/101", title: "Python Developer", company: "Example Company", location: "Казань", representative: false }
  ]
};

const useVacancyDetail = vi.fn();
const useSearchProfiles = vi.fn();
const useCreateApplication = vi.fn();
const useUpdateApplication = vi.fn();
const useRetryApplicationCrmSync = vi.fn();
vi.mock("../hooks/useOrchestrator", () => ({
  useVacancyDetail: (...args: unknown[]) => useVacancyDetail(...args),
  useSearchProfiles: () => useSearchProfiles(),
  useCreateApplication: () => useCreateApplication(),
  useUpdateApplication: () => useUpdateApplication(),
  useRetryApplicationCrmSync: () => useRetryApplicationCrmSync()
}));

function renderPage(entry: string | { pathname: string; state?: unknown } = "/vacancies/business%3Aabc123") {
  return render(<MemoryRouter initialEntries={[entry]}><Routes><Route path="/vacancies/:presentationKey" element={<VacancyDetailPage />} /><Route path="/vacancies" element={<p>Vacancies list</p>} /></Routes></MemoryRouter>);
}

describe("VacancyDetailPage", () => {
  beforeEach(() => {
    useVacancyDetail.mockReturnValue({ data: vacancy, isLoading: false, isError: false });
    useSearchProfiles.mockReturnValue({ data: { profiles: [{ id: "ai_automation_keywords", name: "AI Automation" }] }, isError: false });
    useCreateApplication.mockReturnValue({ isPending: false, error: null, mutateAsync: vi.fn() });
    useUpdateApplication.mockReturnValue({ isPending: false, error: null, mutateAsync: vi.fn() });
    useRetryApplicationCrmSync.mockReturnValue({ isPending: false, mutate: vi.fn() });
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
    expect(screen.getByText("Отклик не отправлен")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Открыть оригинал" })).toHaveAttribute("href", vacancy.url);
  });

  it("shows all group applications and creates a canonical application", async () => {
    const createApplication = vi.fn().mockResolvedValue({ id: 3 });
    useCreateApplication.mockReturnValue({ isPending: false, error: null, mutateAsync: createApplication });
    useVacancyDetail.mockReturnValue({ data: {
      ...vacancy,
      applications: [{
        application: { id: 2, vacancy_id: 2, status: "rejected", applied_at: "2026-09-04T10:00:00Z", application_text: "Текст", employer_response: "Спасибо, нет", response_received_at: "2026-09-05T10:00:00Z", interview_at: null, offer_at: null, notes: null, platform: "hh", created_at: "2026-09-04T10:00:00Z", updated_at: "2026-09-05T10:00:00Z" },
        source: "hh", external_id: "101", url: "https://kazan.hh.ru/vacancy/101", representative_member: false, current: true
      }]
    }, isLoading: false, isError: false });
    renderPage();

    expect(screen.getByText("Текущий отклик")).toBeInTheDocument();
    expect(screen.getByText("Спасибо, нет")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Добавить ещё" }));
    fireEvent.click(screen.getByRole("button", { name: "Сохранить" }));
    await waitFor(() => expect(createApplication).toHaveBeenCalledWith(expect.objectContaining({ vacancyId: 1, payload: expect.objectContaining({ status: "submitted", platform: "hh" }) })));
  });

  it("falls back to raw profile ids when metadata is unavailable", () => {
    useSearchProfiles.mockReturnValue({ data: undefined, isError: true });
    renderPage();

    expect(screen.getByText("ai_automation_keywords")).toBeInTheDocument();
  });

  it("shows failed CRM sync for the current application and retries without hiding data", () => {
    const retry = vi.fn();
    useRetryApplicationCrmSync.mockReturnValue({ isPending: false, mutate: retry });
    useVacancyDetail.mockReturnValue({ data: {
      ...vacancy,
      applications: [{
        application: { id: 2, vacancy_id: 1, status: "submitted", applied_at: null, application_text: "Текст", employer_response: null, response_received_at: null, interview_at: null, offer_at: null, notes: null, platform: "hh", created_at: "2026-09-04T10:00:00Z", updated_at: "2026-09-05T10:00:00Z" },
        source: "hh", external_id: "102", url: vacancy.url, representative_member: true, current: true,
        crm_sync: { application_id: 2, status: "failed", last_attempt_at: "2026-09-05T10:00:00Z", synced_at: null, error_code: "crm_sync_timeout", error_message_safe: "Google CRM sync failed" }
      }]
    }, isLoading: false, isError: false });
    renderPage();

    expect(screen.getByText("Ошибка синхронизации CRM")).toBeInTheDocument();
    expect(screen.getByText("Текст")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Повторить синхронизацию" }));
    expect(retry).toHaveBeenCalledWith(2);
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
