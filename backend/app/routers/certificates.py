import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from ..crypto import (
    cert_to_pem,
    export_p12,
    export_pem_bundle,
    export_zip_pem_bundles,
    issue_certificate,
    key_to_pem,
    load_ca_key_from_file,
    pem_to_key,
)
from ..dependencies import get_data_dir, get_db
from ..models import Certificate, RootCA
from ..schemas import AlertToggle, CertImport, CertificateCreate, CertificateRead
from .cas import _build_ca_chain
from cryptography import x509
from cryptography.hazmat.primitives import serialization

router = APIRouter(prefix="/api/certificates", tags=["Certificates"])


def _load_ca(ca_id: str, db: Session) -> tuple[RootCA, x509.Certificate]:
    ca = db.query(RootCA).filter(RootCA.id == ca_id).first()
    if not ca:
        raise HTTPException(status_code=404, detail="Root CA not found")
    ca_cert = x509.load_pem_x509_certificate(ca.cert_pem.encode())
    return ca, ca_cert


def _require_key(cert: Certificate) -> None:
    if not cert.key_pem:
        raise HTTPException(
            status_code=422,
            detail="This certificate has no stored private key — only cert-only download is available",
        )


@router.get("/", response_model=list[CertificateRead])
def list_certificates(
    ca_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(Certificate)
    if ca_id:
        q = q.filter(Certificate.root_ca_id == ca_id)
    return q.order_by(Certificate.created_at.desc()).all()


@router.post("/", response_model=CertificateRead, status_code=201)
def issue_cert(
    payload: CertificateCreate,
    db: Session = Depends(get_db),
    data_dir: Path = Depends(get_data_dir),
):
    ca, ca_cert = _load_ca(payload.root_ca_id, db)
    if not ca.key_path:
        raise HTTPException(status_code=422, detail="CA has no private key — it was imported without one")
    ca_key = load_ca_key_from_file(Path(ca.key_path))

    sans_json = json.dumps([s.model_dump() for s in payload.sans])

    try:
        leaf_cert, leaf_key = issue_certificate(
            common_name=payload.common_name,
            sans_json=sans_json,
            key_size=payload.key_size,
            valid_days=payload.valid_days,
            ca_cert=ca_cert,
            ca_key=ca_key,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    cert = Certificate(
        root_ca_id=payload.root_ca_id,
        common_name=payload.common_name,
        sans=sans_json,
        key_size=payload.key_size,
        not_before=leaf_cert.not_valid_before_utc,
        not_after=leaf_cert.not_valid_after_utc,
        cert_pem=cert_to_pem(leaf_cert).decode(),
        key_pem=key_to_pem(leaf_key).decode(),
    )
    db.add(cert)
    db.commit()
    db.refresh(cert)
    return cert


@router.post("/import", response_model=CertificateRead, status_code=201)
def import_cert(
    payload: CertImport,
    db: Session = Depends(get_db),
):
    """Import an existing leaf certificate (and optionally its private key)."""
    if payload.root_ca_id:
        ca = db.query(RootCA).filter(RootCA.id == payload.root_ca_id).first()
        if not ca:
            raise HTTPException(status_code=404, detail="CA not found")

    try:
        leaf_cert = x509.load_pem_x509_certificate(payload.cert_pem.encode())
    except Exception:
        raise HTTPException(status_code=422, detail="Invalid certificate PEM")

    if payload.key_pem.strip():
        try:
            pem_to_key(payload.key_pem.encode())  # validate
        except Exception:
            raise HTTPException(status_code=422, detail="Invalid private key PEM")

    pub = leaf_cert.public_key()
    key_size = pub.key_size if hasattr(pub, "key_size") else 0

    cn_attrs = leaf_cert.subject.get_attributes_for_oid(x509.oid.NameOID.COMMON_NAME)
    common_name = cn_attrs[0].value if cn_attrs else ""

    # Extract SANs from cert
    try:
        san_ext = leaf_cert.extensions.get_extension_for_class(x509.SubjectAlternativeName)
        sans = []
        for name in san_ext.value:
            if isinstance(name, x509.DNSName):
                sans.append({"type": "dns", "value": name.value})
            elif isinstance(name, x509.IPAddress):
                sans.append({"type": "ip", "value": str(name.value)})
    except x509.ExtensionNotFound:
        sans = []

    cert = Certificate(
        root_ca_id=payload.root_ca_id,
        common_name=common_name,
        sans=json.dumps(sans),
        key_size=key_size,
        not_before=leaf_cert.not_valid_before_utc,
        not_after=leaf_cert.not_valid_after_utc,
        cert_pem=payload.cert_pem,
        key_pem=payload.key_pem.strip(),
    )
    db.add(cert)
    db.commit()
    db.refresh(cert)
    return cert


@router.delete("/{cert_id}", status_code=204)
def delete_certificate(cert_id: str, db: Session = Depends(get_db)):
    cert = db.query(Certificate).filter(Certificate.id == cert_id).first()
    if not cert:
        raise HTTPException(status_code=404, detail="Certificate not found")
    db.delete(cert)
    db.commit()


@router.get("/{cert_id}/download/p12")
def download_p12(
    cert_id: str,
    password: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    cert = db.query(Certificate).filter(Certificate.id == cert_id).first()
    if not cert:
        raise HTTPException(status_code=404, detail="Certificate not found")
    _require_key(cert)

    chain = []
    if cert.root_ca_id:
        ca, _ = _load_ca(cert.root_ca_id, db)
        chain = _build_ca_chain(ca, db)
    leaf_cert = x509.load_pem_x509_certificate(cert.cert_pem.encode())
    leaf_key = serialization.load_pem_private_key(cert.key_pem.encode(), password=None)

    p12_bytes = export_p12(leaf_cert, leaf_key, chain, cert.common_name, password)
    safe_cn = cert.common_name.replace(" ", "_").replace("*", "wildcard")
    return Response(
        content=p12_bytes,
        media_type="application/x-pkcs12",
        headers={"Content-Disposition": f'attachment; filename="{safe_cn}.p12"'},
    )


@router.get("/{cert_id}/download/pem")
def download_pem_bundle(
    cert_id: str,
    db: Session = Depends(get_db),
):
    cert = db.query(Certificate).filter(Certificate.id == cert_id).first()
    if not cert:
        raise HTTPException(status_code=404, detail="Certificate not found")
    _require_key(cert)

    chain = []
    if cert.root_ca_id:
        ca, _ = _load_ca(cert.root_ca_id, db)
        chain = _build_ca_chain(ca, db)
    leaf_cert = x509.load_pem_x509_certificate(cert.cert_pem.encode())
    leaf_key = serialization.load_pem_private_key(cert.key_pem.encode(), password=None)

    bundle = export_pem_bundle(leaf_cert, leaf_key, chain)
    safe_cn = cert.common_name.replace(" ", "_").replace("*", "wildcard")
    return Response(
        content=bundle,
        media_type="application/x-pem-file",
        headers={"Content-Disposition": f'attachment; filename="{safe_cn}-bundle.pem"'},
    )


@router.get("/{cert_id}/download/cert")
def download_cert_only(cert_id: str, db: Session = Depends(get_db)):
    cert = db.query(Certificate).filter(Certificate.id == cert_id).first()
    if not cert:
        raise HTTPException(status_code=404, detail="Certificate not found")

    safe_cn = cert.common_name.replace(" ", "_").replace("*", "wildcard")
    return Response(
        content=cert.cert_pem.encode(),
        media_type="application/x-pem-file",
        headers={"Content-Disposition": f'attachment; filename="{safe_cn}.crt"'},
    )


@router.patch("/{cert_id}/alert", response_model=CertificateRead)
def set_alert(cert_id: str, payload: AlertToggle, db: Session = Depends(get_db)):
    cert = db.query(Certificate).filter(Certificate.id == cert_id).first()
    if not cert:
        raise HTTPException(status_code=404, detail="Certificate not found")
    cert.alert_enabled = payload.alert_enabled
    db.commit()
    db.refresh(cert)
    return cert


@router.post("/bulk-download")
def bulk_download(
    ca_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(Certificate)
    if ca_id:
        q = q.filter(Certificate.root_ca_id == ca_id)
    certs = q.order_by(Certificate.created_at.desc()).all()

    if not certs:
        raise HTTPException(status_code=404, detail="No certificates found")

    chain_cache: dict[str, list] = {}

    def get_chain(root_ca_id: Optional[str]):
        if not root_ca_id:
            return []
        if root_ca_id not in chain_cache:
            ca = db.query(RootCA).filter(RootCA.id == root_ca_id).first()
            chain_cache[root_ca_id] = _build_ca_chain(ca, db) if ca else []
        return chain_cache[root_ca_id]

    items = []
    for cert in certs:
        if not cert.key_pem:
            continue  # skip keyless certs in bulk download
        leaf_cert = x509.load_pem_x509_certificate(cert.cert_pem.encode())
        leaf_key = serialization.load_pem_private_key(cert.key_pem.encode(), password=None)
        chain = get_chain(cert.root_ca_id)
        safe_cn = cert.common_name.replace(" ", "_").replace("*", "wildcard")
        items.append((leaf_cert, leaf_key, chain, f"{safe_cn}-bundle.pem"))

    if not items:
        raise HTTPException(status_code=404, detail="No certificates with stored keys found")

    zip_bytes = export_zip_pem_bundles(items)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="certs-{ts}.zip"'},
    )
