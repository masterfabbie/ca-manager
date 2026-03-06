import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { SettingsAPI } from "../api/client";
import type { SettingsPayload } from "../types";

export function useSettings() {
  return useQuery({
    queryKey: ["settings"],
    queryFn: SettingsAPI.get,
  });
}

export function useUpdateSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (p: SettingsPayload) => SettingsAPI.update(p),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["settings"] }),
  });
}

export function useTestEmail() {
  return useMutation({
    mutationFn: () => SettingsAPI.testEmail(),
  });
}
