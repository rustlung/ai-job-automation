import { describe, expect, it } from "vitest";

import { profileIdsFromSelection } from "./selection";

const profiles = [
  { id: "vibecoding_keywords", name: "Vibecoding", track: "main", source_type: "expanded_search", enabled: true },
  { id: "disabled", name: "Disabled", track: "main", source_type: "expanded_search", enabled: false }
] as const;

describe("profileIdsFromSelection", () => {
  it("keeps only selected enabled profiles", () => {
    expect(profileIdsFromSelection({ vibecoding_keywords: true, disabled: true }, [...profiles])).toEqual(["vibecoding_keywords"]);
  });

  it("returns an empty list for an empty selection", () => {
    expect(profileIdsFromSelection({}, [...profiles])).toEqual([]);
  });
});
