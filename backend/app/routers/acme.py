"""
ACME protocol server (RFC 8555) + management API.

Protocol endpoints:  /acme/...
Management endpoints: /api/acme/...
"""
from __future__ import annotations

import json
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
from cryptography import x509
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from sqlalchemy.orm import Session

from ..acme_jws import b64url_decode, jwk_thumbprint, public_key_from_jwk, verify_jws
from ..crypto import cert_to_pem, load_ca_key_from_file, sign_csr
from ..database import SessionLocal
from ..dependencies import get_db
from ..models import (
    AcmeAccount,
    AcmeAuthorization,
    AcmeChallenge,
    AcmeNonce,
    AcmeOrder,
    Certificate,
    RootCA,
    Settings,
)

acme_router = APIRouter(prefix="/acme", tags=["ACME Protocol"])
acme_mgmt_router = APIRouter(prefix="/api/acme", tags=["ACME Management"])

_NONCE_TTL_MINUTES = 60


def _iso(dt: datetime) -> str:
    """Format a datetime as RFC 3339. SQLite drops timezone info on retrieval, so we re-attach UTC."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _acme_error(type_suffix: str, detail: str, status: int) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"type": f"urn:ietf:params:acme:error:{type_suffix}", "detail": detail, "status": status},
        media_type="application/problem+json",
    )


def _get_settings(db: Session) -> Settings:
    s = db.query(Settings).filter(Settings.id == 1).first()
    if not s:
        s = Settings(id=1)
        db.add(s)
        db.commit()
        db.refresh(s)
    return s


def _issue_nonce(db: Session) -> str:
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=_NONCE_TTL_MINUTES)
    db.query(AcmeNonce).filter(AcmeNonce.created_at < cutoff).delete()
    nonce = secrets.token_urlsafe(32)
    db.add(AcmeNonce(value=nonce, created_at=datetime.now(timezone.utc)))
    db.commit()
    return nonce


def _consume_nonce(nonce: str, db: Session) -> bool:
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=_NONCE_TTL_MINUTES)
    record = (
        db.query(AcmeNonce)
        .filter(AcmeNonce.value == nonce, AcmeNonce.used == False, AcmeNonce.created_at > cutoff)
        .first()
    )
    if not record:
        return False
    record.used = True
    db.commit()
    return True


def _external_base(request: Request) -> str:
    """Base URL that accounts for X-Forwarded-* headers from a reverse proxy."""
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("x-forwarded-host", request.headers.get("host", request.url.netloc))
    return f"{proto}://{host}"


def _external_url(request: Request) -> str:
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("x-forwarded-host", request.headers.get("host", request.url.netloc))
    return f"{proto}://{host}{request.url.path}"


def _order_url(base: str, order_id: str) -> str:
    return f"{base}/acme/order/{order_id}"


def _authz_url(base: str, authz_id: str) -> str:
    return f"{base}/acme/authz/{authz_id}"


def _challenge_url(base: str, ch_id: str) -> str:
    return f"{base}/acme/challenge/{ch_id}"


def _account_url(base: str, acct_id: str) -> str:
    return f"{base}/acme/account/{acct_id}"


def _cert_dl_url(base: str, cert_id: str) -> str:
    return f"{base}/acme/certificate/{cert_id}"


def _order_body(order: AcmeOrder, base: str) -> dict:
    body: dict = {
        "status": order.status,
        "expires": _iso(order.expires),
        "identifiers": json.loads(order.identifiers),
        "authorizations": [_authz_url(base, a.id) for a in order.authorizations],
        "finalize": f"{_order_url(base, order.id)}/finalize",
    }
    if order.certificate_id:
        body["certificate"] = _cert_dl_url(base, order.certificate_id)
    return body


def _authz_body(authz: AcmeAuthorization, base: str) -> dict:
    challenges = [
        {
            "type": ch.type,
            "url": _challenge_url(base, ch.id),
            "token": ch.token,
            "status": ch.status,
            **({"validated": _iso(ch.validated)} if ch.validated else {}),
            **({"error": json.loads(ch.error)} if ch.error else {}),
        }
        for ch in authz.challenges
    ]
    return {
        "identifier": {"type": authz.identifier_type, "value": authz.identifier_value},
        "status": authz.status,
        "expires": _iso(authz.expires),
        "challenges": challenges,
    }


async def _parse_jws_request(
    request: Request,
    db: Session,
    expected_url: str,
    require_existing_account: bool = True,
) -> tuple[dict, bytes, AcmeAccount | None]:
    """
    Parse and verify an ACME JWS request.
    Returns (protected_header, payload_bytes, account).
    For new-account flows, account may be None.
    Raises ValueError for protocol errors, LookupError if account not found.
    """
    try:
        body = await request.json()
    except Exception:
        raise ValueError("Invalid JSON body")

    for field in ("protected", "payload", "signature"):
        if field not in body:
            raise ValueError(f"Missing field: {field}")

    protected_b64: str = body["protected"]
    payload_b64: str = body["payload"]
    sig_b64: str = body["signature"]

    try:
        header = json.loads(b64url_decode(protected_b64))
    except Exception:
        raise ValueError("Invalid protected header")

    if header.get("url") != expected_url:
        raise ValueError(f"URL mismatch: expected {expected_url!r}, got {header.get('url')!r}")

    nonce = header.get("nonce", "")
    if not _consume_nonce(nonce, db):
        raise ValueError("Bad or expired nonce")

    has_jwk = "jwk" in header
    has_kid = "kid" in header

    if has_jwk and has_kid:
        raise ValueError("JWS must not contain both jwk and kid")

    if has_jwk:
        jwk = header["jwk"]
        try:
            pub = public_key_from_jwk(jwk)
        except Exception as exc:
            raise ValueError(f"Invalid JWK: {exc}")
        thumbprint = jwk_thumbprint(jwk)
        account = db.query(AcmeAccount).filter(AcmeAccount.jwk_thumbprint == thumbprint).first()
    elif has_kid:
        kid: str = header["kid"]
        account_id = kid.rstrip("/").rsplit("/", 1)[-1]
        account = db.query(AcmeAccount).filter(AcmeAccount.id == account_id).first()
        if not account:
            raise LookupError("Account not found")
        if account.status != "valid":
            raise LookupError("Account is deactivated")
        jwk = json.loads(account.public_key_jwk)
        try:
            pub = public_key_from_jwk(jwk)
        except Exception as exc:
            raise ValueError(f"Stored JWK invalid: {exc}")
    else:
        raise ValueError("JWS must contain either jwk or kid")

    if require_existing_account and not account:
        raise LookupError("Account not found")

    alg = header.get("alg", "")
    payload_bytes = b64url_decode(payload_b64) if payload_b64 else b""

    try:
        verify_jws(protected_b64, payload_b64, sig_b64, pub, alg)
    except ValueError:
        raise ValueError("Signature verification failed")

    return header, payload_bytes, account


# ── Directory ─────────────────────────────────────────────────────────────────

@acme_router.get("/directory")
def acme_directory(request: Request):
    base = _external_base(request)
    return {
        "newNonce": f"{base}/acme/new-nonce",
        "newAccount": f"{base}/acme/new-account",
        "newOrder": f"{base}/acme/new-order",
        "meta": {"externalAccountRequired": False},
    }


# ── Nonce ─────────────────────────────────────────────────────────────────────

@acme_router.api_route("/new-nonce", methods=["HEAD", "GET"])
def new_nonce(request: Request, db: Session = Depends(get_db)):
    nonce = _issue_nonce(db)
    status = 204 if request.method == "HEAD" else 200
    return Response(status_code=status, headers={"Replay-Nonce": nonce, "Cache-Control": "no-store"})


# ── Account ───────────────────────────────────────────────────────────────────

@acme_router.post("/new-account")
async def new_account(request: Request, db: Session = Depends(get_db)):
    settings = _get_settings(db)
    if not settings.acme_enabled:
        return _acme_error("serverInternal", "ACME is disabled", 503)

    base = _external_base(request)
    expected_url = _external_url(request)

    try:
        header, payload_bytes, account = await _parse_jws_request(
            request, db, expected_url, require_existing_account=False
        )
    except LookupError as exc:
        return _acme_error("accountDoesNotExist", str(exc), 400)
    except ValueError as exc:
        return _acme_error("malformed", str(exc), 400)

    try:
        payload = json.loads(payload_bytes) if payload_bytes else {}
    except Exception:
        return _acme_error("malformed", "Invalid payload JSON", 400)

    only_existing = payload.get("onlyReturnExisting", False)
    jwk = header["jwk"]

    if account:
        status_code = 200
    else:
        if only_existing:
            return _acme_error("accountDoesNotExist", "No account found for this key", 400)
        contact = payload.get("contact", [])
        account = AcmeAccount(
            jwk_thumbprint=jwk_thumbprint(jwk),
            public_key_jwk=json.dumps(jwk),
            contact=json.dumps(contact),
        )
        db.add(account)
        db.commit()
        db.refresh(account)
        status_code = 201

    acct_url = _account_url(base, account.id)
    nonce = _issue_nonce(db)
    return JSONResponse(
        status_code=status_code,
        content={
            "status": account.status,
            "contact": json.loads(account.contact),
            "orders": f"{acct_url}/orders",
        },
        headers={"Location": acct_url, "Replay-Nonce": nonce},
    )


@acme_router.post("/account/{account_id}")
async def get_or_update_account(account_id: str, request: Request, db: Session = Depends(get_db)):
    settings = _get_settings(db)
    if not settings.acme_enabled:
        return _acme_error("serverInternal", "ACME is disabled", 503)

    base = _external_base(request)
    expected_url = _external_url(request)

    try:
        _, payload_bytes, account = await _parse_jws_request(request, db, expected_url)
    except LookupError as exc:
        return _acme_error("accountDoesNotExist", str(exc), 400)
    except ValueError as exc:
        return _acme_error("malformed", str(exc), 400)

    # Allow contact update
    if payload_bytes:
        try:
            payload = json.loads(payload_bytes)
            if "contact" in payload:
                account.contact = json.dumps(payload["contact"])
                db.commit()
        except Exception:
            pass

    nonce = _issue_nonce(db)
    return JSONResponse(
        content={
            "status": account.status,
            "contact": json.loads(account.contact),
            "orders": f"{_account_url(base, account.id)}/orders",
        },
        headers={"Replay-Nonce": nonce},
    )


@acme_router.post("/account/{account_id}/orders")
async def list_account_orders(account_id: str, request: Request, db: Session = Depends(get_db)):
    settings = _get_settings(db)
    if not settings.acme_enabled:
        return _acme_error("serverInternal", "ACME is disabled", 503)

    base = _external_base(request)
    expected_url = _external_url(request)

    try:
        _, _, account = await _parse_jws_request(request, db, expected_url)
    except LookupError as exc:
        return _acme_error("accountDoesNotExist", str(exc), 400)
    except ValueError as exc:
        return _acme_error("malformed", str(exc), 400)

    order_urls = [_order_url(base, o.id) for o in account.orders]
    nonce = _issue_nonce(db)
    return JSONResponse(content={"orders": order_urls}, headers={"Replay-Nonce": nonce})


# ── Order ─────────────────────────────────────────────────────────────────────

@acme_router.post("/new-order")
async def new_order(request: Request, db: Session = Depends(get_db)):
    settings = _get_settings(db)
    if not settings.acme_enabled:
        return _acme_error("serverInternal", "ACME is disabled", 503)
    if not settings.acme_ca_id:
        return _acme_error("serverInternal", "No CA configured for ACME", 503)

    base = _external_base(request)
    expected_url = _external_url(request)

    try:
        _, payload_bytes, account = await _parse_jws_request(request, db, expected_url)
    except LookupError as exc:
        return _acme_error("accountDoesNotExist", str(exc), 400)
    except ValueError as exc:
        return _acme_error("malformed", str(exc), 400)

    try:
        payload = json.loads(payload_bytes)
        identifiers: list[dict] = payload["identifiers"]
    except Exception:
        return _acme_error("malformed", "Missing or invalid identifiers", 400)

    for ident in identifiers:
        if ident.get("type") != "dns":
            return _acme_error(
                "unsupportedIdentifier",
                f"Identifier type {ident.get('type')!r} is not supported; only 'dns' is accepted",
                400,
            )

    now = datetime.now(timezone.utc)
    expires = now + timedelta(days=7)

    order = AcmeOrder(
        account_id=account.id,
        status="pending",
        identifiers=json.dumps(identifiers),
        expires=expires,
    )
    db.add(order)
    db.flush()

    for ident in identifiers:
        authz = AcmeAuthorization(
            order_id=order.id,
            identifier_type=ident["type"],
            identifier_value=ident["value"],
            status="pending",
            expires=expires,
        )
        db.add(authz)
        db.flush()

        challenge = AcmeChallenge(
            authz_id=authz.id,
            type="http-01",
            token=secrets.token_urlsafe(32),
            status="pending",
        )
        db.add(challenge)

    db.commit()
    db.refresh(order)

    order_url = _order_url(base, order.id)
    nonce = _issue_nonce(db)
    return JSONResponse(
        status_code=201,
        content=_order_body(order, base),
        headers={"Location": order_url, "Replay-Nonce": nonce},
    )


@acme_router.post("/order/{order_id}")
async def get_order(order_id: str, request: Request, db: Session = Depends(get_db)):
    settings = _get_settings(db)
    if not settings.acme_enabled:
        return _acme_error("serverInternal", "ACME is disabled", 503)

    base = _external_base(request)
    expected_url = _external_url(request)

    try:
        _, _, account = await _parse_jws_request(request, db, expected_url)
    except LookupError as exc:
        return _acme_error("accountDoesNotExist", str(exc), 400)
    except ValueError as exc:
        return _acme_error("malformed", str(exc), 400)

    order = (
        db.query(AcmeOrder)
        .filter(AcmeOrder.id == order_id, AcmeOrder.account_id == account.id)
        .first()
    )
    if not order:
        return _acme_error("malformed", "Order not found", 404)

    nonce = _issue_nonce(db)
    return JSONResponse(content=_order_body(order, base), headers={"Replay-Nonce": nonce})


@acme_router.post("/order/{order_id}/finalize")
async def finalize_order(order_id: str, request: Request, db: Session = Depends(get_db)):
    settings = _get_settings(db)
    if not settings.acme_enabled:
        return _acme_error("serverInternal", "ACME is disabled", 503)
    if not settings.acme_ca_id:
        return _acme_error("serverInternal", "No CA configured for ACME", 503)

    base = _external_base(request)
    expected_url = _external_url(request)

    try:
        _, payload_bytes, account = await _parse_jws_request(request, db, expected_url)
    except LookupError as exc:
        return _acme_error("accountDoesNotExist", str(exc), 400)
    except ValueError as exc:
        return _acme_error("malformed", str(exc), 400)

    order = (
        db.query(AcmeOrder)
        .filter(AcmeOrder.id == order_id, AcmeOrder.account_id == account.id)
        .first()
    )
    if not order:
        return _acme_error("malformed", "Order not found", 404)
    if order.status != "ready":
        return _acme_error("orderNotReady", f"Order status is '{order.status}', expected 'ready'", 403)

    try:
        payload = json.loads(payload_bytes)
        csr_der = b64url_decode(payload["csr"])
    except Exception:
        return _acme_error("badCSR", "Missing or invalid CSR", 400)

    ca = db.query(RootCA).filter(RootCA.id == settings.acme_ca_id).first()
    if not ca or not ca.key_path:
        return _acme_error("serverInternal", "Configured CA is not available", 503)

    try:
        csr = x509.load_der_x509_csr(csr_der)
        ca_cert = x509.load_pem_x509_certificate(ca.cert_pem.encode())
        ca_key = load_ca_key_from_file(Path(ca.key_path))

        identifiers = json.loads(order.identifiers)
        sans_json = json.dumps([{"type": i["type"], "value": i["value"]} for i in identifiers])

        issued = sign_csr(csr, sans_json, settings.acme_cert_days, ca_cert, ca_key)
    except Exception as exc:
        return _acme_error("badCSR", f"Certificate issuance failed: {exc}", 400)

    cn_attrs = issued.subject.get_attributes_for_oid(x509.oid.NameOID.COMMON_NAME)
    common_name = cn_attrs[0].value if cn_attrs else json.loads(order.identifiers)[0]["value"]

    cert_record = Certificate(
        root_ca_id=settings.acme_ca_id,
        common_name=common_name,
        sans=sans_json,
        key_size=0,
        not_before=issued.not_valid_before_utc,
        not_after=issued.not_valid_after_utc,
        cert_pem=cert_to_pem(issued).decode(),
        key_pem="",
    )
    db.add(cert_record)
    db.flush()

    order.certificate_id = cert_record.id
    order.status = "valid"
    db.commit()
    db.refresh(order)

    nonce = _issue_nonce(db)
    return JSONResponse(content=_order_body(order, base), headers={"Replay-Nonce": nonce})


# ── Authorization ─────────────────────────────────────────────────────────────

@acme_router.post("/authz/{authz_id}")
async def get_authz(authz_id: str, request: Request, db: Session = Depends(get_db)):
    settings = _get_settings(db)
    if not settings.acme_enabled:
        return _acme_error("serverInternal", "ACME is disabled", 503)

    base = _external_base(request)
    expected_url = _external_url(request)

    try:
        _, _, account = await _parse_jws_request(request, db, expected_url)
    except LookupError as exc:
        return _acme_error("accountDoesNotExist", str(exc), 400)
    except ValueError as exc:
        return _acme_error("malformed", str(exc), 400)

    authz = (
        db.query(AcmeAuthorization)
        .join(AcmeOrder)
        .filter(AcmeAuthorization.id == authz_id, AcmeOrder.account_id == account.id)
        .first()
    )
    if not authz:
        return _acme_error("malformed", "Authorization not found", 404)

    nonce = _issue_nonce(db)
    return JSONResponse(content=_authz_body(authz, base), headers={"Replay-Nonce": nonce})


# ── Challenge ─────────────────────────────────────────────────────────────────

async def _verify_http01_challenge(
    challenge_id: str, domain: str, token: str, key_auth: str, skip: bool
) -> None:
    """Background task: verify http-01 challenge and update order/authz status."""
    db = SessionLocal()
    try:
        challenge = db.query(AcmeChallenge).filter(AcmeChallenge.id == challenge_id).first()
        if not challenge:
            return

        challenge.status = "processing"
        db.commit()

        if skip:
            success, error_detail = True, None
        else:
            success, error_detail = False, None
            try:
                url = f"http://{domain}/.well-known/acme-challenge/{token}"
                async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                    resp = await client.get(url)
                if resp.status_code == 200 and resp.text.strip() == key_auth:
                    success = True
                else:
                    error_detail = f"HTTP {resp.status_code}; expected key authorization in body"
            except Exception as exc:
                error_detail = str(exc)

        now = datetime.now(timezone.utc)
        authz_id = challenge.authz_id

        if success:
            challenge.status = "valid"
            challenge.validated = now
        else:
            challenge.status = "invalid"
            challenge.error = json.dumps({
                "type": "urn:ietf:params:acme:error:connection",
                "detail": error_detail or "Challenge verification failed",
            })
        db.commit()

        authz = db.query(AcmeAuthorization).filter(AcmeAuthorization.id == authz_id).first()
        if not authz:
            return

        authz.status = "valid" if success else "invalid"
        db.commit()

        if success:
            order = db.query(AcmeOrder).filter(AcmeOrder.id == authz.order_id).first()
            if order and order.status == "pending":
                all_authzs = (
                    db.query(AcmeAuthorization)
                    .filter(AcmeAuthorization.order_id == order.id)
                    .all()
                )
                if all(a.status == "valid" for a in all_authzs):
                    order.status = "ready"
                    db.commit()
    finally:
        db.close()


@acme_router.post("/challenge/{challenge_id}")
async def respond_to_challenge(
    challenge_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    settings = _get_settings(db)
    if not settings.acme_enabled:
        return _acme_error("serverInternal", "ACME is disabled", 503)

    base = _external_base(request)
    expected_url = _external_url(request)

    try:
        _, _, account = await _parse_jws_request(request, db, expected_url)
    except LookupError as exc:
        return _acme_error("accountDoesNotExist", str(exc), 400)
    except ValueError as exc:
        return _acme_error("malformed", str(exc), 400)

    challenge = (
        db.query(AcmeChallenge)
        .join(AcmeAuthorization)
        .join(AcmeOrder)
        .filter(AcmeChallenge.id == challenge_id, AcmeOrder.account_id == account.id)
        .first()
    )
    if not challenge:
        return _acme_error("malformed", "Challenge not found", 404)

    # Fetch authz now — needed for the "up" Link header required by RFC 8555 §7.5
    authz = db.query(AcmeAuthorization).filter(AcmeAuthorization.id == challenge.authz_id).first()
    if not authz:
        return _acme_error("malformed", "Authorization not found", 404)
    authz_link = f'<{_authz_url(base, authz.id)}>;rel="up"'

    if challenge.status != "pending":
        nonce = _issue_nonce(db)
        return JSONResponse(
            content={
                "type": challenge.type,
                "url": expected_url,
                "token": challenge.token,
                "status": challenge.status,
            },
            headers={"Replay-Nonce": nonce, "Link": authz_link},
        )

    account_jwk = json.loads(account.public_key_jwk)
    key_auth = f"{challenge.token}.{jwk_thumbprint(account_jwk)}"
    domain = authz.identifier_value

    background_tasks.add_task(
        _verify_http01_challenge,
        challenge.id,
        domain,
        challenge.token,
        key_auth,
        settings.acme_skip_challenges,
    )

    nonce = _issue_nonce(db)
    return JSONResponse(
        content={
            "type": challenge.type,
            "url": expected_url,
            "token": challenge.token,
            "status": "processing",
        },
        headers={"Replay-Nonce": nonce, "Link": authz_link},
    )


# ── Certificate download ───────────────────────────────────────────────────────

@acme_router.post("/certificate/{cert_id}")
async def download_certificate(cert_id: str, request: Request, db: Session = Depends(get_db)):
    settings = _get_settings(db)
    if not settings.acme_enabled:
        return _acme_error("serverInternal", "ACME is disabled", 503)

    expected_url = _external_url(request)

    try:
        _, _, account = await _parse_jws_request(request, db, expected_url)
    except LookupError as exc:
        return _acme_error("accountDoesNotExist", str(exc), 400)
    except ValueError as exc:
        return _acme_error("malformed", str(exc), 400)

    order = (
        db.query(AcmeOrder)
        .filter(AcmeOrder.certificate_id == cert_id, AcmeOrder.account_id == account.id)
        .first()
    )
    if not order:
        return _acme_error("unauthorized", "Certificate not found or not authorized", 403)

    cert_record = db.query(Certificate).filter(Certificate.id == cert_id).first()
    if not cert_record:
        return _acme_error("malformed", "Certificate record not found", 404)

    # Build full chain: leaf + signing CA + any parent CAs
    chain_pem = cert_record.cert_pem
    ca = db.query(RootCA).filter(RootCA.id == cert_record.root_ca_id).first()
    while ca:
        chain_pem += "\n" + ca.cert_pem
        if not ca.parent_ca_id:
            break
        ca = db.query(RootCA).filter(RootCA.id == ca.parent_ca_id).first()

    nonce = _issue_nonce(db)
    return Response(
        content=chain_pem.encode(),
        media_type="application/pem-certificate-chain",
        headers={"Replay-Nonce": nonce},
    )


# ── Management API ────────────────────────────────────────────────────────────

@acme_mgmt_router.get("/accounts")
def list_accounts(db: Session = Depends(get_db)):
    accounts = db.query(AcmeAccount).order_by(AcmeAccount.created_at.desc()).all()
    return [
        {
            "id": a.id,
            "status": a.status,
            "contact": json.loads(a.contact),
            "jwk_thumbprint": a.jwk_thumbprint,
            "created_at": _iso(a.created_at),
            "order_count": len(a.orders),
        }
        for a in accounts
    ]


@acme_mgmt_router.delete("/accounts/{account_id}", status_code=204)
def delete_account(account_id: str, db: Session = Depends(get_db)):
    account = db.query(AcmeAccount).filter(AcmeAccount.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    db.delete(account)
    db.commit()
