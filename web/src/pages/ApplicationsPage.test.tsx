import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApplicationsPage } from "./ApplicationsPage";

const useApplications = vi.fn();
vi.mock("../hooks/useOrchestrator", () => ({
  useApplications: (...args: unknown[]) => useApplications(...args)
}));

function LocationProbe() {
  return <output data-testid="location">{useLocation().search}</output>;
}

function renderPage(entry = "/applications") {
  return render(<MemoryRouter initialEntries={[entry]}><LocationProbe /><Routes><Route path="/applications" element={<ApplicationsPage />} /><Route path="/vacancies/:presentationKey" element={<p>Vacancy detail</p>} /></Routes></MemoryRouter>);
}

describe("ApplicationsPage", () => {
  beforeEach(() => {
    useApplications.mockReturnValue({ data: { total: 1, limit: 25, offset: 0, items: [{ id: 7, vacancy_id: 2, presentation_key: "business:abc", company: "Example Company", title: "Python Developer", vacancy_url: "https://hh.ru/vacancy/2", status: "interview", applied_at: "2026-09-04T10:00:00Z", application_text: null, employer_response: null, response_received_at: null, interview_at: "2026-09-10T10:00:00Z", offer_at: null, notes: null, platform: "hh", created_at: "2026-09-04T10:00:00Z", updated_at: "2026-09-05T10:00:00Z" }] }, isLoading: false, isError: false });
  });
  afterEach(() => cleanup());

  it("renders application rows, URL filters, and detail navigation", () => {
    renderPage("/applications?status=interview");
    expect(screen.getByText("Example Company")).toBeInTheDocument();
    expect(screen.getAllByText("Интервью")).toHaveLength(2);
    expect(screen.getByRole("combobox", { name: "Статус" })).toHaveValue("interview");
    fireEvent.change(screen.getByRole("combobox", { name: "Статус" }), { target: { value: "rejected" } });
    expect(screen.getByTestId("location")).toHaveTextContent("status=rejected");
    fireEvent.click(screen.getByText("Python Developer"));
    expect(screen.getByText("Vacancy detail")).toBeInTheDocument();
  });

  it("renders loading, empty, and error states", () => {
    useApplications.mockReturnValue({ data: undefined, isLoading: true, isError: false });
    const { unmount } = renderPage();
    expect(screen.getByText("Загрузка…")).toBeInTheDocument();
    unmount();
    useApplications.mockReturnValue({ data: { items: [], total: 0, limit: 25, offset: 0 }, isLoading: false, isError: false });
    renderPage();
    expect(screen.getByText("Откликов не найдено")).toBeInTheDocument();
  });
});
