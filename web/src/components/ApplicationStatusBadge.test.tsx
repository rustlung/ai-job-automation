import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ApplicationStatusBadge } from "./ApplicationStatusBadge";

describe("ApplicationStatusBadge", () => {
  it("uses a readable label for a persisted status", () => {
    render(<ApplicationStatusBadge status="interview" />);
    expect(screen.getByText("Интервью")).toBeInTheDocument();
  });

  it("makes missing application explicit without inventing a domain status", () => {
    render(<ApplicationStatusBadge status={null} />);
    expect(screen.getByText("Без отклика")).toBeInTheDocument();
  });
});
