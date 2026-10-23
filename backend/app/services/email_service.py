import logging
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib

logger = logging.getLogger(__name__)


async def send_email_via_gmail(to_email: str, subject: str, html_body: str) -> None:
    """Send an email using Gmail's SMTP server via an App Password."""
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", 587))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")

    if not smtp_user or not smtp_password:
        logger.error("SMTP credentials not configured.")
        raise RuntimeError("SMTP credentials are not configured.")

    message = MIMEMultipart()
    message["From"] = f"MediSkye <{smtp_user}>"
    message["To"] = to_email
    message["Subject"] = subject
    message.attach(MIMEText(html_body, "html"))

    try:
        await aiosmtplib.send(
            message,
            hostname=smtp_host,
            port=smtp_port,
            start_tls=True,
            username=smtp_user,
            password=smtp_password,
        )
        logger.info("Email sent successfully to %s via Gmail SMTP", to_email)
    except Exception:
        logger.exception("Failed to send email via Gmail SMTP to %s", to_email)
        raise
