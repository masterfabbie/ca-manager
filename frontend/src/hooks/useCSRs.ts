import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CSRsAPI } from "../api/client";
import type { CSRGeneratePayload, CSRImportCertPayload, CSRSignPayload } from "../types";

export const useCSRs = (signed?: boolean) =>
  useQuery({ queryKey: ["csrs", signed], queryFn: () => CSRsAPI.list(signed) });

export const useUploadCSR = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (arg: File | string) =>
      typeof arg === "string" ? CSRsAPI.uploadPem(arg) : CSRsAPI.upload(arg),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["csrs"] }),
  });
};

export const useGenerateCSR = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (p: CSRGeneratePayload) => CSRsAPI.generate(p),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["csrs"] }),
  });
};

export const useSignCSR = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: CSRSignPayload }) =>
      CSRsAPI.sign(id, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["csrs"] });
      qc.invalidateQueries({ queryKey: ["certificates"] });
    },
  });
};

export const useImportCSRCert = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: CSRImportCertPayload }) =>
      CSRsAPI.importCert(id, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["csrs"] });
      qc.invalidateQueries({ queryKey: ["certificates"] });
    },
  });
};

export const useDeleteCSR = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => CSRsAPI.delete(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["csrs"] }),
  });
};
