import { request, requestBlob } from "./client";
import type {
  PipelineRunDetail,
  ApplicationCreateRequest,
  ApplicationFilters,
  ApplicationListResponse,
  ApplicationPatchRequest, ApplicationWriteResponse,
  RunCreateRequest,
  RunCreateResponse, DiagnosticConfig, DiagnosticHealthItem, DiagnosticRecentRun, DiagnosticRunResponse, HHDiagnostic,
  RunsResponse,
  SearchProfilesResponse,
  SystemHealth,
  VacancyDetail, BulkDeleteResult, DeleteResult,
  VacancyFilters,
  VacancyListResponse, VacancyUserState, VacancyUserStatePatchRequest, VacancyUserStateWriteResponse, ManualVacancyCreateRequest, ManualVacancyCreateResponse, StatisticsRequest, VacancyStatistics, ExportRequest, ExportSchema, ExportDownload
} from "../types/api";

function vacancyQuery(filters: VacancyFilters): string {
  const params = new URLSearchParams();
  const optionalFilters: Array<[string, string | undefined]> = [
    ["date_from", filters.date_from],
    ["date_to", filters.date_to],
    ["track", filters.track],
    ["profile_id", filters.profile_id],
    ["run_id", filters.run_id],
    ["search", filters.search],
    ["application_status", filters.application_status]
    , ["vacancy_status", filters.vacancy_status]
    , ["user_priority", filters.user_priority]
    , ["processing", filters.processing]
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

function applicationQuery(filters: ApplicationFilters): string {
  const params = new URLSearchParams();
  (["status", "date_from", "date_to", "platform", "search"] as const).forEach((key) => {
    const value = filters[key];
    if (value) params.set(key, value);
  });
  params.set("limit", String(filters.limit));
  params.set("offset", String(filters.offset));
  return params.toString();
}

function statisticsQuery(request: StatisticsRequest): string {
  const params = new URLSearchParams({ period: request.period });
  if (request.date_from) params.set("date_from", request.date_from);
  if (request.date_to) params.set("date_to", request.date_to);
  return params.toString();
}

export const orchestratorApi = {
  getSystemHealth: () => request<SystemHealth>("/api/system/health"),
  getSearchProfiles: () => request<SearchProfilesResponse>("/api/search-profiles"),
  getRuns: (limit = 20, offset = 0) => request<RunsResponse>(`/api/runs?limit=${limit}&offset=${offset}`),
  getRun: (runId: string) => request<PipelineRunDetail>(`/api/runs/${encodeURIComponent(runId)}`),
  cancelRun: (runId: string) => request<PipelineRunDetail>(`/api/runs/${encodeURIComponent(runId)}/cancel`, { method: "POST" }),
  getVacancies: (filters: VacancyFilters) => request<VacancyListResponse>(`/api/vacancies?${vacancyQuery(filters)}`),
  getStatistics: (statistics: StatisticsRequest) => request<VacancyStatistics>(`/api/statistics?${statisticsQuery(statistics)}`),
  getExportSchema: () => request<ExportSchema>("/api/exports/schema"),
  downloadVacancyExport: (payload: ExportRequest) => requestBlob("/api/exports/vacancies", { method: "POST", body: JSON.stringify(payload) }) as Promise<ExportDownload>,
  downloadApplicationExport: (payload: ExportRequest) => requestBlob("/api/exports/applications", { method: "POST", body: JSON.stringify(payload) }) as Promise<ExportDownload>,
  getVacancyDetail: (presentationKey: string) => request<VacancyDetail>(`/api/vacancies/${encodeURIComponent(presentationKey)}`),
  deleteVacancy: (presentationKey: string) => request<DeleteResult>(`/api/vacancies/${encodeURIComponent(presentationKey)}`, { method: "DELETE" }),
  bulkDeleteVacancies: (presentationKeys: string[]) => request<BulkDeleteResult>("/api/vacancies/bulk-delete", { method: "POST", body: JSON.stringify({ presentation_keys: presentationKeys }) }),
  createManualVacancy: (payload: ManualVacancyCreateRequest) => request<ManualVacancyCreateResponse>("/api/vacancies/manual", { method: "POST", body: JSON.stringify(payload) }),
  getVacancyUserState: (presentationKey: string) => request<VacancyUserState>(`/api/vacancies/${encodeURIComponent(presentationKey)}/user-state`),
  updateVacancyUserState: (presentationKey: string, payload: VacancyUserStatePatchRequest) => request<VacancyUserStateWriteResponse>(`/api/vacancies/${encodeURIComponent(presentationKey)}/user-state`, { method: "PATCH", body: JSON.stringify(payload) }),
  getApplications: (filters: ApplicationFilters) => request<ApplicationListResponse>(`/api/applications?${applicationQuery(filters)}`),
  createApplication: (vacancyId: number, payload: ApplicationCreateRequest) =>
    request<ApplicationWriteResponse>(`/api/vacancies/${vacancyId}/applications`, { method: "POST", body: JSON.stringify(payload) }),
  updateApplication: (applicationId: number, payload: ApplicationPatchRequest) =>
    request<ApplicationWriteResponse>(`/api/applications/${applicationId}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deleteApplication: (applicationId: number) => request<DeleteResult>(`/api/applications/${applicationId}`, { method: "DELETE" }),
  bulkDeleteApplications: (applicationIds: number[]) => request<BulkDeleteResult>("/api/applications/bulk-delete", { method: "POST", body: JSON.stringify({ application_ids: applicationIds }) }),
  startRun: (payload: RunCreateRequest) =>
    request<RunCreateResponse>("/api/runs", { method: "POST", body: JSON.stringify(payload) }),
  getDiagnosticsHealth: () => request<Record<string, DiagnosticHealthItem>>("/api/diagnostics/health"),
  getDiagnosticRuns: (limit = 10) => request<{ runs: DiagnosticRecentRun[] }>(`/api/diagnostics/runs?limit=${limit}`),
  getDiagnosticRun: (runId: string) => request<DiagnosticRunResponse>(`/api/diagnostics/runs/${encodeURIComponent(runId)}`),
  getDiagnosticsConfig: () => request<DiagnosticConfig>("/api/diagnostics/config"),
  runHHDiagnostic: () => request<HHDiagnostic>("/api/diagnostics/hh-check", { method: "POST" })
};
