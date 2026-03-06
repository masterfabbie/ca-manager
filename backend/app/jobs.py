from datetime import datetime, timezone, timedelta

from .database import SessionLocal
from .models import Certificate, Settings
from .email_utils import send_expiry_alert


def check_expiry_and_alert() -> None:
    db = SessionLocal()
    try:
        settings = db.query(Settings).filter(Settings.id == 1).first()
        if not settings or not settings.alerts_enabled or not settings.alert_to:
            return
        now = datetime.now(timezone.utc)
        threshold = now + timedelta(days=settings.alert_days)
        expiring = db.query(Certificate).filter(
            Certificate.alert_enabled == True,
            Certificate.not_after <= threshold,
            Certificate.not_after >= now,
        ).all()
        for cert in expiring:
            not_after = cert.not_after
            if not_after.tzinfo is None:
                not_after = not_after.replace(tzinfo=timezone.utc)
            days_left = (not_after - now).days
            try:
                send_expiry_alert(settings, cert.common_name, days_left)
            except Exception as e:
                print(f"Alert email failed for {cert.common_name}: {e}")
    finally:
        db.close()
