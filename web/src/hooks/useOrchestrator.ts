import { useMutation, useQuery } from "@tanstack/react-query";

import { orchestratorApi } from "../api/orchestrator";
import { runPollingInterval } from "../lib/format";
import type { RunCreateRequest } from "../types/api";

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

export function useStartRun() {
  return useMutation({ mutationFn: (payload: RunCreateRequest) => orchestratorApi.startRun(payload) });
}
