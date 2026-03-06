"""
All cryptographic operations using the `cryptography` library.
No subprocess calls; pure Python.
"""
from __future__ import annotations

import io
import ipaddress
import json
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey
from cryptography.hazmat.primitives.serialization.pkcs12 import (
    serialize_key_and_certificates,
)
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID


def generate_rsa_key(key_size: int) -> RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=key_size)


def key_to_pem(key: RSAPrivateKey) -> bytes:
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )


def pem_to_key(pem: bytes) -> RSAPrivateKey:
    return serialization.load_pem_private_key(pem, password=None)


def cert_to_pem(cert: x509.Certificate) -> bytes:
    return cert.public_bytes(serialization.Encoding.PEM)


def create_root_ca(
    common_name: str,
    key_size: int,
    valid_days: int,
    key_save_path: Path,
) -> tuple[x509.Certificate, RSAPrivateKey]:
    """Generate a self-signed Root CA and persist the key to disk."""
    key = generate_rsa_key(key_size)
    now = datetime.now(timezone.utc)
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, common_name),
    ])

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + timedelta(days=valid_days))
        .add_extension(
            x509.BasicConstraints(ca=True, path_length=None), critical=True
        )
        .add_extension(
            x509.SubjectKeyIdentifier.from_public_key(key.public_key()),
            critical=False,
        )
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                key_cert_sign=True,
                crl_sign=True,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .sign(key, hashes.SHA256())
    )

    key_save_path.write_bytes(key_to_pem(key))
    key_save_path.chmod(0o600)
    return cert, key


def create_intermediate_ca(
    common_name: str,
    key_size: int,
    valid_days: int,
    parent_ca_cert: x509.Certificate,
    parent_ca_key: RSAPrivateKey,
    key_save_path: Path,
) -> tuple[x509.Certificate, RSAPrivateKey]:
    """Generate an intermediate CA signed by a parent CA."""
    key = generate_rsa_key(key_size)
    now = datetime.now(timezone.utc)
    subject = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, common_name),
    ])

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(parent_ca_cert.subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + timedelta(days=valid_days))
        .add_extension(
            x509.BasicConstraints(ca=True, path_length=0), critical=True
        )
        .add_extension(
            x509.SubjectKeyIdentifier.from_public_key(key.public_key()),
            critical=False,
        )
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(parent_ca_cert.public_key()),
            critical=False,
        )
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                key_cert_sign=True,
                crl_sign=True,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .sign(parent_ca_key, hashes.SHA256())
    )

    key_save_path.write_bytes(key_to_pem(key))
    key_save_path.chmod(0o600)
    return cert, key


def _build_san_extension(
    sans: list[dict],
) -> Optional[x509.SubjectAlternativeName]:
    names: list[x509.GeneralName] = []
    for san in sans:
        if san["type"] == "dns":
            names.append(x509.DNSName(san["value"]))
        elif san["type"] == "ip":
            names.append(x509.IPAddress(ipaddress.ip_address(san["value"])))
    return x509.SubjectAlternativeName(names) if names else None


def issue_certificate(
    common_name: str,
    sans_json: str,
    key_size: int,
    valid_days: int,
    ca_cert: x509.Certificate,
    ca_key: RSAPrivateKey,
) -> tuple[x509.Certificate, RSAPrivateKey]:
    """Issue a leaf certificate signed by the given CA."""
    sans: list[dict] = json.loads(sans_json)
    leaf_key = generate_rsa_key(key_size)
    now = datetime.now(timezone.utc)

    subject = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, common_name),
    ])

    builder = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(ca_cert.subject)
        .public_key(leaf_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + timedelta(days=valid_days))
        .add_extension(
            x509.BasicConstraints(ca=False, path_length=None), critical=True
        )
        .add_extension(
            x509.SubjectKeyIdentifier.from_public_key(leaf_key.public_key()),
            critical=False,
        )
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_cert.public_key()),
            critical=False,
        )
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                key_encipherment=True,
                content_commitment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(
            x509.ExtendedKeyUsage([
                ExtendedKeyUsageOID.SERVER_AUTH,
                ExtendedKeyUsageOID.CLIENT_AUTH,
            ]),
            critical=False,
        )
    )

    san_ext = _build_san_extension(sans)
    if san_ext:
        builder = builder.add_extension(san_ext, critical=False)

    leaf_cert = builder.sign(ca_key, hashes.SHA256())
    return leaf_cert, leaf_key


