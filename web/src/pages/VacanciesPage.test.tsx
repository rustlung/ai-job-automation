import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

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
  member_count: 2,
  application_id: null,
  application_status: null,
  application_updated_at: null,
  vacancy_status: "active" as const,
  user_priority: null,
  user_comment: null
};

const useVacancies = vi.fn();
const useSearchProfiles = vi.fn();
const useUpdateVacancyUserState = vi.fn();
const useCreateManualVacancy = vi.fn();
vi.mock("../hooks/useOrchestrator", () => ({
  useVacancies: (...args: unknown[]) => useVacancies(...args),
  useSearchProfiles: () => useSearchProfiles(),
  useUpdateVacancyUserState: () => useUpdateVacancyUserState(),
  useCreateManualVacancy: () => useCreateManualVacancy()
}));

function LocationProbe() {
  return <output data-testid="location">{useLocation().search}</output>;
}

function renderPage(initialEntry = "/vacancies") {
  return render(<MemoryRouter initialEntries={[initialEntry]}><LocationProbe /><Routes><Route path="/vacancies" element={<VacanciesPage />} /><Route path="/vacancies/:presentationKey" element={<p>Detail route</p>} /></Routes></MemoryRouter>);
}

function profileQuery(overrides = {}) {
  return {
    data: { profiles: [
      { id: "ai_automation_keywords", name: "AI Automation", enabled: true, user_selectable: true },
      { id: "legacy_profile", name: "Legacy profile", enabled: true, user_selectable: false },
      { id: "disabled_profile", name: "Disabled profile", enabled: false, user_selectable: false }
    ] },
    isLoading: false,
    isError: false,
    ...overrides
  };
}

