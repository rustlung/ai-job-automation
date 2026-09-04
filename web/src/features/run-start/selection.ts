import type { PipelineRunOverrides, SearchProfile } from "../../types/api";

export type ProfileSelection = Record<string, boolean>;

export const emptyOverrides: PipelineRunOverrides = {
  max_pages_override: null,
  max_filter_items_override: null,
  max_enrich_items_override: null
};

export function profileIdsFromSelection(selection: ProfileSelection, profiles: SearchProfile[]): string[] {
  return profiles.filter((profile) => profile.enabled && selection[profile.id] === true).map((profile) => profile.id);
}

export function parseOptionalLimit(value: string): number | null {
  if (value.trim() === "") return null;
  const number = Number(value);
  return Number.isInteger(number) && number > 0 ? number : null;
}
