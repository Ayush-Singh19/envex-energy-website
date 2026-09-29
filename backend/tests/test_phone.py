import pytest

from app.core.phone import InvalidPhoneError, normalise_phone


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("9876543210", "+919876543210"),
        ("98765 43210", "+919876543210"),
        ("098765-43210", "+919876543210"),
        ("919876543210", "+919876543210"),
        ("+91 98765 43210", "+919876543210"),
        ("+91 (98765) 43210", "+919876543210"),
        ("0135 264 0000", "+911352640000"),  # Dehradun landline with STD code
        ("+44 20 7946 0958", "+442079460958"),
        ("0044 20 7946 0958", "+442079460958"),
    ],
)
def test_normalises_to_e164(raw: str, expected: str) -> None:
    assert normalise_phone(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "123456",  # fails the frontend regex (under 7 chars)
        "98765abc10",  # letters
        "1234567",  # passes the regex but isn't a routable number
        "+91 98765",  # +91 with too few digits
        "+1234567890123456",  # more than 15 digits
    ],
)
def test_rejects_unusable_numbers(raw: str) -> None:
    with pytest.raises(InvalidPhoneError):
        normalise_phone(raw)