describe("VacanciesPage", () => {
  beforeEach(() => {
    useVacancies.mockReturnValue({ data: { items: [vacancy], total: 1, limit: 25, offset: 0 }, isLoading: false, isError: false });
    useSearchProfiles.mockReturnValue(profileQuery());
    useUpdateVacancyUserState.mockReturnValue({ isPending: false, isError: false, mutate: vi.fn() });
    useCreateManualVacancy.mockReturnValue({ isPending: false, mutateAsync: vi.fn() });
  });
  afterEach(() => cleanup());

  it("renders grouped rows, profile display names and detail links", () => {
    renderPage("/vacancies?priority=P1");

    expect(screen.getByText("Example Company")).toBeInTheDocument();
    expect(screen.getAllByText("Без отклика")).toHaveLength(2);
    expect(screen.getAllByText("AI Automation")).toHaveLength(2);
    expect(screen.getByRole("checkbox", { name: "P1" })).toBeChecked();
    fireEvent.click(screen.getByText("Python Developer"));
    expect(screen.getByText("Detail route")).toBeInTheDocument();
  });

  it("redirects to the DB-created manual vacancy even when CRM append failed", async () => {
    const create = vi.fn().mockResolvedValue({
      created: true,
      presentation_key: "manual:uuid-1",
      vacancy_id: 7,
      user_state: null,
      crm_sync: { vacancy_id: 7, presentation_key: "manual:uuid-1", status: "failed", last_attempt_at: null, synced_at: null, error_code: "crm_sync_timeout", error_message_safe: "Google CRM row creation failed" },
      duplicate: null
    });
    useCreateManualVacancy.mockReturnValue({ isPending: false, mutateAsync: create });
    renderPage();

    fireEvent.click(screen.getByRole("button", { name: "Добавить вакансию" }));
    fireEvent.change(screen.getByLabelText("Компания *"), { target: { value: "Manual Co" } });
    fireEvent.change(screen.getByLabelText("Должность *"), { target: { value: "Manual role" } });
    fireEvent.change(screen.getByLabelText("Описание *"), { target: { value: "Описание вакансии" } });
    fireEvent.click(screen.getByRole("button", { name: "Создать вакансию" }));

    await waitFor(() => expect(screen.getByText("Detail route")).toBeInTheDocument());
    expect(create).toHaveBeenCalledWith(expect.objectContaining({ company: "Manual Co", title: "Manual role" }));
  });

  it("keeps table headers and row values in the same semantic column order", () => {
    const { container } = renderPage();
    const headers = Array.from(container.querySelectorAll("thead th")).map((header) => header.textContent);
    const cells = Array.from(container.querySelectorAll("tbody tr:first-child > td"));
    const vacancyStatusSelect = cells[4]?.querySelector("select") as HTMLSelectElement | null;
    const userPrioritySelect = cells[7]?.querySelector("select") as HTMLSelectElement | null;

    expect(headers).toEqual(["Дата", "Компания", "Вакансия", "Зарплата", "Статус вакансии", "Статус отклика", "AI Priority", "Мой приоритет", "Мой комментарий", "Score", "Track", "Профили поиска"]);
    expect(cells).toHaveLength(headers.length);
    expect(vacancyStatusSelect).toHaveValue("active");
    expect(cells[5]).toHaveTextContent("Без отклика");
    expect(cells[6]).toHaveTextContent("P1");
    expect(userPrioritySelect).toHaveValue("");
    expect(cells[8]).toHaveTextContent("Добавить комментарий");
    expect(cells[9]).toHaveTextContent("95");
  });

  it("clears both dates and activates all time", () => {
    renderPage("/vacancies?date_from=2026-09-01&date_to=2026-09-08");

    fireEvent.click(screen.getByRole("button", { name: "Всё время" }));
    expect(screen.getByTestId("location")).not.toHaveTextContent("date_from");
    expect(screen.getByTestId("location")).not.toHaveTextContent("date_to");
    expect(screen.getByRole("button", { name: "Всё время" })).toHaveAttribute("aria-pressed", "true");
  });

  it("activates matching presets and leaves custom date ranges unselected", () => {
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: "3 дня" }));
    expect(screen.getByRole("button", { name: "3 дня" })).toHaveAttribute("aria-pressed", "true");

    fireEvent.change(screen.getByLabelText("С даты"), { target: { value: "2020-01-01" } });
    expect(screen.getByRole("button", { name: "3 дня" })).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByRole("button", { name: "Всё время" })).toHaveAttribute("aria-pressed", "false");
  });

  it("uses enabled API profiles and synchronizes their ids with the URL", () => {
    renderPage();
    const dropdown = screen.getByRole("combobox", { name: "Профиль поиска" });

    expect(screen.getByRole("option", { name: "AI Automation" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Legacy profile" })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "Disabled profile" })).not.toBeInTheDocument();
    fireEvent.change(dropdown, { target: { value: "ai_automation_keywords" } });
    expect(screen.getByTestId("location")).toHaveTextContent("profile_id=ai_automation_keywords");
    fireEvent.change(dropdown, { target: { value: "" } });
    expect(screen.getByTestId("location")).not.toHaveTextContent("profile_id");
  });

  it("restores valid profile ids and safely clears invalid ones", async () => {
    renderPage("/vacancies?profile_id=ai_automation_keywords");
    expect(screen.getByRole("combobox", { name: "Профиль поиска" })).toHaveValue("ai_automation_keywords");
    cleanup();

    renderPage("/vacancies?profile_id=missing_profile");
    await waitFor(() => expect(screen.getByTestId("location")).not.toHaveTextContent("missing_profile"));
    expect(screen.getByRole("combobox", { name: "Профиль поиска" })).toHaveValue("");
  });

  it("keeps the list available when profile metadata is loading or unavailable", () => {
    useSearchProfiles.mockReturnValue(profileQuery({ data: undefined, isLoading: true }));
    renderPage();
    expect(screen.getByText("Example Company")).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "Профиль поиска" })).toBeDisabled();
    cleanup();

    useSearchProfiles.mockReturnValue(profileQuery({ isError: true }));
    renderPage();
    expect(screen.getByText("Example Company")).toBeInTheDocument();
    expect(screen.getByText("Фильтр профилей недоступен.")).toBeInTheDocument();
    expect(useVacancies).toHaveBeenLastCalledWith(expect.objectContaining({ profile_id: undefined }));
  });

  it("synchronizes the application status filter and resets pagination", () => {
    renderPage("/vacancies?offset=50");
    const dropdown = screen.getByRole("combobox", { name: "Статус отклика" });

    fireEvent.change(dropdown, { target: { value: "submitted" } });
    expect(screen.getByTestId("location")).toHaveTextContent("application_status=submitted");
    expect(screen.getByTestId("location")).not.toHaveTextContent("offset");
    expect(useVacancies).toHaveBeenLastCalledWith(expect.objectContaining({ application_status: "submitted" }));

    fireEvent.change(dropdown, { target: { value: "response_received" } });
    expect(screen.getByTestId("location")).toHaveTextContent("application_status=response_received");

    fireEvent.change(dropdown, { target: { value: "interview" } });
    expect(screen.getByTestId("location")).toHaveTextContent("application_status=interview");

    fireEvent.change(dropdown, { target: { value: "" } });
    expect(screen.getByTestId("location")).not.toHaveTextContent("application_status");
  });

  it("synchronizes vacancy status and user priority filters and resets pagination", () => {
    renderPage("/vacancies?offset=50");
    fireEvent.change(screen.getByRole("combobox", { name: "Статус вакансии" }), { target: { value: "archived" } });
    expect(screen.getByTestId("location")).toHaveTextContent("vacancy_status=archived");
    expect(screen.getByTestId("location")).not.toHaveTextContent("offset");
    fireEvent.change(screen.getByRole("combobox", { name: "Мой приоритет" }), { target: { value: "P3" } });
    expect(screen.getByTestId("location")).toHaveTextContent("user_priority=P3");
    expect(useVacancies).toHaveBeenLastCalledWith(expect.objectContaining({ vacancy_status: "archived", user_priority: "P3" }));
  });

  it("shows independent vacancy and user priority values", () => {
    useVacancies.mockReturnValue({ data: { items: [{ ...vacancy, priority: "P1", user_priority: "P3", vacancy_status: "closed" }], total: 1, limit: 25, offset: 0 }, isLoading: false, isError: false });
    renderPage();
    expect(screen.getAllByText("Закрыта")).toHaveLength(2);
    expect(screen.getByRole("combobox", { name: "Изменить мой приоритет" })).toHaveValue("P3");
  });

  it("updates status and priority inline through the shared user-state mutation", () => {
    const mutate = vi.fn();
    useUpdateVacancyUserState.mockReturnValue({ isPending: false, isError: false, mutate });
    renderPage();

    fireEvent.change(screen.getByRole("combobox", { name: "Изменить статус вакансии" }), { target: { value: "archived" } });
    fireEvent.change(screen.getByRole("combobox", { name: "Изменить мой приоритет" }), { target: { value: "P2" } });
    expect(mutate).toHaveBeenNthCalledWith(1, { presentationKey: "business:abc123", payload: { vacancy_status: "archived" } });
    expect(mutate).toHaveBeenNthCalledWith(2, { presentationKey: "business:abc123", payload: { user_priority: "P2" } });
  });

  it("clears priority and saves only a changed inline comment", () => {
    const mutate = vi.fn();
    useVacancies.mockReturnValue({ data: { items: [{ ...vacancy, user_priority: "P3", user_comment: "Existing note" }], total: 1, limit: 25, offset: 0 }, isLoading: false, isError: false });
    useUpdateVacancyUserState.mockReturnValue({ isPending: false, isError: false, mutate });
    renderPage();

    fireEvent.change(screen.getByRole("combobox", { name: "Изменить мой приоритет" }), { target: { value: "" } });
    expect(mutate).toHaveBeenCalledWith({ presentationKey: "business:abc123", payload: { user_priority: null } });
    fireEvent.click(screen.getByRole("button", { name: "Изменить комментарий" }));
    fireEvent.click(screen.getByRole("button", { name: "Сохранить комментарий" }));
    expect(mutate).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole("button", { name: "Изменить комментарий" }));
    fireEvent.change(screen.getByRole("textbox", { name: "Мой комментарий" }), { target: { value: "" } });
    fireEvent.click(screen.getByRole("button", { name: "Сохранить комментарий" }));
    expect(mutate).toHaveBeenLastCalledWith(expect.objectContaining({ payload: { comment: null } }), expect.any(Object));
  });

  it("keeps the previous visible values and shows failure without a false success state", () => {
    useVacancies.mockReturnValue({ data: { items: [{ ...vacancy, vacancy_status: "closed", user_comment: "Existing note" }], total: 1, limit: 25, offset: 0 }, isLoading: false, isError: false });
    useUpdateVacancyUserState.mockReturnValue({ isPending: false, isError: true, mutate: vi.fn() });
    renderPage();
    expect(screen.getByRole("combobox", { name: "Изменить статус вакансии" })).toHaveValue("closed");
    expect(screen.getAllByText("Не сохранено")).not.toHaveLength(0);
  });

  it("restores an application status filter from the URL without local expansion", () => {
    renderPage("/vacancies?application_status=response_received");
    expect(screen.getByRole("combobox", { name: "Статус отклика" })).toHaveValue("response_received");
    expect(useVacancies).toHaveBeenLastCalledWith(expect.objectContaining({ application_status: "response_received" }));
  });

  it("resets pagination for first page, filters and page size", () => {
    useVacancies.mockReturnValue({ data: { items: [vacancy], total: 100, limit: 25, offset: 50 }, isLoading: false, isError: false });
    renderPage("/vacancies?offset=50");

    expect(screen.getByRole("button", { name: "На первую страницу" })).toBeEnabled();
    fireEvent.click(screen.getByRole("button", { name: "На первую страницу" }));
    expect(screen.getByTestId("location")).not.toHaveTextContent("offset");
    cleanup();

    renderPage("/vacancies?offset=50");
    fireEvent.click(screen.getByRole("checkbox", { name: "P1" }));
    expect(screen.getByTestId("location")).not.toHaveTextContent("offset");
    cleanup();

    renderPage("/vacancies?offset=50");
    fireEvent.change(screen.getByRole("combobox", { name: "На странице" }), { target: { value: "50" } });
    expect(screen.getByTestId("location")).not.toHaveTextContent("offset");
  });

  it("disables first and previous page controls on the first page", () => {
    renderPage();
    expect(screen.getByRole("button", { name: "На первую страницу" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Предыдущая страница" })).toBeDisabled();
  });

  it("renders loading, empty and error states", () => {
    useVacancies.mockReturnValue({ data: undefined, isLoading: true, isError: false });
    const { unmount } = renderPage();
    expect(screen.getByText("Загрузка…")).toBeInTheDocument();
    unmount();

    useVacancies.mockReturnValue({ data: { items: [], total: 0, limit: 25, offset: 0 }, isLoading: false, isError: false });
    renderPage();
    expect(screen.getByText("Вакансий не найдено")).toBeInTheDocument();
    cleanup();

    useVacancies.mockReturnValue({ data: undefined, isLoading: false, isError: true });
    renderPage();
    expect(screen.getByText("Не удалось загрузить список вакансий.")).toBeInTheDocument();
  });
});
