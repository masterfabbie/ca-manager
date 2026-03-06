import json
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from sqlalchemy.orm import Session

from cryptography.hazmat.primitives import serialization as _serialization

from ..crypto import (
    cert_to_pem,
    generate_csr,
    key_to_pem,
    load_ca_key_from_file,
    load_csr,
    pem_to_key,
    sign_csr,
)
from ..dependencies import get_db
from ..models import Certificate, CsrRecord, RootCA
from ..schemas import CSRGenerate, CSRImportCert, CSRRead, CSRSign
from cryptography import x509

router = APIRouter(prefix="/api/csrs", tags=["CSRs"])


def _extract_sans_from_csr(csr: x509.CertificateSigningRequest) -> list[dict]:
    try:
        san_ext = csr.extensions.get_extension_for_class(x509.SubjectAlternativeName)
        sans = []
        for name in san_ext.value:
            if isinstance(name, x509.DNSName):
                sans.append({"type": "dns", "value": name.value})
            elif isinstance(name, x509.IPAddress):
                sans.append({"type": "ip", "value": str(name.value)})
        return sans
    except x509.ExtensionNotFound:
        return []


def _get_cn_from_csr(csr: x509.CertificateSigningRequest) -> str:
    attrs = csr.subject.get_attributes_for_oid(x509.oid.NameOID.COMMON_NAME)
    return attrs[0].value if attrs else ""


# ── List ─────────────────────────────────────────────────────────────────────

@router.get("/", response_model=list[CSRRead])
def list_csrs(
    signed: Optional[bool] = None,
    db: Session = Depends(get_db),
):
    q = db.query(CsrRecord)
    if signed is True:
        q = q.filter(CsrRecord.signed_cert_id.isnot(None))
    elif signed is False:
        q = q.filter(CsrRecord.signed_cert_id.is_(None))
    return q.order_by(CsrRecord.created_at.desc()).all()


# ── Upload external CSR ───────────────────────────────────────────────────────

