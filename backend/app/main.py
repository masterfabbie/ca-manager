from contextlib import asynccontextmanager
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from .database import Base, DATA_DIR, engine
from .jobs import check_expiry_and_alert
from .routers import cas, certificates, csrs
from .routers import settings as settings_router
from .routers.acme import acme_mgmt_router, acme_router

# Ensure /data directory and DB are ready at startup
DATA_DIR.mkdir(parents=True, exist_ok=True)
(DATA_DIR / "ca_keys").mkdir(parents=True, exist_ok=True)
Base.metadata.create_all(bind=engine)

# Incremental schema migrations for existing DBs
_migrations = [
    "ALTER TABLE root_cas ADD COLUMN parent_ca_id VARCHAR(36) REFERENCES root_cas(id)",
    "ALTER TABLE root_cas ADD COLUMN is_intermediate BOOLEAN NOT NULL DEFAULT 0",
    "ALTER TABLE csr_records ADD COLUMN key_pem TEXT",
    "ALTER TABLE certificates ADD COLUMN alert_enabled BOOLEAN NOT NULL DEFAULT 0",
    (
        "CREATE TABLE IF NOT EXISTS settings ("
        "id INTEGER PRIMARY KEY, "
        "smtp_host VARCHAR(255) NOT NULL DEFAULT '', "
        "smtp_port INTEGER NOT NULL DEFAULT 587, "
        "smtp_username VARCHAR(255) NOT NULL DEFAULT '', "
        "smtp_password TEXT NOT NULL DEFAULT '', "
        "smtp_from VARCHAR(255) NOT NULL DEFAULT '', "
        "alert_to VARCHAR(255) NOT NULL DEFAULT '', "
        "use_tls BOOLEAN NOT NULL DEFAULT 1, "
        "alert_days INTEGER NOT NULL DEFAULT 30, "
        "alerts_enabled BOOLEAN NOT NULL DEFAULT 0)"
    ),
    "ALTER TABLE settings ADD COLUMN acme_enabled BOOLEAN NOT NULL DEFAULT 0",
    "ALTER TABLE settings ADD COLUMN acme_ca_id VARCHAR(36)",
    "ALTER TABLE settings ADD COLUMN acme_cert_days INTEGER NOT NULL DEFAULT 90",
    "ALTER TABLE settings ADD COLUMN acme_skip_challenges BOOLEAN NOT NULL DEFAULT 0",
]
with engine.connect() as conn:
    for stmt in _migrations:
        try:
            conn.execute(text(stmt))
            conn.commit()
        except Exception:
            pass  # Column/table already exists

    # Make certificates.root_ca_id nullable (SQLite requires table recreation)
    rows = conn.execute(text("PRAGMA table_info(certificates)")).fetchall()
    for row in rows:
        # row: (cid, name, type, notnull, dflt_value, pk)
        if row[1] == "root_ca_id" and row[3] == 1:  # notnull=1 → need to migrate
            try:
                conn.execute(text(
                    "CREATE TABLE certificates_v2 ("
                    "id VARCHAR(36) NOT NULL PRIMARY KEY,"
                    "root_ca_id VARCHAR(36),"
                    "common_name VARCHAR(255) NOT NULL,"
                    "sans TEXT NOT NULL,"
                    "key_size INTEGER NOT NULL,"
                    "not_before DATETIME,"
                    "not_after DATETIME,"
                    "cert_pem TEXT NOT NULL,"
                    "key_pem TEXT NOT NULL,"
                    "alert_enabled BOOLEAN NOT NULL DEFAULT 0,"
                    "created_at DATETIME,"
                    "FOREIGN KEY (root_ca_id) REFERENCES root_cas(id))"
                ))
                conn.execute(text("INSERT INTO certificates_v2 SELECT * FROM certificates"))
                conn.execute(text("DROP TABLE certificates"))
                conn.execute(text("ALTER TABLE certificates_v2 RENAME TO certificates"))
                conn.execute(text(
                    "CREATE INDEX IF NOT EXISTS ix_certificates_root_ca_id ON certificates (root_ca_id)"
                ))
                conn.commit()
            except Exception:
                pass
            break


scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.add_job(check_expiry_and_alert, "interval", hours=24, id="expiry_check")
    scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(title="CA Manager", docs_url="/api/docs", redoc_url="/api/redoc", lifespan=lifespan)

app.include_router(cas.router)
app.include_router(certificates.router)
app.include_router(csrs.router)
app.include_router(settings_router.router)
app.include_router(acme_router)
app.include_router(acme_mgmt_router)

STATIC_DIR = Path("/app/frontend/dist")

if STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        return FileResponse(STATIC_DIR / "index.html")
