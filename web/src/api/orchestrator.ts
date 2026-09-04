import { request } from "./client";
import type {
  PipelineRunDetail,
  RunCreateRequest,
  RunCreateResponse,
  RunsResponse,
  SearchProfilesResponse,
  SystemHealth
} from "../types/api";

export const orchestratorApi = {
  getSystemHealth: () => request<SystemHealth>("/api/system/health"),
  getSearchProfiles: () => request<SearchProfilesResponse>("/api/search-profiles"),
  getRuns: (limit = 20, offset = 0) => request<RunsResponse>(`/api/runs?limit=${limit}&offset=${offset}`),
  getRun: (runId: string) => request<PipelineRunDetail>(`/api/runs/${encodeURIComponent(runId)}`),
  startRun: (payload: RunCreateRequest) =>
    request<RunCreateResponse>("/api/runs", { method: "POST", body: JSON.stringify(payload) })
};
