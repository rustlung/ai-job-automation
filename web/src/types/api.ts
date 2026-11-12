export type HealthStatus = "ok" | "degraded" | "unavailable" | "unknown" | string;

export interface ComponentHealth {
  status: HealthStatus;
  component: string;
  available: boolean;
}

export interface SystemHealth {
  status: HealthStatus;
  orchestrator: ComponentHealth;
  worker: ComponentHealth;
  ollama: ComponentHealth;
  compute_status: HealthStatus;
  pipeline_runs_supported: boolean;
}

export type SearchProfileTrack = "main" | "alternative";
export type SearchProfileSourceType = "resume_recommendations" | "expanded_search";

export interface SearchProfile {
  id: string;
  name: string;
  track: SearchProfileTrack;
  source_type: SearchProfileSourceType;
  enabled: boolean;
  user_selectable: boolean;
  is_test?: boolean;
}

export interface SearchProfilesResponse {
  profiles: SearchProfile[];
}

export type PipelineRunStatus =
  | "accepted"
  | "running"
  | "completed"
  | "completed_with_errors"
  | "failed"
  | "cancelled";

export type PipelineRunTriggerSource = "manual_n8n" | "web_ui" | "scheduled";

export interface PipelineRunOverrides {
  max_pages_override: number | null;
  max_filter_items_override: number | null;
  max_enrich_items_override: number | null;
}

export interface PipelineRunDiagnostic {
  code: string;
  count: number;
  summary: string;
}

export interface PipelineRunStatsSnapshot {
  legacy_crm_key_matches?: number;
  warnings?: PipelineRunDiagnostic[];
  partial_failures?: PipelineRunDiagnostic[];
  integration_errors?: PipelineRunDiagnostic[];
  progress?: {
    stage: "queued" | "collection" | "discovery" | "preliminary" | "enrichment" | "persistence" | "post_processing" | "recovery" | "completed" | "failed" | "cancelled";
    current: number | null;
    total: number | null;
    percent: number | null;
    message: string;
    details?: Record<string, unknown>;
  };
  [key: string]: unknown;
}

export interface RunCreateRequest {
  profile_ids: string[];
  overrides: PipelineRunOverrides;
}

export interface PipelineRunSummary {
  run_id: string;
  trigger_source: PipelineRunTriggerSource;
  status: PipelineRunStatus;
  profile_ids: string[];
  stats_snapshot: PipelineRunStatsSnapshot | null;
  error_code: string | null;
  started_at: string;
  completed_at: string | null;
}

export interface PipelineRunDetail extends PipelineRunSummary {
  config_snapshot: Record<string, unknown>;
  error_summary: string | null;
  created_at: string;
  updated_at: string;
}

export interface RunCreateResponse {
  run: PipelineRunDetail;
  accepted: boolean;
}

export interface RunsResponse {
  count: number;
  total: number;
  limit: number;
  offset: number;
  runs: PipelineRunSummary[];
}

export interface ApiErrorBody {
  detail?: string | { error_code?: string };
}

export type VacancyPriority = "P1" | "P2" | "P3" | "ALT";
export type VacancyUserPriority = "P1" | "P2" | "P3";
export type VacancyStatus = "active" | "archived" | "closed";
export type ManualVacancyOrigin = "hh" | "company_site" | "habr" | "telegram" | "direct_contact" | "other";
export type VacancyStatusFilter = VacancyStatus;
export type VacancyUserPriorityFilter = VacancyUserPriority | "none";
export type ApplicationStatus = "submitted" | "response_received" | "screening" | "test_task" | "interview" | "offer" | "rejected" | "withdrawn";
export type StatisticsPeriod = "today" | "7d" | "14d" | "30d" | "all" | "custom";
export type VacancyApplicationStatusFilter = ApplicationStatus | "none";
export type VacancyListSort = "first_seen" | "final_score" | "priority";
export type SortDirection = "asc" | "desc";
export type VacancyProcessingFilter = "working" | "rejected" | "errors" | "all";
export type PreliminaryOutcome = "rejected_by_policy" | "rejected_by_ai" | "keep_main" | "keep_alt" | "uncertain" | "preliminary_fallback" | "preliminary_failed";
export type VacancyProcessingState = "preliminary_rejected" | "preliminary_kept" | "enrichment_failed" | "enriched" | "processing_failed";

