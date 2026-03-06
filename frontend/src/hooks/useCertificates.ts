import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CertsAPI } from "../api/client";
import type { CertImportPayload, CreateCertPayload } from "../types";

export const useCertificates = (caId?: string | null) =>
  useQuery({
    queryKey: ["certificates", caId ?? "all"],
    queryFn: () => CertsAPI.list(caId),
  });

export const useIssueCert = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (p: CreateCertPayload) => CertsAPI.create(p),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["certificates"] }),
  });
};

export const useImportCert = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (p: CertImportPayload) => CertsAPI.importCert(p),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["certificates"] }),
  });
};

export const useDeleteCert = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => CertsAPI.delete(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["certificates"] }),
  });
};
