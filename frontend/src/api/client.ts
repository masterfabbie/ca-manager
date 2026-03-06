import axios from "axios";
import type {
  AcmeAccount,
  AppSettings,
  CAImportPayload,
  Certificate,
  CertImportPayload,
  CreateCAPayload,
  CreateCertPayload,
  CreateIntermediateCAPayload,
  CSRGeneratePayload,
  CSRImportCertPayload,
  CSRRecord,
  CSRSignPayload,
  RootCA,
  SettingsPayload,
} from "../types";

const api = axios.create({ baseURL: "/api" });

export const CAsAPI = {
  list: () => api.get<RootCA[]>("/cas/").then((r) => r.data),
  create: (p: CreateCAPayload) =>
    api.post<RootCA>("/cas/", p).then((r) => r.data),
  createIntermediate: (p: CreateIntermediateCAPayload) =>
    api.post<RootCA>("/cas/intermediate", p).then((r) => r.data),
  importCA: (p: CAImportPayload) =>
    api.post<RootCA>("/cas/import", p).then((r) => r.data),
  delete: (id: string) => api.delete(`/cas/${id}`),
  downloadCert: (id: string) =>
    window.open(`/api/cas/${id}/download/cert`, "_blank"),
};

export const CertsAPI = {
  list: (caId?: string | null) =>
    api
      .get<Certificate[]>("/certificates/", {
        params: caId ? { ca_id: caId } : {},
      })
      .then((r) => r.data),
  create: (p: CreateCertPayload) =>
    api.post<Certificate>("/certificates/", p).then((r) => r.data),
  importCert: (p: CertImportPayload) =>
    api.post<Certificate>("/certificates/import", p).then((r) => r.data),
  delete: (id: string) => api.delete(`/certificates/${id}`),
  setAlert: (id: string, alert_enabled: boolean) =>
    api.patch<Certificate>(`/certificates/${id}/alert`, { alert_enabled }).then((r) => r.data),
  downloadP12: (id: string, password?: string) => {
    const params = password
      ? `?password=${encodeURIComponent(password)}`
      : "";
    window.open(`/api/certificates/${id}/download/p12${params}`, "_blank");
  },
  downloadPEM: (id: string) =>
    window.open(`/api/certificates/${id}/download/pem`, "_blank"),
  downloadCert: (id: string) =>
    window.open(`/api/certificates/${id}/download/cert`, "_blank"),
  bulkDownload: (caId?: string | null) => {
    const params = caId ? `?ca_id=${encodeURIComponent(caId)}` : "";
    window.open(`/api/certificates/bulk-download${params}`, "_blank");
  },
};

export const SettingsAPI = {
  get: () => api.get<AppSettings>("/settings/").then((r) => r.data),
  update: (p: SettingsPayload) => api.put<AppSettings>("/settings/", p).then((r) => r.data),
  testEmail: () => api.post("/settings/test-email").then((r) => r.data),
};

export const AcmeAPI = {
  accounts: () => api.get<AcmeAccount[]>("/acme/accounts").then((r) => r.data),
  deleteAccount: (id: string) => api.delete(`/acme/accounts/${id}`),
};

export const CSRsAPI = {
  list: (signed?: boolean) =>
    api
      .get<CSRRecord[]>("/csrs/", {
        params: signed !== undefined ? { signed } : {},
      })
      .then((r) => r.data),
  upload: (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return api.post<CSRRecord>("/csrs/", fd).then((r) => r.data);
  },
  uploadPem: (pem: string) => {
    const fd = new FormData();
    fd.append("pem", pem);
    return api.post<CSRRecord>("/csrs/", fd).then((r) => r.data);
  },
  generate: (p: CSRGeneratePayload) =>
    api.post<CSRRecord>("/csrs/generate", p).then((r) => r.data),
  sign: (id: string, payload: CSRSignPayload) =>
    api.post<CSRRecord>(`/csrs/${id}/sign`, payload).then((r) => r.data),
  importCert: (id: string, payload: CSRImportCertPayload) =>
    api.post<CSRRecord>(`/csrs/${id}/import-cert`, payload).then((r) => r.data),
  downloadCSR: (id: string) =>
    window.open(`/api/csrs/${id}/download/csr`, "_blank"),
  downloadKey: (id: string) =>
    window.open(`/api/csrs/${id}/download/key`, "_blank"),
  delete: (id: string) => api.delete(`/csrs/${id}`),
};