export interface VacancyListItem {
  presentation_key: string;
  vacancy_id: number;
  source: string;
  external_id: string;
  company: string;
  title: string;
  salary_text: string | null;
  location: string | null;
  published_at: string | null;
  first_seen_at: string;
  url: string | null;
  priority: VacancyPriority | null;
  final_score: number | null;
  track: string | null;
  summary: string;
  profile_ids: string[];
  run_id: string | null;
  member_count: number;
  application_id: number | null;
  application_status: ApplicationStatus | null;
  application_updated_at: string | null;
  vacancy_status: VacancyStatus;
  user_priority: VacancyUserPriority | null;
  user_comment: string | null;
  processing_state: VacancyProcessingState | null;
  preliminary_outcome: VacancyPreliminaryOutcome | null;
}

export interface VacancyListResponse {
  items: VacancyListItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface VacancyFilters {
  date_from?: string;
  date_to?: string;
  priority?: VacancyPriority[];
  track?: string;
  profile_id?: string;
  run_id?: string;
  search?: string;
  application_status?: VacancyApplicationStatusFilter;
  vacancy_status?: VacancyStatusFilter;
  user_priority?: VacancyUserPriorityFilter;
  processing?: VacancyProcessingFilter;
  limit: number;
  offset: number;
  sort: VacancyListSort;
  sort_direction: SortDirection;
}

export interface VacancyCanonicalMember {
  source: string;
  external_id: string;
  url: string | null;
  title: string;
  company: string;
  location: string | null;
  representative: boolean;
}

export interface Application {
  id: number;
  vacancy_id: number;
  status: ApplicationStatus;
  applied_at: string | null;
  application_text: string | null;
  employer_response: string | null;
  response_received_at: string | null;
  interview_at: string | null;
  offer_at: string | null;
  notes: string | null;
  platform: string | null;
  created_at: string;
  updated_at: string;
}

export interface ApplicationCreateRequest {
  status: ApplicationStatus;
  applied_at?: string | null;
  application_text?: string | null;
  employer_response?: string | null;
  response_received_at?: string | null;
  interview_at?: string | null;
  offer_at?: string | null;
  notes?: string | null;
  platform?: string | null;
}

export type ApplicationPatchRequest = Partial<ApplicationCreateRequest>;

export interface ApplicationListItem extends Application {
  presentation_key: string;
  company: string;
  title: string;
  vacancy_url: string | null;
}

export interface ApplicationWriteResponse {
  application: Application;
}

export interface ApplicationListResponse {
  items: ApplicationListItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface ApplicationFilters {
  status?: ApplicationStatus;
  date_from?: string;
  date_to?: string;
  platform?: string;
  search?: string;
  limit: number;
  offset: number;
}

export interface VacancyApplicationDetail {
  application: Application;
  source: string;
  external_id: string;
  url: string | null;
  representative_member: boolean;
  current: boolean;
}

export interface VacancyAnalysisDetail {
  priority: VacancyPriority | null;
  final_score: number | null;
  relevance: number | null;
  track: string | null;
  summary: string | null;
  reason: string | null;
  risks: string[] | null;
  hard_blockers: string[] | null;
}

export interface VacancyPreliminaryOutcome {
  outcome: PreliminaryOutcome;
  outcome_source: "policy" | "ai" | "fallback" | "error";
  processing_state: VacancyProcessingState;
  score: number | null;
  confidence: number | null;
  summary: string | null;
  provider: string | null;
  model: string | null;
  prompt_version: string | null;
  error_code: string | null;
  run_id: string;
  updated_at: string;
}

export interface VacancyDetail {
  presentation_key: string;
  vacancy_id: number;
  source: string;
  external_id: string;
  member_count: number;
  company: string;
  title: string;
  salary_text: string | null;
  location: string | null;
  work_format: string | null;
  working_hours: string | null;
  experience_min_years: number | null;
  experience_max_years: number | null;
  published_at: string | null;
  first_seen_at: string;
  last_seen_at: string;
  url: string | null;
  description: string | null;
  skills: string[];
  analysis: VacancyAnalysisDetail | null;
  preliminary_outcome: VacancyPreliminaryOutcome | null;
  profile_ids: string[];
  query_variant_ids: string[];
  provenance_tracks: string[];
  run_ids: string[];
  members: VacancyCanonicalMember[];
  applications: VacancyApplicationDetail[];
  user_state: VacancyUserState;
}

export interface VacancyUserState {
  id: number | null;
  presentation_key: string;
  user_priority: VacancyUserPriority | null;
  comment: string | null;
  vacancy_status: VacancyStatus;
  created_at: string | null;
  updated_at: string | null;
}

export interface VacancyUserStatePatchRequest {
  user_priority?: VacancyUserPriority | null;
  comment?: string | null;
  vacancy_status?: VacancyStatus;
}

export interface VacancyUserStateWriteResponse {
  user_state: VacancyUserState;
}

export interface ManualVacancyCreateRequest { company: string; title: string; description: string; origin: ManualVacancyOrigin; url?: string | null; salary_text?: string | null; work_format?: string | null; location?: string | null; stack?: string | null; user_priority?: VacancyUserPriority | null; vacancy_status?: VacancyStatus; user_comment?: string | null; }
export interface ManualVacancyCreateResponse { created: boolean; presentation_key: string | null; vacancy_id: number | null; user_state: VacancyUserState | null; duplicate: { presentation_key: string; vacancy_id: number } | null; }

export interface VacancyStatistics {
  period: StatisticsPeriod;
  date_from: string | null;
  date_to: string | null;
  found: number;
  reviewed: number;
  applications: number;
  responses: number;
  interviews: number;
  rejections: number;
  active_processes: number;
  offers: number;
  legacy_without_date: number;
}

export interface StatisticsRequest {
  period: StatisticsPeriod;
  date_from?: string;
  date_to?: string;
}

export type ExportEntity = "vacancies" | "applications";
export type ExportFormat = "xlsx" | "csv";
export type ExportPeriod = "all" | "7d" | "30d" | "custom";
export type ExportColumnCategory = "business" | "ai" | "technical";

export interface ExportColumnDefinition {
  key: string;
  label: string;
  default_enabled: boolean;
  category: ExportColumnCategory;
  type: string;
}

export interface ExportSchema {
  vacancies: ExportColumnDefinition[];
  applications: ExportColumnDefinition[];
  formats: ExportFormat[];
  periods: ExportPeriod[];
}

export interface ExportRequest {
  format: ExportFormat;
  period: ExportPeriod;
  date_from?: string;
  date_to?: string;
  columns: string[];
}

export interface ExportDownload {
  blob: Blob;
  filename: string | null;
}

export type DiagnosticStatus = "PASS" | "WARN" | "FAIL" | "unavailable";
export interface DiagnosticHealthItem { status: DiagnosticStatus; summary: string; }
export interface DiagnosticRecentRun { run_id: string; started_at: string; completed_at: string | null; status: PipelineRunStatus; profile_ids: string[]; error_code: string | null; }
export interface DiagnosticFailureSample { vacancy_id: number; external_id: string; company: string; title: string; url: string | null; state: string; error_code: string; error_summary: string | null; }
export interface DiagnosticFailureGroup { count: number; summary: string | null; samples: DiagnosticFailureSample[]; }
export interface DiagnosticRunResponse { run: PipelineRunDetail; preliminary: { availability: string; processed_count: number; outcome_counts: Record<string, number>; enrichment_selected_count: number; }; enrichment: { availability: string; analysis_count: number; enriched_count: number; processing_failed_count: number; }; backlog: { availability: string; total: number; state_counts: Record<string, number>; }; failures: Record<string, DiagnosticFailureGroup>; full_fetch_transport: { value: string; source: string }; pagination: { availability: string }; }
export interface DiagnosticConfig { collection: Record<string, string | number | null>; preliminary: Record<string, number>; enrichment: Record<string, number>; recovery: Record<string, number>; secrets: Record<string, boolean>; }
export interface HHDiagnostic { classification: string; transports: Array<{ transport: string; status: number | null; final_url: string | null; captcha_detected: boolean; login_detected: boolean; vpn_detected: boolean; challenge_detected: boolean; }>; }
