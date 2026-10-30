import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ExportsPage } from "./ExportsPage";

const useExportSchema = vi.fn();
const useDownloadVacancyExport = vi.fn();
const useDownloadApplicationExport = vi.fn();
const downloadBlob = vi.fn();

vi.mock("../hooks/useOrchestrator", () => ({
  useExportSchema: () => useExportSchema(),
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
    { key: "score", label: "Score", default_enabled: false, category: "ai" as const, type: "integer" },
    { key: "presentation_key", label: "Presentation key", default_enabled: false, category: "technical" as const, type: "text" }
  ],
  applications: [
    { key: "company", label: "Компания", default_enabled: true, category: "business" as const, type: "text" },
    { key: "status", label: "Статус отклика", default_enabled: true, category: "business" as const, type: "text" },
    { key: "application_id", label: "Application ID", default_enabled: false, category: "technical" as const, type: "integer" }
  ],
  formats: ["xlsx", "csv"] as const,
  periods: ["all", "7d", "30d", "custom"] as const
};

function mutation(overrides: Partial<{ isPending: boolean; mutateAsync: ReturnType<typeof vi.fn> }> = {}) {
  return { isPending: false, mutateAsync: vi.fn().mockResolvedValue({ blob: new Blob(["file"]), filename: 'attachment; filename="server.xlsx"' }), ...overrides };
}

function renderPage() {
  return render(<ExportsPage />);
}

beforeEach(() => {
  useExportSchema.mockReturnValue({ data: schema, isLoading: false, isError: false });
  useDownloadVacancyExport.mockReturnValue(mutation());
  useDownloadApplicationExport.mockReturnValue(mutation());
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("ExportsPage", () => {
  it("отображает страницу, defaults и категории backend schema", async () => {
    renderPage();

    expect(screen.getByRole("heading", { name: "Экспорт данных" })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByLabelText("Компания")).toBeChecked());
    expect(screen.getByLabelText("Должность")).toBeChecked();
    expect(screen.getByLabelText("Score")).not.toBeChecked();
    expect(screen.getByText("AI")).toBeInTheDocument();
    expect(screen.getByText("Технические")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Excel (.xlsx)" })).toHaveAttribute("aria-pressed", "true");
  });

  it("показывает loading и schema error", () => {
    useExportSchema.mockReturnValue({ data: undefined, isLoading: true, isError: false });
    const { rerender } = renderPage();
    expect(screen.getByText("Загрузка параметров экспорта…")).toBeInTheDocument();

    useExportSchema.mockReturnValue({ data: undefined, isLoading: false, isError: true });
    rerender(<ExportsPage />);
    expect(screen.getByRole("alert")).toHaveTextContent("Не удалось загрузить параметры экспорта.");
  });

  it("переключает entity и применяет application defaults", async () => {
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: "Отклики" }));

    await waitFor(() => expect(screen.getByLabelText("Статус отклика")).toBeChecked());
    expect(screen.queryByLabelText("Должность")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Application ID")).not.toBeChecked();
  });

  it("изменяет column selection, выбирает все и сбрасывает к defaults", async () => {
    renderPage();
    await waitFor(() => expect(screen.getByLabelText("Компания")).toBeChecked());
    fireEvent.click(screen.getByLabelText("Score"));
    expect(screen.getByLabelText("Score")).toBeChecked();
    fireEvent.click(screen.getByRole("button", { name: "Выбрать все" }));
    expect(screen.getByLabelText("Presentation key")).toBeChecked();
    fireEvent.click(screen.getByRole("button", { name: "По умолчанию" }));
    expect(screen.getByLabelText("Score")).not.toBeChecked();
  });

  it("валидирует custom range до скачивания", async () => {
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: "Произвольный период" }));
    fireEvent.change(screen.getByLabelText("С даты"), { target: { value: "2026-10-31" } });
    fireEvent.change(screen.getByLabelText("По дату"), { target: { value: "2026-10-01" } });

    expect(screen.getByRole("alert")).toHaveTextContent("Укажите корректный диапазон дат.");
    expect(screen.getByRole("button", { name: "Скачать" })).toBeDisabled();
  });

  it("отправляет vacancy payload, использует filename и сохраняет пустой файл", async () => {
    const download = mutation({ mutateAsync: vi.fn().mockResolvedValue({ blob: new Blob([]), filename: 'attachment; filename="vacancies-2026-10-31.xlsx"' }) });
    useDownloadVacancyExport.mockReturnValue(download);
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: "Последние 7 дней" }));
    fireEvent.click(screen.getByRole("button", { name: "CSV (.csv)" }));
    fireEvent.click(screen.getByRole("button", { name: "Скачать" }));

    await waitFor(() => expect(download.mutateAsync).toHaveBeenCalledWith({ format: "csv", period: "7d", columns: ["company", "title"] }));
    expect(downloadBlob).toHaveBeenCalledWith(expect.any(Blob), "vacancies-2026-10-31.xlsx");
  });

  it("отправляет custom application payload и использует fallback filename", async () => {
    const download = mutation({ mutateAsync: vi.fn().mockResolvedValue({ blob: new Blob(["file"]), filename: null }) });
    useDownloadApplicationExport.mockReturnValue(download);
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: "Отклики" }));
    fireEvent.click(screen.getByRole("button", { name: "Произвольный период" }));
    fireEvent.change(screen.getByLabelText("С даты"), { target: { value: "2026-10-01" } });
    fireEvent.change(screen.getByLabelText("По дату"), { target: { value: "2026-10-31" } });
    fireEvent.click(screen.getByRole("button", { name: "Скачать" }));

    await waitFor(() => expect(download.mutateAsync).toHaveBeenCalledWith({ format: "xlsx", period: "custom", date_from: "2026-10-01", date_to: "2026-10-31", columns: ["company", "status"] }));
    expect(downloadBlob).toHaveBeenCalledWith(expect.any(Blob), "applications-export.xlsx");
  });

  it("показывает pending и download error", async () => {
    const download = mutation({ isPending: true, mutateAsync: vi.fn() });
    useDownloadVacancyExport.mockReturnValue(download);
    const { rerender } = renderPage();
    expect(screen.getByRole("button", { name: "Формирование файла..." })).toBeDisabled();

    const rejected = mutation({ mutateAsync: vi.fn().mockRejectedValue(new Error("failed")) });
    useDownloadVacancyExport.mockReturnValue(rejected);
    rerender(<ExportsPage />);
    fireEvent.click(screen.getByRole("button", { name: "Скачать" }));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Не удалось сформировать выгрузку."));
  });
});
