import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { LegacyCrmKeyMigrationStatus } from "./LegacyCrmKeyMigrationStatus";

describe("LegacyCrmKeyMigrationStatus", () => {
  it("renders a positive legacy match count", () => {
    render(<LegacyCrmKeyMigrationStatus matches={17} />);

    expect(screen.getByText("17 совпадений в этом запуске")).toBeInTheDocument();
  });

  it("renders a safe zero state for missing or invalid older stats", () => {
    render(<LegacyCrmKeyMigrationStatus />);

    expect(screen.getByText("0 совпадений в этом запуске")).toBeInTheDocument();
  });
});