@router.post("/", response_model=CSRRead, status_code=201)
async def upload_csr(
    file: Optional[UploadFile] = File(None),
    pem: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    if file:
        raw = await file.read()
        filename = file.filename or "upload.csr"
    elif pem:
        raw = pem.encode()
        filename = "pasted.csr"
    else:
        raise HTTPException(status_code=422, detail="Provide either a file or pem field")

    try:
        csr = load_csr(raw)
    except Exception:
        raise HTTPException(status_code=422, detail="Invalid PEM CSR")

    record = CsrRecord(
        filename=filename,
        csr_pem=raw.decode(errors="replace"),
        common_name=_get_cn_from_csr(csr),
        sans=json.dumps(_extract_sans_from_csr(csr)),
        key_pem=None,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


# ── Generate CSR in-app ───────────────────────────────────────────────────────

@router.post("/generate", response_model=CSRRead, status_code=201)
def generate_csr_endpoint(
    payload: CSRGenerate,
    db: Session = Depends(get_db),
):
    sans_json = json.dumps([s.model_dump() for s in payload.sans])
    try:
        csr, key = generate_csr(payload.common_name, sans_json, payload.key_size)
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))

    safe_cn = payload.common_name.replace(" ", "_").replace("*", "wildcard")
    record = CsrRecord(
        filename=f"{safe_cn}.csr",
        csr_pem=csr.public_bytes(_serialization.Encoding.PEM).decode(),
        common_name=payload.common_name,
        sans=sans_json,
        key_pem=key_to_pem(key).decode(),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


# ── Downloads ────────────────────────────────────────────────────────────────

@router.get("/{csr_id}/download/csr")
def download_csr_pem(csr_id: str, db: Session = Depends(get_db)):
    record = db.query(CsrRecord).filter(CsrRecord.id == csr_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="CSR not found")
    safe = record.filename.replace(" ", "_")
    return Response(
        content=record.csr_pem.encode(),
        media_type="application/x-pem-file",
        headers={"Content-Disposition": f'attachment; filename="{safe}"'},
    )


@router.get("/{csr_id}/download/key")
def download_csr_key(csr_id: str, db: Session = Depends(get_db)):
    record = db.query(CsrRecord).filter(CsrRecord.id == csr_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="CSR not found")
    if not record.key_pem:
        raise HTTPException(status_code=404, detail="No private key stored for this CSR")
    safe = record.filename.replace(".csr", ".key").replace(" ", "_")
    return Response(
        content=record.key_pem.encode(),
        media_type="application/x-pem-file",
        headers={"Content-Disposition": f'attachment; filename="{safe}"'},
    )


# ── Sign with internal CA ─────────────────────────────────────────────────────

@router.post("/{csr_id}/sign", response_model=CSRRead)
def sign_csr_endpoint(
    csr_id: str,
    payload: CSRSign,
    db: Session = Depends(get_db),
):
    record = db.query(CsrRecord).filter(CsrRecord.id == csr_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="CSR not found")
    if record.signed_cert_id:
        raise HTTPException(status_code=409, detail="CSR already signed")

    ca = db.query(RootCA).filter(RootCA.id == payload.ca_id).first()
    if not ca:
        raise HTTPException(status_code=404, detail="CA not found")
    if not ca.key_path:
        raise HTTPException(status_code=422, detail="CA has no private key — it was imported without one")

    ca_cert = x509.load_pem_x509_certificate(ca.cert_pem.encode())
    ca_key = load_ca_key_from_file(Path(ca.key_path))
    sans_json = json.dumps([s.model_dump() for s in payload.sans])
    csr = load_csr(record.csr_pem.encode())

    try:
        leaf_cert = sign_csr(csr, sans_json, payload.valid_days, ca_cert, ca_key)
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))

    # If we generated this CSR, we have the key; otherwise key is with the requester
    stored_key = record.key_pem or ""

    cert_record = Certificate(
        root_ca_id=ca.id,
        common_name=record.common_name or _get_cn_from_csr(csr),
        sans=sans_json,
        key_size=csr.public_key().key_size if hasattr(csr.public_key(), "key_size") else 0,
        not_before=leaf_cert.not_valid_before_utc,
        not_after=leaf_cert.not_valid_after_utc,
        cert_pem=cert_to_pem(leaf_cert).decode(),
        key_pem=stored_key,
    )
    db.add(cert_record)
    db.flush()

    record.signed_cert_id = cert_record.id
    db.commit()
    db.refresh(record)
    return record


# ── Import signed cert (answer from external CA) ──────────────────────────────

@router.post("/{csr_id}/import-cert", response_model=CSRRead)
def import_cert_for_csr(
    csr_id: str,
    payload: CSRImportCert,
    db: Session = Depends(get_db),
):
    record = db.query(CsrRecord).filter(CsrRecord.id == csr_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="CSR not found")
    if record.signed_cert_id:
        raise HTTPException(status_code=409, detail="CSR already has a signed certificate")

    ca = db.query(RootCA).filter(RootCA.id == payload.ca_id).first()
    if not ca:
        raise HTTPException(status_code=404, detail="CA not found")

    try:
        leaf_cert = x509.load_pem_x509_certificate(payload.cert_pem.encode())
    except Exception:
        raise HTTPException(status_code=422, detail="Invalid certificate PEM")

    stored_key = record.key_pem or ""

    cert_record = Certificate(
        root_ca_id=ca.id,
        common_name=record.common_name,
        sans=record.sans,
        key_size=leaf_cert.public_key().key_size if hasattr(leaf_cert.public_key(), "key_size") else 0,
        not_before=leaf_cert.not_valid_before_utc,
        not_after=leaf_cert.not_valid_after_utc,
        cert_pem=payload.cert_pem,
        key_pem=stored_key,
    )
    db.add(cert_record)
    db.flush()

    record.signed_cert_id = cert_record.id
    db.commit()
    db.refresh(record)
    return record


# ── Delete ────────────────────────────────────────────────────────────────────

@router.delete("/{csr_id}", status_code=204)
def delete_csr(csr_id: str, db: Session = Depends(get_db)):
    record = db.query(CsrRecord).filter(CsrRecord.id == csr_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="CSR not found")
    db.delete(record)
    db.commit()
