"""Builds wa.me click-to-chat links. Pure functions: no I/O, easy to test."""

import uuid
from urllib.parse import quote


def enquiry_reference(enquiry_id: uuid.UUID) -> str:
    """Short reference the team can match in WhatsApp, e.g. ``ENV-3F2A``."""
    return "ENV-" + enquiry_id.hex[:4].upper()


def build_enquiry_message(
    *,
    company_name: str,
    name: str,
    project_type: str,
    location: str,
    reference: str,
    system_size: str | None = None,
) -> str:
    project = f"{project_type} ({system_size})" if system_size else project_type
    return "\n".join(
        [
            f"Hello {company_name}, I've just sent a project enquiry on your website.",
            f"Name: {name}",
            f"Project: {project}",
            f"Location: {location}",
            f"Reference: {reference}",
        ]
    )


def build_whatsapp_url(whatsapp_number: str, text: str) -> str:
    """``https://wa.me/<digits>?text=<percent-encoded>``.

    ``safe=""`` encodes every reserved character (``& # + / ?`` and newlines) so user
    input can never break out of the ``text`` parameter.
    """
    return f"https://wa.me/{whatsapp_number}?text={quote(text, safe='')}"


def build_customer_reply_message(
    *, company_name: str, name: str, project_type: str, reference: str
) -> str:
    """Opening line when the team messages a customer from the admin page."""
    first_name = name.split()[0] if name.split() else name
    return (
        f"Hello {first_name}, this is {company_name} about your {project_type.lower()} "
        f"enquiry ({reference}). Is this a good time to talk?"
    )


def customer_whatsapp_url(phone_e164: str, text: str) -> str:
    """wa.me wants the number as digits only, without '+'."""
    return build_whatsapp_url(phone_e164.lstrip("+"), text)
