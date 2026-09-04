import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { StartRunPage } from "./StartRunPage";

vi.mock("../hooks/useOrchestrator", () => ({
  useSearchProfiles: () => ({
    data: {
      profiles: [
        { id: "vibecoding_keywords", name: "Vibecoding", track: "main", source_type: "expanded_search", enabled: true }
      ]
    },
    isLoading: false,
    isError: false
  }),
  useStartRun: () => ({ isPending: false, isError: false, mutate: vi.fn() })
}));

describe("StartRunPage", () => {
  it("disables submission until at least one profile is selected", () => {
    render(<MemoryRouter><StartRunPage /></MemoryRouter>);

    expect(screen.getByRole("button", { name: "Запустить поиск" })).toBeDisabled();
    expect(screen.getByRole("status")).toHaveTextContent("Выберите хотя бы один поисковый профиль.");
  });
});
