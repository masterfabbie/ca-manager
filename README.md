# CA Manager

A self-hosted web-based Certificate Authority manager for homelabs. Run your own CA, issue certificates, and automate renewal with a built-in ACME server — all in a single Docker container.

## Features

- **Root & Intermediate CAs** — create, import, and chain CAs
- **Certificate issuance** — issue leaf certificates with SANs (DNS + IP), download as PEM bundle or PKCS#12
- **CSR workflow** — upload external CSRs or generate CSR + key in-browser, sign with any CA
- **ACME server** (RFC 8555) — fully compatible with certbot, acme.sh, Caddy, Traefik, and any RFC 8555 client
- **Expiry alerts** — scheduled email notifications via SMTP before certificates expire
- **Dark/light theme**
- **No authentication** — designed for trusted internal networks only

## Stack

| Layer | Tech |
|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy (SQLite) |
| Frontend | React 18 + TypeScript, Vite, TanStack Query |
| Crypto | Python `cryptography` library (no openssl subprocess) |
| Container | Single Docker image, multi-stage build |

## Quick Start

```bash
git clone https://github.com/masterfabbie/ca-manager.git
cd ca-manager
docker compose up --build
```

Open **http://localhost:8080**

Data is persisted in the `ca_data` Docker volume (`/data` in the container).

## Docker Compose

```yaml
services:
  ca-manager:
    build: .
    ports:
      - "8080:8000"
    volumes:
      - ca_data:/data

volumes:
  ca_data:
```

## ACME Server

The built-in ACME server lets clients automatically obtain and renew certificates from your CA.

### Setup

1. Go to the **ACME** page in the UI
2. Enable the ACME server
3. Select which CA should sign ACME-issued certificates
4. Set certificate validity (default: 90 days)
5. *(Optional)* Enable **Skip challenge verification** for internal hostnames the CA server can't reach over HTTP

### Directory URL

```
http://<your-ca-host>/acme/directory
```

### Client examples

**certbot**
```bash
certbot certonly --standalone \
  --server http://ca.internal/acme/directory \
  -d myservice.internal
```

**acme.sh**
```bash
acme.sh --issue -d myservice.internal \
  --server http://ca.internal/acme/directory \
  --standalone
```

**Caddy** (`Caddyfile`)
```
myservice.internal {
  tls {
    ca http://ca.internal/acme/directory
  }
}
```

**Traefik** (`traefik.yml`)
```yaml
certificatesResolvers:
  internal:
    acme:
      caServer: http://ca.internal/acme/directory
      httpChallenge:
        entryPoint: web
```

### Supported

- Challenge type: `http-01`
- Key types: RSA (RS256/384/512) and ECDSA (ES256/384/512)
- Reverse proxy aware (`X-Forwarded-Host`, `X-Forwarded-Proto`)

## Configuration

All settings are in the **Settings** page (SMTP/expiry alerts) and **ACME** page.

| Setting | Description |
|---|---|
| ACME enabled | Enable/disable the ACME server |
| Signing CA | Which CA issues ACME certificates |
| Certificate validity | Days, default 90 |
| Skip challenge verification | Auto-approve http-01 challenges (for unreachable internal hosts) |
| Expiry alerts | Email notification N days before expiry via SMTP |

## Certificate Downloads

| Format | Use case |
|---|---|
| `.crt` | Certificate only (trust store import) |
| `.pem` bundle | Cert + key + CA chain concatenated |
| `.p12` / PKCS#12 | Windows, Java, browser import |
| Bulk ZIP | All certificates for a CA as PEM bundles |

## Verify with OpenSSL

```bash
# Verify a certificate against its CA
openssl verify -CAfile ca.crt cert.crt

# Inspect a PKCS#12 file
openssl pkcs12 -in file.p12 -info -noout

# Check ACME directory
curl http://localhost:8080/acme/directory
```

## Data & Backup

| Path | Contents |
|---|---|
| `/data/ca-manager.db` | SQLite database (all certs, settings, ACME state) |
| `/data/ca_keys/` | CA private keys (chmod 600, never served over HTTP) |

Back up the entire `/data` directory (Docker volume `ca_data`) to preserve everything.

## Development

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev   # proxies /api and /acme to localhost:8000
```

## Security Notes

- **No authentication** — do not expose to untrusted networks
- CA private keys are stored on the filesystem at `/data/ca_keys/`, never in the database or HTTP responses
- Leaf certificate private keys are stored in SQLite (downloaded once by the user)
- ACME `skip_challenges` bypasses domain ownership verification — only use on fully trusted networks
