from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..dependencies import get_db
from ..models import Settings
from ..schemas import SettingsRead, SettingsUpdate
from ..email_utils import send_test_email

router = APIRouter(prefix="/api/settings", tags=["settings"])


def _get_or_create(db: Session) -> Settings:
    s = db.query(Settings).filter(Settings.id == 1).first()
    if not s:
        s = Settings(id=1)
        db.add(s)
        db.commit()
        db.refresh(s)
    return s


@router.get("/", response_model=SettingsRead)
def get_settings(db: Session = Depends(get_db)):
    return _get_or_create(db)


@router.put("/", response_model=SettingsRead)
def update_settings(payload: SettingsUpdate, db: Session = Depends(get_db)):
    s = _get_or_create(db)
    for field, value in payload.model_dump().items():
        # Don't overwrite stored password if client sends empty string (treat as "unchanged")
        if field == "smtp_password" and value == "":
            continue
        setattr(s, field, value)
    db.commit()
    db.refresh(s)
    return s


@router.post("/test-email")
def test_email(db: Session = Depends(get_db)):
    s = _get_or_create(db)
    if not s.smtp_host or not s.alert_to:
        raise HTTPException(status_code=422, detail="Configure SMTP host and recipient email first")
    try:
        send_test_email(s)
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {"ok": True}
