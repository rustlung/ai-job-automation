import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { orchestratorApi } from "../api/orchestrator";
import { runPollingInterval } from "../lib/format";
import type { ApplicationCreateRequest, ApplicationFilters, ApplicationPatchRequest, ManualVacancyCreateRequest, RunCreateRequest, StatisticsRequest, VacancyFilters, VacancyUserStatePatchRequest } from "../types/api";

export function useSystemHealth() {
  return useQuery({ queryKey: ["system-health"], queryFn: orchestratorApi.getSystemHealth, refetchInterval: 30_000 });
}

export function useSearchProfiles() {
  return useQuery({ queryKey: ["search-profiles"], queryFn: orchestratorApi.getSearchProfiles });
}

export function useRuns(limit = 20, offset = 0) {
  return useQuery({ queryKey: ["runs", limit, offset], queryFn: () => orchestratorApi.getRuns(limit, offset) });
}

export function useRun(runId: string) {
  return useQuery({
    queryKey: ["run", runId],
    queryFn: () => orchestratorApi.getRun(runId),
    enabled: Boolean(runId),
    refetchInterval: (query) => runPollingInterval(query.state.data?.status)
  });
}

export function useVacancies(filters: VacancyFilters) {
  return useQuery({
    queryKey: ["vacancies", filters],
    queryFn: () => orchestratorApi.getVacancies(filters)
  });
}

export function useStatistics(request: StatisticsRequest) {
  const customRangeIsComplete = request.period !== "custom" || Boolean(request.date_from && request.date_to && request.date_from <= request.date_to);
  return useQuery({
    queryKey: ["statistics", request],
    queryFn: () => orchestratorApi.getStatistics(request),
    enabled: customRangeIsComplete
  });
}

export function useVacancyDetail(presentationKey: string) {
  return useQuery({
    queryKey: ["vacancy", presentationKey],
    queryFn: () => orchestratorApi.getVacancyDetail(presentationKey),
    enabled: Boolean(presentationKey)
  });
}

export function useCreateManualVacancy() {
  const queryClient = useQueryClient();
  return useMutation({ mutationFn: (payload: ManualVacancyCreateRequest) => orchestratorApi.createManualVacancy(payload), onSuccess: () => queryClient.invalidateQueries({ queryKey: ["vacancies"] }) });
}

export function useRetryManualVacancyCrmSync() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: orchestratorApi.retryManualVacancyCrmSync,
    onSuccess: () => Promise.all([
      queryClient.invalidateQueries({ queryKey: ["vacancy"] }),
      queryClient.invalidateQueries({ queryKey: ["vacancies"] })
    ])
  });
}

export function useApplications(filters: ApplicationFilters) {
  return useQuery({ queryKey: ["applications", filters], queryFn: () => orchestratorApi.getApplications(filters) });
}

function useApplicationInvalidation() {
  const queryClient = useQueryClient();
  return () => Promise.all([
    queryClient.invalidateQueries({ queryKey: ["vacancy"] }),
    queryClient.invalidateQueries({ queryKey: ["vacancies"] }),
    queryClient.invalidateQueries({ queryKey: ["applications"] })
  ]);
}

export function useCreateApplication() {
  const invalidate = useApplicationInvalidation();
  return useMutation({
    mutationFn: ({ vacancyId, payload }: { vacancyId: number; payload: ApplicationCreateRequest }) => orchestratorApi.createApplication(vacancyId, payload),
    onSuccess: invalidate
  });
}

export function useUpdateApplication() {
  const invalidate = useApplicationInvalidation();
  return useMutation({
    mutationFn: ({ applicationId, payload }: { applicationId: number; payload: ApplicationPatchRequest }) => orchestratorApi.updateApplication(applicationId, payload),
    onSuccess: invalidate
  });
}

export function useRetryApplicationCrmSync() {
  const invalidate = useApplicationInvalidation();
  return useMutation({ mutationFn: orchestratorApi.retryApplicationCrmSync, onSuccess: invalidate });
}

export function useUpdateVacancyUserState() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ presentationKey, payload }: { presentationKey: string; payload: VacancyUserStatePatchRequest }) => orchestratorApi.updateVacancyUserState(presentationKey, payload),
    onSuccess: () => Promise.all([
      queryClient.invalidateQueries({ queryKey: ["vacancy"] }),
      queryClient.invalidateQueries({ queryKey: ["vacancies"] })
    ])
  });
}

export function useStartRun() {
  return useMutation({ mutationFn: (payload: RunCreateRequest) => orchestratorApi.startRun(payload) });
}
