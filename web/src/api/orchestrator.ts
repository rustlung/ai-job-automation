import { request } from "./client";
import type {
  PipelineRunDetail,
  RunCreateRequest,
  RunCreateResponse,
  RunsResponse,
  SearchProfilesResponse,
  SystemHealth,
  VacancyDetail,
  VacancyFilters,
  VacancyListResponse
} from "../types/api";

function vacancyQuery(filters: VacancyFilters): string {
  const params = new URLSearchParams();
  const optionalFilters: Array<[string, string | undefined]> = [
    ["date_from", filters.date_from],
    ["date_to", filters.date_to],
    ["track", filters.track],
    ["profile_id", filters.profile_id],
    ["run_id", filters.run_id],
    ["search", filters.search]
  ];
  optionalFilters.forEach(([key, value]) => {
    if (value) params.set(key, value);
  });
  filters.priority?.forEach((value) => params.append("priority", value));
  params.set("limit", String(filters.limit));
  params.set("offset", String(filters.offset));
  params.set("sort", filters.sort);
  params.set("sort_direction", filters.sort_direction);
  return params.toString();
}

export const orchestratorApi = {
  getSystemHealth: () => request<SystemHealth>("/api/system/health"),
  getSearchProfiles: () => request<SearchProfilesResponse>("/api/search-profiles"),
  getRuns: (limit = 20, offset = 0) => request<RunsResponse>(`/api/runs?limit=${limit}&offset=${offset}`),
  getRun: (runId: string) => request<PipelineRunDetail>(`/api/runs/${encodeURIComponent(runId)}`),
  getVacancies: (filters: VacancyFilters) => request<VacancyListResponse>(`/api/vacancies?${vacancyQuery(filters)}`),
  getVacancyDetail: (presentationKey: string) => request<VacancyDetail>(`/api/vacancies/${encodeURIComponent(presentationKey)}`),
  startRun: (payload: RunCreateRequest) =>
    request<RunCreateResponse>("/api/runs", { method: "POST", body: JSON.stringify(payload) })
};
