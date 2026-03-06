import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def _send(settings, subject: str, body: str) -> None:
    msg = MIMEMultipart()
    msg["From"] = settings.smtp_from
    msg["To"] = settings.alert_to
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
        if settings.use_tls:
            smtp.starttls()
        if settings.smtp_username:
            smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.sendmail(settings.smtp_from, settings.alert_to, msg.as_string())


def send_expiry_alert(settings, cert_common_name: str, days_left: int) -> None:
    subject = f"[CA Manager] Certificate expiring in {days_left} day(s): {cert_common_name}"
    body = (
        f"Certificate '{cert_common_name}' will expire in {days_left} day(s).\n\n"
        "Please renew it before it expires to avoid service disruptions.\n"
    )
    _send(settings, subject, body)


def send_test_email(settings) -> None:
    subject = "[CA Manager] Test email"
    body = "This is a test email from CA Manager. Your SMTP configuration is working correctly."
    _send(settings, subject, body)
