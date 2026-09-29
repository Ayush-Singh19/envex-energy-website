import uuid
from urllib.parse import parse_qs, urlsplit

from app.services.whatsapp_service import (
    build_enquiry_message,
    build_whatsapp_url,
    enquiry_reference,
)


def _decoded_text(url: str) -> str:
    return parse_qs(urlsplit(url).query, strict_parsing=True)["text"][0]


def test_reference_is_env_plus_first_four_hex_chars_uppercase() -> None:
    assert enquiry_reference(uuid.UUID("3f2a9c1e-0000-4000-8000-000000000000")) == "ENV-3F2A"


def test_message_contents_with_and_without_size() -> None:
    with_size = build_enquiry_message(
        company_name="Envex Energy",
        name="Asha",
        project_type="Rooftop solar",
        system_size="5 kW",
        location="Dehradun",
        reference="ENV-3F2A",
    )
    assert with_size.startswith("Hello Envex Energy,")
    assert "Name: Asha" in with_size
    assert "Project: Rooftop solar (5 kW)" in with_size
    assert "Location: Dehradun" in with_size
    assert with_size.endswith("Reference: ENV-3F2A")

    without_size = build_enquiry_message(
        company_name="Envex Energy",
        name="Asha",
        project_type="Rooftop solar",
        location="Dehradun",
        reference="ENV-3F2A",
    )
    assert "Project: Rooftop solar\n" in without_size


def test_url_targets_company_number() -> None:
    url = build_whatsapp_url("917055444005", "hi")
    assert url == "https://wa.me/917055444005?text=hi"


def test_reserved_characters_cannot_break_out_of_text_param() -> None:
    nasty = "Solar EPC & project execution\n#1 + 50% off?a=b/c ✓ देहरादून"
    url = build_whatsapp_url("917055444005", nasty)

    query = urlsplit(url).query
    assert query.count("=") == 1  # only text=, the "=" inside the text is encoded
    for raw in ("&", "#", "+", "\n", " ", "?", "/"):
        assert raw not in query
    assert "%0A" in query  # newline
    assert "%26" in query  # ampersand
    assert _decoded_text(url) == nasty  # lossless round trip, unicode included
