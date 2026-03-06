import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CAsAPI } from "../api/client";
import type { CAImportPayload, CreateCAPayload, CreateIntermediateCAPayload } from "../types";

export const useCAs = () =>
  useQuery({ queryKey: ["cas"], queryFn: CAsAPI.list });

export const useCreateCA = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (p: CreateCAPayload) => CAsAPI.create(p),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["cas"] }),
  });
};

export const useCreateIntermediateCA = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (p: CreateIntermediateCAPayload) => CAsAPI.createIntermediate(p),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["cas"] }),
  });
};

export const useImportCA = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (p: CAImportPayload) => CAsAPI.importCA(p),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["cas"] }),
  });
};

export const useDeleteCA = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => CAsAPI.delete(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["cas"] });
      qc.invalidateQueries({ queryKey: ["certificates"] });
    },
  });
};
