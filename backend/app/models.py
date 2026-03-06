import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from .database import Base


def _new_uuid() -> str:
    return str(uuid.uuid4())


def _now_utc():
    return datetime.now(timezone.utc)


class RootCA(Base):
    __tablename__ = "root_cas"

    id = Column(String(36), primary_key=True, default=_new_uuid)
    name = Column(String(255), nullable=False, unique=True)
    common_name = Column(String(255), nullable=False)
    key_size = Column(Integer, nullable=False)
    not_before = Column(DateTime(timezone=True), nullable=False)
    not_after = Column(DateTime(timezone=True), nullable=False)
    key_path = Column(String(512), nullable=False, default="")  # "" = imported, no key
    cert_pem = Column(Text, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    parent_ca_id = Column(String(36), ForeignKey("root_cas.id"), nullable=True)
    is_intermediate = Column(Boolean, nullable=False, default=False)

    parent = relationship("RootCA", remote_side="RootCA.id", foreign_keys=[parent_ca_id])
    certificates = relationship(
        "Certificate", back_populates="root_ca", cascade="all, delete-orphan"
    )

    @property
    def has_key(self) -> bool:
        return bool(self.key_path)


class Certificate(Base):
    __tablename__ = "certificates"

    id = Column(String(36), primary_key=True, default=_new_uuid)
    root_ca_id = Column(String(36), ForeignKey("root_cas.id"), nullable=False, index=True)
    common_name = Column(String(255), nullable=False)
    sans = Column(Text, nullable=False, default="[]")
    key_size = Column(Integer, nullable=False)
    not_before = Column(DateTime(timezone=True), nullable=False)
    not_after = Column(DateTime(timezone=True), nullable=False)
    cert_pem = Column(Text, nullable=False)
    key_pem       = Column(Text, nullable=False, default="")  # "" = no key (external CSR / import)
    alert_enabled = Column(Boolean, nullable=False, default=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    root_ca = relationship("RootCA", back_populates="certificates")

    @property
    def has_key(self) -> bool:
        return bool(self.key_pem)


# ── ACME ─────────────────────────────────────────────────────────────────────

class AcmeAccount(Base):
    __tablename__ = "acme_accounts"

    id = Column(String(36), primary_key=True, default=_new_uuid)
    status = Column(String(20), nullable=False, default="valid")
    contact = Column(Text, nullable=False, default="[]")
    jwk_thumbprint = Column(String(100), nullable=False, unique=True, index=True)
    public_key_jwk = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now_utc)

    orders = relationship("AcmeOrder", back_populates="account", cascade="all, delete-orphan")


class AcmeOrder(Base):
    __tablename__ = "acme_orders"

    id = Column(String(36), primary_key=True, default=_new_uuid)
    account_id = Column(String(36), ForeignKey("acme_accounts.id"), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="pending")
    identifiers = Column(Text, nullable=False)
    expires = Column(DateTime(timezone=True), nullable=False)
    certificate_id = Column(String(36), ForeignKey("certificates.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now_utc)

    account = relationship("AcmeAccount", back_populates="orders")
    authorizations = relationship(
        "AcmeAuthorization", back_populates="order", cascade="all, delete-orphan"
    )


class AcmeAuthorization(Base):
    __tablename__ = "acme_authorizations"

    id = Column(String(36), primary_key=True, default=_new_uuid)
    order_id = Column(String(36), ForeignKey("acme_orders.id"), nullable=False, index=True)
    identifier_type = Column(String(20), nullable=False)
    identifier_value = Column(String(255), nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    expires = Column(DateTime(timezone=True), nullable=False)

    order = relationship("AcmeOrder", back_populates="authorizations")
    challenges = relationship(
        "AcmeChallenge", back_populates="authz", cascade="all, delete-orphan"
    )


class AcmeChallenge(Base):
    __tablename__ = "acme_challenges"

    id = Column(String(36), primary_key=True, default=_new_uuid)
    authz_id = Column(String(36), ForeignKey("acme_authorizations.id"), nullable=False, index=True)
    type = Column(String(20), nullable=False)
    token = Column(String(100), nullable=False, unique=True)
    status = Column(String(20), nullable=False, default="pending")
    validated = Column(DateTime(timezone=True), nullable=True)
    error = Column(Text, nullable=True)

    authz = relationship("AcmeAuthorization", back_populates="challenges")


class AcmeNonce(Base):
    __tablename__ = "acme_nonces"

    value = Column(String(100), primary_key=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    used = Column(Boolean, nullable=False, default=False)


class Settings(Base):
    __tablename__ = "settings"

    id             = Column(Integer, primary_key=True, default=1)
    smtp_host      = Column(String(255), nullable=False, default="")
    smtp_port      = Column(Integer, nullable=False, default=587)
    smtp_username  = Column(String(255), nullable=False, default="")
    smtp_password  = Column(Text, nullable=False, default="")
    smtp_from      = Column(String(255), nullable=False, default="")
    alert_to       = Column(String(255), nullable=False, default="")
    use_tls        = Column(Boolean, nullable=False, default=True)
    alert_days     = Column(Integer, nullable=False, default=30)
    alerts_enabled = Column(Boolean, nullable=False, default=False)
    acme_enabled = Column(Boolean, nullable=False, default=False)
    acme_ca_id = Column(String(36), ForeignKey("root_cas.id"), nullable=True)
    acme_cert_days = Column(Integer, nullable=False, default=90)
    acme_skip_challenges = Column(Boolean, nullable=False, default=False)


class CsrRecord(Base):
    __tablename__ = "csr_records"

    id = Column(String(36), primary_key=True, default=_new_uuid)
    filename = Column(String(255), nullable=False)
    csr_pem = Column(Text, nullable=False)
    common_name = Column(String(255), nullable=False)
    sans = Column(Text, nullable=False, default="[]")
    key_pem = Column(Text, nullable=True)  # set when CSR was generated in-app
    signed_cert_id = Column(String(36), ForeignKey("certificates.id"), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    @property
    def has_key(self) -> bool:
        return bool(self.key_pem)
