import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from ..crypto import (
    cert_to_pem,
    create_intermediate_ca,
    create_root_ca,
    load_ca_key_from_file,
    key_to_pem,
    pem_to_key,
)
from ..dependencies import get_data_dir, get_db
from ..models import RootCA
from ..schemas import CAImport, IntermediateCACreate, RootCACreate, RootCARead
from cryptography import x509

router = APIRouter(prefix="/api/cas", tags=["Root CAs"])


def _build_ca_chain(ca: RootCA, db: Session) -> list[x509.Certificate]:
    """Return [signing_ca_cert, ...parent_certs] — outermost root last."""
    chain = []
    current = ca
    while current:
        chain.append(x509.load_pem_x509_certificate(current.cert_pem.encode()))
        if current.parent_ca_id:
            current = db.query(RootCA).filter(RootCA.id == current.parent_ca_id).first()
        else:
            break
    return chain


@router.get("/", response_model=list[RootCARead])
def list_cas(db: Session = Depends(get_db)):
    return db.query(RootCA).order_by(RootCA.created_at.desc()).all()


@router.post("/", response_model=RootCARead, status_code=201)
def create_ca(
    payload: RootCACreate,
    db: Session = Depends(get_db),
    data_dir: Path = Depends(get_data_dir),
):
    if db.query(RootCA).filter(RootCA.name == payload.name).first():
        raise HTTPException(status_code=409, detail="A CA with this name already exists")

    ca_id = str(uuid.uuid4())
    key_path = data_dir / "ca_keys" / f"{ca_id}.key.pem"

    cert, _ = create_root_ca(
        common_name=payload.common_name,
        key_size=payload.key_size,
        valid_days=payload.valid_days,
        key_save_path=key_path,
    )

    ca = RootCA(
        id=ca_id,
        name=payload.name,
        common_name=payload.common_name,
        key_size=payload.key_size,
        not_before=cert.not_valid_before_utc,
        not_after=cert.not_valid_after_utc,
        key_path=str(key_path),
        cert_pem=cert_to_pem(cert).decode(),
        is_intermediate=False,
    )
    db.add(ca)
    db.commit()
    db.refresh(ca)
    return ca


@router.post("/intermediate", response_model=RootCARead, status_code=201)
def create_intermediate(
    payload: IntermediateCACreate,
    db: Session = Depends(get_db),
    data_dir: Path = Depends(get_data_dir),
):
    if db.query(RootCA).filter(RootCA.name == payload.name).first():
        raise HTTPException(status_code=409, detail="A CA with this name already exists")

    parent = db.query(RootCA).filter(RootCA.id == payload.parent_ca_id).first()
    if not parent:
        raise HTTPException(status_code=404, detail="Parent CA not found")
    if not parent.key_path:
        raise HTTPException(status_code=422, detail="Parent CA has no private key — cannot sign")

    parent_cert = x509.load_pem_x509_certificate(parent.cert_pem.encode())
    parent_key = load_ca_key_from_file(Path(parent.key_path))

    ca_id = str(uuid.uuid4())
    key_path = data_dir / "ca_keys" / f"{ca_id}.key.pem"

    cert, _ = create_intermediate_ca(
        common_name=payload.common_name,
        key_size=payload.key_size,
        valid_days=payload.valid_days,
        parent_ca_cert=parent_cert,
        parent_ca_key=parent_key,
        key_save_path=key_path,
    )

    ca = RootCA(
        id=ca_id,
        name=payload.name,
        common_name=payload.common_name,
        key_size=payload.key_size,
        not_before=cert.not_valid_before_utc,
        not_after=cert.not_valid_after_utc,
        key_path=str(key_path),
        cert_pem=cert_to_pem(cert).decode(),
        is_intermediate=True,
        parent_ca_id=payload.parent_ca_id,
    )
    db.add(ca)
    db.commit()
    db.refresh(ca)
    return ca


@router.post("/import", response_model=RootCARead, status_code=201)
def import_ca(
    payload: CAImport,
    db: Session = Depends(get_db),
    data_dir: Path = Depends(get_data_dir),
):
    """Import an existing CA certificate (root or intermediate), with optional private key."""
    if db.query(RootCA).filter(RootCA.name == payload.name).first():
        raise HTTPException(status_code=409, detail="A CA with this name already exists")

    try:
        cert = x509.load_pem_x509_certificate(payload.cert_pem.encode())
    except Exception:
        raise HTTPException(status_code=422, detail="Invalid certificate PEM")

    key_path_str = ""
    if payload.key_pem.strip():
        try:
            pem_to_key(payload.key_pem.encode())  # validate
        except Exception:
            raise HTTPException(status_code=422, detail="Invalid private key PEM")
        ca_id = str(uuid.uuid4())
        key_path = data_dir / "ca_keys" / f"{ca_id}.key.pem"
        key_path.write_bytes(payload.key_pem.encode())
        key_path.chmod(0o600)
        key_path_str = str(key_path)
    else:
        ca_id = str(uuid.uuid4())

    # Parse key size from cert
    pub = cert.public_key()
    key_size = pub.key_size if hasattr(pub, "key_size") else 0

    # Parse CN from cert subject
    cn_attrs = cert.subject.get_attributes_for_oid(x509.oid.NameOID.COMMON_NAME)
    common_name = cn_attrs[0].value if cn_attrs else payload.name

    ca = RootCA(
        id=ca_id,
        name=payload.name,
        common_name=common_name,
        key_size=key_size,
        not_before=cert.not_valid_before_utc,
        not_after=cert.not_valid_after_utc,
        key_path=key_path_str,
        cert_pem=payload.cert_pem,
        is_intermediate=payload.is_intermediate,
        parent_ca_id=payload.parent_ca_id,
    )
    db.add(ca)
    db.commit()
    db.refresh(ca)
    return ca


@router.delete("/{ca_id}", status_code=204)
def delete_ca(
    ca_id: str,
    db: Session = Depends(get_db),
):
    ca = db.query(RootCA).filter(RootCA.id == ca_id).first()
    if not ca:
        raise HTTPException(status_code=404, detail="CA not found")

    key_path = Path(ca.key_path) if ca.key_path else None
    db.delete(ca)
    db.commit()

    if key_path and key_path.exists():
        key_path.unlink()


@router.get("/{ca_id}/download/cert")
def download_ca_cert(
    ca_id: str,
    db: Session = Depends(get_db),
):
    ca = db.query(RootCA).filter(RootCA.id == ca_id).first()
    if not ca:
        raise HTTPException(status_code=404, detail="CA not found")

    safe_name = ca.name.replace(" ", "_")
    return Response(
        content=ca.cert_pem.encode(),
        media_type="application/x-pem-file",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}-ca.crt"'},
    )
