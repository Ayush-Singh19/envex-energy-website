"""Domain constants shared by schemas, models and services.

PROJECT_TYPES mirrors ``Component.PROJECT_TYPES`` in the frontend
(``Envex Energy Landing.dc.html``). Keep the two lists in sync.
"""

import enum
import re

PROJECT_TYPES: tuple[str, ...] = (
    "Residential solar",
    "Rooftop solar",
    "On-grid solar",
    "Hybrid solar",
    "Commercial solar",
    "Industrial solar",
    "Customized solar solution",
    "Project consultancy",
    "Solar EPC & project execution",
    "Service & maintenance",
    "Other",
)

# Same rules as the frontend's _submitEnquiry validation.
PHONE_PATTERN = re.compile(r"^[0-9+\-\s()]{7,}$")
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class EnquiryStatus(enum.StrEnum):
    """Lead pipeline, in the order the admin dropdown shows it. Any status can be set any time."""

    NEW = "new"
    CALLED = "called"
    SITE_VISIT = "site_visit"
    QUOTE_SENT = "quote_sent"
    WON = "won"
    LOST = "lost"
    NOT_RELEVANT = "not_relevant"


STATUS_LABELS: dict[EnquiryStatus, str] = {
    EnquiryStatus.NEW: "New",
    EnquiryStatus.CALLED: "Called",
    EnquiryStatus.SITE_VISIT: "Site visit",
    EnquiryStatus.QUOTE_SENT: "Quote sent",
    EnquiryStatus.WON: "Won",
    EnquiryStatus.LOST: "Lost",
    EnquiryStatus.NOT_RELEVANT: "Not relevant",
}

# Leads that no longer need follow-up.
CLOSED_STATUSES = frozenset({EnquiryStatus.WON, EnquiryStatus.LOST, EnquiryStatus.NOT_RELEVANT})


class ClickType(enum.StrEnum):
    CALL = "call"
    WHATSAPP = "whatsapp"
    QUOTE = "quote"
    EMAIL = "email"


class AuditAction(enum.StrEnum):
    LOGIN = "login"
    LOGOUT = "logout"
    CHANGE_PASSWORD = "change_password"  # noqa: S105  (an audit action name, not a secret)
    UPDATE = "update"
    ADD_NOTE = "add_note"
    EXPORT = "export"


AUTH_COOKIE_NAME = "envex_admin"
PASSWORD_MIN_LENGTH = 12
PASSWORD_MAX_BYTES = 72  # bcrypt ignores anything past 72 bytes, so we refuse it instead
MAX_FAILED_LOGINS = 5
LOCKOUT_MINUTES = 15
