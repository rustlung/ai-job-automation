import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ExportsPage } from "./ExportsPage";

const useExportSchema = vi.fn();
const useSearchProfiles = vi.fn();
const useDownloadVacancyExport = vi.fn();
const useDownloadApplicationExport = vi.fn();
const downloadBlob = vi.fn();

vi.mock("../hooks/useOrchestrator", () => ({
  useExportSchema: () => useExportSchema(),
  useSearchProfiles: () => useSearchProfiles(),
  useDownloadVacancyExport: () => useDownloadVacancyExport(),
  useDownloadApplicationExport: () => useDownloadApplicationExport()
}));
vi.mock("../lib/download", () => ({
  downloadBlob: (...args: unknown[]) => downloadBlob(...args),
  filenameFromContentDisposition: (header: string | null, fallback: string) => header?.match(/filename="([^"]+)"/)?.[1] ?? fallback
}));

const schema = {
  vacancies: [
    { key: "company", label: "Компания", default_enabled: true, category: "business" as const, type: "text" },
    { key: "title", label: "Должность", default_enabled: true, category: "business" as const, type: "text" },
    { key: "score", label: "Score", default_enabled: false, category: "ai" as const, type: "integer" }
  ],
  applications: [
    { key: "company", label: "Компания", default_enabled: true, category: "business" as const, type: "text" },
    { key: "status", label: "Статус отклика", default_enabled: true, category: "business" as const, type: "text" }
  ],
  formats: ["xlsx", "csv"] as const,
  periods: ["all", "7d", "30d", "custom"] as const
};

function mutation(overrides: Partial<{ isPending: boolean; mutateAsync: ReturnType<typeof vi.fn> }> = {}) {
  return { isPending: false, mutateAsync: vi.fn().mockResolvedValue({ blob: new Blob(["file"]), filename: 'attachment; filename="server.xlsx"' }), ...overrides };
}

beforeEach(() => {
  useExportSchema.mockReturnValue({ data: schema, isLoading: false, isError: false });
  useSearchProfiles.mockReturnValue({ data: { profiles: [{ id: "test_expanded_search", name: "[TEST] Expanded search", enabled: true }] }, isLoading: false, isError: false });
  useDownloadVacancyExport.mockReturnValue(mutation());
  useDownloadApplicationExport.mockReturnValue(mutation());
});
afterEach(() => { cleanup(); vi.clearAllMocks(); });

describe("ExportsPage", () => {
  it("shows explicit vacancy filters with the visible working default", async () => {
    render(<ExportsPage />);
    await waitFor(() => expect(screen.getByLabelText("Компания")).toBeChecked());
    expect(screen.getByRole("combobox", { name: "Обработка" })).toHaveValue("working");
    expect(screen.getByRole("combobox", { name: "Профиль поиска" })).toBeInTheDocument();
    expect(screen.getByLabelText("Поиск вакансий")).toBeInTheDocument();
  });

  it("switches to the application-only filter panel", () => {
    render(<ExportsPage />);
    fireEvent.click(screen.getByRole("button", { name: "Отклики" }));
    expect(screen.getByRole("combobox", { name: "Статус отклика" })).toBeInTheDocument();
    expect(screen.getByLabelText("Платформа")).toBeInTheDocument();
    expect(screen.getByLabelText("Поиск откликов")).toBeInTheDocument();
    expect(screen.queryByRole("combobox", { name: "Обработка" })).not.toBeInTheDocument();
  });

  it("sends only the vacancy filter set and ignores list pagination", async () => {
    const download = mutation();
    useDownloadVacancyExport.mockReturnValue(download);
    render(<ExportsPage />);
    fireEvent.change(screen.getByLabelText("Обработка"), { target: { value: "rejected" } });
    fireEvent.change(screen.getByLabelText("Поиск вакансий"), { target: { value: "Python" } });
    fireEvent.click(screen.getByRole("button", { name: "CSV (.csv)" }));
    fireEvent.click(screen.getByRole("button", { name: "Скачать выгрузку" }));
    await waitFor(() => expect(download.mutateAsync).toHaveBeenCalledWith(expect.objectContaining({
      format: "csv", period: "all", vacancy_filters: expect.objectContaining({ processing: "rejected", search: "Python" })
    })));
    expect(download.mutateAsync.mock.calls[0][0]).not.toHaveProperty("application_filters");
  });

  it("sends only application filters and uses an application fallback filename", async () => {
    const download = mutation({ mutateAsync: vi.fn().mockResolvedValue({ blob: new Blob(["file"]), filename: null }) });
    useDownloadApplicationExport.mockReturnValue(download);
    render(<ExportsPage />);
    fireEvent.click(screen.getByRole("button", { name: "Отклики" }));
    fireEvent.change(screen.getByRole("combobox", { name: "Статус отклика" }), { target: { value: "interview" } });
    fireEvent.change(screen.getByLabelText("С даты откликов"), { target: { value: "2026-10-01" } });
    fireEvent.change(screen.getByLabelText("Платформа"), { target: { value: "hh" } });
    fireEvent.click(screen.getByRole("button", { name: "Скачать выгрузку" }));
    await waitFor(() => expect(download.mutateAsync).toHaveBeenCalledWith(expect.objectContaining({
      application_filters: { status: "interview", date_from: "2026-10-01", platform: "hh" }
    })));
    expect(download.mutateAsync.mock.calls[0][0]).not.toHaveProperty("vacancy_filters");
    expect(downloadBlob).toHaveBeenCalledWith(expect.any(Blob), "applications-export.xlsx");
  });

  it("resets filters for the active entity", () => {
    render(<ExportsPage />);
    fireEvent.change(screen.getByRole("combobox", { name: "Обработка" }), { target: { value: "errors" } });
    fireEvent.click(screen.getByRole("button", { name: "Сбросить фильтры" }));
    expect(screen.getByRole("combobox", { name: "Обработка" })).toHaveValue("working");
    fireEvent.click(screen.getByRole("button", { name: "Отклики" }));
    fireEvent.change(screen.getByLabelText("Платформа"), { target: { value: "hh" } });
    fireEvent.click(screen.getByRole("button", { name: "Сбросить фильтры" }));
    expect(screen.getByLabelText("Платформа")).toHaveValue("");
  });

  it("keeps long filter controls inside responsive grid cells", () => {
    render(<ExportsPage />);
    expect(screen.getByLabelText("Поиск вакансий").closest("label")).toHaveClass("min-w-0");
    expect(screen.getByLabelText("Профиль поиска").closest("label")).toHaveClass("min-w-0");
  });

  it("shows download failures without treating an empty file as an error", async () => {
    const download = mutation({ mutateAsync: vi.fn().mockRejectedValue(new Error("failed")) });
    useDownloadVacancyExport.mockReturnValue(download);
    render(<ExportsPage />);
    fireEvent.click(screen.getByRole("button", { name: "Скачать выгрузку" }));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Не удалось сформировать выгрузку."));
  });
});
