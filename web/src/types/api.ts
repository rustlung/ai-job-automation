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
}

export interface SearchProfilesResponse {
  profiles: SearchProfile[];
}

export type PipelineRunStatus =
  | "accepted"
  | "running"
  | "completed"
  | "completed_with_errors"
  | "failed";

export type PipelineRunTriggerSource = "manual_n8n" | "web_ui" | "scheduled";

export interface PipelineRunOverrides {
  max_pages_override: number | null;
  max_filter_items_override: number | null;
  max_enrich_items_override: number | null;
}

export interface PipelineRunStatsSnapshot {
  legacy_crm_key_matches?: number;
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
export type ApplicationStatus = "submitted" | "response_received" | "screening" | "test_task" | "interview" | "offer" | "rejected" | "withdrawn";
export type VacancyApplicationStatusFilter = ApplicationStatus | "none";
export type VacancyListSort = "first_seen" | "final_score" | "priority";
export type SortDirection = "asc" | "desc";

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
  url: string;
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
  limit: number;
  offset: number;
  sort: VacancyListSort;
  sort_direction: SortDirection;
}

export interface VacancyCanonicalMember {
  source: string;
  external_id: string;
  url: string;
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
  vacancy_url: string;
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
  url: string;
  representative_member: boolean;
  current: boolean;
}

export interface VacancyAnalysisDetail {
  priority: VacancyPriority | null;
  final_score: number | null;
  relevance: number;
  track: string | null;
  summary: string;
  reason: string;
  risks: string[];
  hard_blockers: string[];
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
  url: string;
  description: string;
  skills: string[];
  analysis: VacancyAnalysisDetail;
  profile_ids: string[];
  query_variant_ids: string[];
  provenance_tracks: string[];
  run_ids: string[];
  members: VacancyCanonicalMember[];
  applications: VacancyApplicationDetail[];
}
