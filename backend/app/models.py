import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from .database import Base


def _new_uuid() -> str:
    return str(uuid.uuid4())


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
