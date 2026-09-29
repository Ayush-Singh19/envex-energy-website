"""New-enquiry email alerts, sent from a background task after the response.

With no SMTP_HOST configured the email is not sent; a log line records that it would
have been (recipient, subject, enquiry id). Personal data is never written to logs,
so the rendered body is not logged either.
"""

import logging
import uuid
from dataclasses import dataclass
from email.message import EmailMessage
from pathlib import Path

import aiosmtplib
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.core.config import Settings
from app.services.whatsapp_service import build_whatsapp_url

logger = logging.getLogger(__name__)

_templates = Environment(
    loader=FileSystemLoader(Path(__file__).resolve().parent.parent / "templates"),
    autoescape=select_autoescape(["html"]),
)


@dataclass(frozen=True, slots=True)
class EnquiryAlert:
    """A plain snapshot of the enquiry, so the task doesn't depend on a closed DB session."""

    id: uuid.UUID
    reference: str
    name: str
    company: str | None
    phone: str
    email: str
    location: str
    project_type: str
    system_size: str | None
    message: str | None
    is_duplicate: bool
    received_at: str


def build_alert_email(alert: EnquiryAlert, settings: Settings) -> EmailMessage:
    subject = f"New enquiry {alert.reference}: {alert.project_type}"
    if alert.is_duplicate:
        subject += " (possible repeat)"

    # wa.me link that opens a chat *with the customer*, for a quick reply.
    customer_wa = build_whatsapp_url(
        alert.phone.lstrip("+"), f"Hello {alert.name}, this is {settings.company_name}."
    )
    html = _templates.get_template("email/new_enquiry.html").render(
        a=alert,
        whatsapp_customer_url=customer_wa,
        duplicate_window_hours=settings.duplicate_window_hours,
    )
    text_lines = [
        f"New website enquiry {alert.reference}",
        "",
        f"Project: {alert.project_type}" + (f" ({alert.system_size})" if alert.system_size else ""),
        f"Name: {alert.name}",
        *([f"Company: {alert.company}"] if alert.company else []),
        f"Phone: {alert.phone}",
        f"Email: {alert.email}",
        f"Location: {alert.location}",
        f"Received: {alert.received_at}",
        *(["", alert.message] if alert.message else []),
    ]

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from or settings.smtp_user or settings.alert_email
    msg["To"] = settings.alert_email
    msg["Reply-To"] = alert.email  # validated upstream: no whitespace, so no header injection
    msg.set_content("\n".join(text_lines))
    msg.add_alternative(html, subtype="html")
    return msg


async def send_new_enquiry_alert(alert: EnquiryAlert, settings: Settings) -> None:
    msg = build_alert_email(alert, settings)
    log_extra = {"enquiry_id": str(alert.id), "to": settings.alert_email}

    if not settings.smtp_enabled:
        logger.info(
            "alert_email_not_sent_smtp_disabled", extra={**log_extra, "subject": msg["Subject"]}
        )
        return

    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_user or None,
            password=settings.smtp_password.get_secret_value() or None,
            use_tls=settings.smtp_port == 465,
            start_tls=settings.smtp_port == 587,
            timeout=20,
        )
    except Exception as exc:
        # SMTP error text can echo addresses back, so log only the exception type.
        # The enquiry is already saved; a failed alert never loses the lead.
        logger.error("alert_email_failed", extra={**log_extra, "error_type": type(exc).__name__})
        return
    logger.info("alert_email_sent", extra=log_extra)