def generate_csr(
    common_name: str,
    sans_json: str,
    key_size: int,
) -> tuple[x509.CertificateSigningRequest, RSAPrivateKey]:
    """Generate a private key and a CSR. Key is returned for caller to persist."""
    sans: list[dict] = json.loads(sans_json)
    key = generate_rsa_key(key_size)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])

    builder = x509.CertificateSigningRequestBuilder().subject_name(subject)

    san_ext = _build_san_extension(sans)
    if san_ext:
        builder = builder.add_extension(san_ext, critical=False)

    csr = builder.sign(key, hashes.SHA256())
    return csr, key


def load_csr(pem: bytes) -> x509.CertificateSigningRequest:
    return x509.load_pem_x509_csr(pem)


def sign_csr(
    csr: x509.CertificateSigningRequest,
    sans_json: str,
    valid_days: int,
    ca_cert: x509.Certificate,
    ca_key: RSAPrivateKey,
) -> x509.Certificate:
    """Sign a CSR using the given CA. SANs from sans_json override those in the CSR."""
    sans: list[dict] = json.loads(sans_json)
    now = datetime.now(timezone.utc)

    builder = (
        x509.CertificateBuilder()
        .subject_name(csr.subject)
        .issuer_name(ca_cert.subject)
        .public_key(csr.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + timedelta(days=valid_days))
        .add_extension(
            x509.BasicConstraints(ca=False, path_length=None), critical=True
        )
        .add_extension(
            x509.SubjectKeyIdentifier.from_public_key(csr.public_key()),
            critical=False,
        )
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_cert.public_key()),
            critical=False,
        )
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                key_encipherment=True,
                content_commitment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(
            x509.ExtendedKeyUsage([
                ExtendedKeyUsageOID.SERVER_AUTH,
                ExtendedKeyUsageOID.CLIENT_AUTH,
            ]),
            critical=False,
        )
    )

    san_ext = _build_san_extension(sans)
    if san_ext:
        builder = builder.add_extension(san_ext, critical=False)

    return builder.sign(ca_key, hashes.SHA256())


def export_p12(
    leaf_cert: x509.Certificate,
    leaf_key: RSAPrivateKey,
    ca_chain: list[x509.Certificate],
    friendly_name: str,
    password: Optional[str] = None,
) -> bytes:
    p12_password: Optional[bytes] = password.encode() if password else None
    encryption = (
        serialization.BestAvailableEncryption(p12_password)
        if p12_password
        else serialization.NoEncryption()
    )
    return serialize_key_and_certificates(
        name=friendly_name.encode(),
        key=leaf_key,
        cert=leaf_cert,
        cas=ca_chain,
        encryption_algorithm=encryption,
    )


def export_pem_bundle(
    leaf_cert: x509.Certificate,
    leaf_key: RSAPrivateKey,
    ca_chain: list[x509.Certificate],
) -> bytes:
    """Concatenate: leaf cert + private key + CA certs (signing CA first)."""
    parts = cert_to_pem(leaf_cert) + key_to_pem(leaf_key)
    for ca_cert in ca_chain:
        parts += cert_to_pem(ca_cert)
    return parts


def export_zip_pem_bundles(
    items: list[tuple[x509.Certificate, RSAPrivateKey, list[x509.Certificate], str]],
) -> bytes:
    """Build a ZIP in memory containing PEM bundles for each item."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for leaf_cert, leaf_key, ca_chain, filename in items:
            bundle = export_pem_bundle(leaf_cert, leaf_key, ca_chain)
            zf.writestr(filename, bundle)
    return buf.getvalue()


def load_ca_key_from_file(key_path: Path) -> RSAPrivateKey:
    return pem_to_key(key_path.read_bytes())
