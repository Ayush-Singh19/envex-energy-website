"""Import every model so Base.metadata is complete (Alembic autogenerate relies on it)."""

from app.models.admin_user import AdminUser
from app.models.audit_log import AuditLog
from app.models.click_event import ClickEvent
from app.models.enquiry import Enquiry
from app.models.enquiry_note import EnquiryNote

__all__ = ["AdminUser", "AuditLog", "ClickEvent", "Enquiry", "EnquiryNote"]
