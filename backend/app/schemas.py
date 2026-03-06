import json
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class SANEntry(BaseModel):
    type: Literal["dns", "ip"]
    value: str


# ── Root CA ─────────────────────────────────────────────────────────────────

class RootCACreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    common_name: str = Field(..., min_length=1, max_length=255)
    valid_days: int = Field(..., ge=1, le=36500)
    key_size: Literal[2048, 4096] = 4096


class IntermediateCACreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    common_name: str = Field(..., min_length=1, max_length=255)
    parent_ca_id: str
    valid_days: int = Field(..., ge=1, le=3650)
    key_size: Literal[2048, 4096] = 4096


class CAImport(BaseModel):
    """Import an existing CA certificate (root or intermediate)."""
    name: str = Field(..., min_length=1, max_length=255)
    cert_pem: str
    key_pem: str = ""          # optional — without it the CA is read-only
    is_intermediate: bool = False
    parent_ca_id: str | None = None


class RootCARead(BaseModel):
    id: str
    name: str
    common_name: str
    key_size: int
    not_before: datetime
    not_after: datetime
    created_at: datetime
    parent_ca_id: str | None = None
    is_intermediate: bool = False
    has_key: bool = True

    model_config = {"from_attributes": True}


# ── Certificate ──────────────────────────────────────────────────────────────

class CertificateCreate(BaseModel):
    root_ca_id: str
    common_name: str = Field(..., min_length=1, max_length=255)
    sans: list[SANEntry] = Field(default_factory=list)
    valid_days: int = Field(..., ge=1, le=3650)
    key_size: Literal[2048, 4096] = 2048


class CertImport(BaseModel):
    """Import an existing leaf certificate."""
    root_ca_id: str
    cert_pem: str
    key_pem: str = ""   # optional — without it only cert-only download works


class CertificateRead(BaseModel):
    id: str
    root_ca_id: str
    common_name: str
    sans: list[SANEntry]
    key_size: int
    not_before: datetime
    not_after: datetime
    created_at: datetime
    has_key: bool = True
    alert_enabled: bool = False

    model_config = {"from_attributes": True}

    @field_validator("sans", mode="before")
    @classmethod
    def parse_sans(cls, v):
        if isinstance(v, str):
            return json.loads(v)
        return v


# ── CSR ─────────────────────────────────────────────────────────────────────

class CSRGenerate(BaseModel):
    common_name: str = Field(..., min_length=1, max_length=255)
    sans: list[SANEntry] = Field(default_factory=list)
    key_size: Literal[2048, 4096] = 2048


class CSRRead(BaseModel):
    id: str
    filename: str
    common_name: str
    sans: list[SANEntry]
    signed_cert_id: str | None = None
    created_at: datetime
    has_key: bool = False   # True when CSR was generated in-app (key stored server-side)

    model_config = {"from_attributes": True}

    @field_validator("sans", mode="before")
    @classmethod
    def parse_sans(cls, v):
        if isinstance(v, str):
            return json.loads(v)
        return v


class CSRSign(BaseModel):
    ca_id: str
    valid_days: int = Field(..., ge=1, le=3650)
    sans: list[SANEntry] = Field(default_factory=list)


class CSRImportCert(BaseModel):
    """Attach a signed cert to a previously generated CSR."""
    cert_pem: str
    ca_id: str   # which CA in our system signed it (for chain building)


# ── Settings ─────────────────────────────────────────────────────────────────

class SettingsRead(BaseModel):
    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_from: str
    alert_to: str
    use_tls: bool
    alert_days: int
    alerts_enabled: bool
    acme_enabled: bool
    acme_ca_id: str | None
    acme_cert_days: int
    acme_skip_challenges: bool

    model_config = {"from_attributes": True}


class SettingsUpdate(BaseModel):
    smtp_host: str = ""
    smtp_port: int = Field(587, ge=1, le=65535)
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    alert_to: str = ""
    use_tls: bool = True
    alert_days: int = Field(30, ge=1, le=365)
    alerts_enabled: bool = False
    acme_enabled: bool = False
    acme_ca_id: str | None = None
    acme_cert_days: int = Field(90, ge=1, le=3650)
    acme_skip_challenges: bool = False


class AlertToggle(BaseModel):
    alert_enabled: bool
