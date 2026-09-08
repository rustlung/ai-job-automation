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
  limit: number;
  offset: number;
  sort: VacancyListSort;
  sort_direction: SortDirection;
}
