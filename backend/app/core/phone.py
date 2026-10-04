"""Phone normalisation to E.164, defaulting to India (+91).

The frontend accepts anything matching PHONE_PATTERN (digits, spaces, + - ( ), 7+ chars).
We apply the same check, then normalise so duplicates can be detected by exact match.
"""

import re

from app.core.constants import PHONE_PATTERN

_NON_DIGITS = re.compile(r"\D")


class InvalidPhoneError(ValueError):
    pass


def normalise_phone(raw: str) -> str:
    """Return an E.164 number such as ``+917055444005``.

    Accepted shapes (spaces, dashes and brackets are ignored):
      * ``+<country><number>`` or ``00<country><number>``: kept as international.
      * 10 digits (mobile or landline with STD code): ``+91`` prepended.
      * ``0`` + 10 digits (trunk prefix): the ``0`` is replaced with ``+91``.
      * ``91`` + 10 digits: ``+`` prepended.
    """
    value = raw.strip()
    if not PHONE_PATTERN.fullmatch(value):
        raise InvalidPhoneError("Please enter a phone number we can reach you on.")

    digits = _NON_DIGITS.sub("", value)
    if value.startswith("+"):
        number = digits
    elif digits.startswith("00"):
        number = digits[2:]
    elif len(digits) == 10:
        number = "91" + digits
    elif len(digits) == 11 and digits.startswith("0"):
        number = "91" + digits[1:]
    elif len(digits) == 12 and digits.startswith("91"):
        number = digits
    else:
        raise InvalidPhoneError(
            "Please enter a 10-digit phone number, or include the country code (e.g. +91)."
        )

    # E.164 allows at most 15 digits; below 8 isn't a reachable number anywhere.
    if not 8 <= len(number) <= 15 or number.startswith("0"):
        raise InvalidPhoneError("Please enter a phone number we can reach you on.")
    if number.startswith("91") and len(number) != 12:
        raise InvalidPhoneError("Indian numbers need 10 digits after +91.")
    return "+" + number
