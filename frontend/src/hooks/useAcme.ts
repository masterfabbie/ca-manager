import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AcmeAPI } from "../api/client";

export function useAcmeAccounts() {
  return useQuery({ queryKey: ["acme-accounts"], queryFn: AcmeAPI.accounts });
}

export function useDeleteAcmeAccount() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => AcmeAPI.deleteAccount(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["acme-accounts"] }),
  });
}
