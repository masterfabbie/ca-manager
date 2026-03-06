export interface RootCA {
  id: string;
  name: string;
  common_name: string;
  key_size: number;
  not_before: string;
  not_after: string;
  created_at: string;
  parent_ca_id: string | null;
  is_intermediate: boolean;
  has_key: boolean;
}

export interface SANEntry {
  type: "dns" | "ip";
  value: string;
}

export interface Certificate {
  id: string;
  root_ca_id: string;
  common_name: string;
  sans: SANEntry[];
  key_size: number;
  not_before: string;
  not_after: string;
  created_at: string;
  has_key: boolean;
  alert_enabled: boolean;
}

export interface AppSettings {
  smtp_host: string;
  smtp_port: number;
  smtp_username: string;
  smtp_from: string;
  alert_to: string;
  use_tls: boolean;
  alert_days: number;
  alerts_enabled: boolean;
  acme_enabled: boolean;
  acme_ca_id: string | null;
  acme_cert_days: number;
  acme_skip_challenges: boolean;
}

export interface SettingsPayload extends AppSettings {
  smtp_password: string;
}

export interface AcmeAccount {
  id: string;
  status: string;
  contact: string[];
  jwk_thumbprint: string;
  created_at: string;
  order_count: number;
}

export interface CSRRecord {
  id: string;
  filename: string;
  common_name: string;
  sans: SANEntry[];
  signed_cert_id: string | null;
  created_at: string;
  has_key: boolean;   // true = generated in-app (key stored server-side)
}

export interface CreateCAPayload {
  name: string;
  common_name: string;
  valid_days: number;
  key_size: 2048 | 4096;
}

export interface CreateIntermediateCAPayload {
  name: string;
  common_name: string;
  parent_ca_id: string;
  valid_days: number;
  key_size: 2048 | 4096;
}

export interface CAImportPayload {
  name: string;
  cert_pem: string;
  key_pem: string;
  is_intermediate: boolean;
  parent_ca_id: string | null;
}

export interface CreateCertPayload {
  root_ca_id: string;
  common_name: string;
  sans: SANEntry[];
  valid_days: number;
  key_size: 2048 | 4096;
}

export interface CertImportPayload {
  root_ca_id: string;
  cert_pem: string;
  key_pem: string;
}

export interface CSRSignPayload {
  ca_id: string;
  valid_days: number;
  sans: SANEntry[];
}

export interface CSRGeneratePayload {
  common_name: string;
  sans: SANEntry[];
  key_size: 2048 | 4096;
}

export interface CSRImportCertPayload {
  cert_pem: string;
  ca_id: string;
}
