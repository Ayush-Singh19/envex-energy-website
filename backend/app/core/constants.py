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
    NEW = "new"
    CONTACTED = "contacted"
    QUOTED = "quoted"
    WON = "won"
    LOST = "lost"
    SPAM = "spam"


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
MAX_FAILED_LOGINS = 5
LOCKOUT_MINUTES = 15
