from pathlib import Path

from .database import DATA_DIR, SessionLocal


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_data_dir() -> Path:
    key_dir = DATA_DIR / "ca_keys"
    key_dir.mkdir(parents=True, exist_ok=True)
    return DATA_DIR
