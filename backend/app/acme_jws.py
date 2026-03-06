"""ACME JWS utilities per RFC 7515 / 7638 / 8555."""
from __future__ import annotations

import base64
import hashlib
import json

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature


def b64url_decode(s: str) -> bytes:
    pad = 4 - len(s) % 4
    if pad != 4:
        s += "=" * pad
    return base64.urlsafe_b64decode(s)


def b64url_encode(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def jwk_thumbprint(jwk: dict) -> str:
    """Compute RFC 7638 JWK thumbprint (base64url SHA-256 of canonical JSON)."""
    kty = jwk["kty"]
    if kty == "RSA":
        members = {"e": jwk["e"], "kty": "RSA", "n": jwk["n"]}
    elif kty == "EC":
        members = {"crv": jwk["crv"], "kty": "EC", "x": jwk["x"], "y": jwk["y"]}
    else:
        raise ValueError(f"Unsupported key type: {kty}")
    canonical = json.dumps(members, separators=(",", ":"), sort_keys=True)
    return b64url_encode(hashlib.sha256(canonical.encode()).digest())


def public_key_from_jwk(jwk: dict):
    """Load a cryptography public key object from a JWK dict."""
    kty = jwk["kty"]
    if kty == "RSA":
        n = int.from_bytes(b64url_decode(jwk["n"]), "big")
        e = int.from_bytes(b64url_decode(jwk["e"]), "big")
        return rsa.RSAPublicNumbers(e, n).public_key()
    elif kty == "EC":
        curves = {"P-256": ec.SECP256R1(), "P-384": ec.SECP384R1(), "P-521": ec.SECP521R1()}
        curve = curves.get(jwk["crv"])
        if not curve:
            raise ValueError(f"Unsupported curve: {jwk['crv']}")
        x = int.from_bytes(b64url_decode(jwk["x"]), "big")
        y = int.from_bytes(b64url_decode(jwk["y"]), "big")
        return ec.EllipticCurvePublicNumbers(x, y, curve).public_key()
    raise ValueError(f"Unsupported key type: {kty}")


def verify_jws(protected_b64: str, payload_b64: str, sig_b64: str, public_key, alg: str) -> None:
    """Verify a JWS signature. Raises ValueError on failure."""
    signing_input = f"{protected_b64}.{payload_b64}".encode()
    sig = b64url_decode(sig_b64)
    try:
        if alg.startswith("RS"):
            h = {"RS256": hashes.SHA256(), "RS384": hashes.SHA384(), "RS512": hashes.SHA512()}[alg]
            public_key.verify(sig, signing_input, padding.PKCS1v15(), h)
        elif alg.startswith("ES"):
            # JOSE ECDSA uses raw r||s; cryptography expects DER
            coord_size = {"ES256": 32, "ES384": 48, "ES512": 66}[alg]
            h = {"ES256": hashes.SHA256(), "ES384": hashes.SHA384(), "ES512": hashes.SHA512()}[alg]
            r = int.from_bytes(sig[:coord_size], "big")
            s = int.from_bytes(sig[coord_size:], "big")
            public_key.verify(encode_dss_signature(r, s), signing_input, ec.ECDSA(h))
        else:
            raise ValueError(f"Unsupported algorithm: {alg}")
    except (InvalidSignature, KeyError):
        raise ValueError("JWS signature verification failed")
