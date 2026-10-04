"""Admin password policy: length, bcrypt's byte limit, and a common-password check.

The list below is the long (12+ character) end of the well-known breached-password lists,
plus patterns specific to this company. It is deliberately small and embedded so the check
works offline; the rule checks catch the variations a list can't enumerate.
"""

import re

from app.core.constants import PASSWORD_MAX_BYTES, PASSWORD_MIN_LENGTH

COMMON_PASSWORDS = frozenset(
    {
        "123456789012",
        "1234567890123",
        "12345678901234",
        "123456789123",
        "1234567891011",
        "000000000000",
        "111111111111",
        "123123123123",
        "121212121212",
        "112233445566",
        "password1234",
        "password12345",
        "password123456",
        "password@123",
        "password@1234",
        "passw0rd1234",
        "p@ssw0rd1234",
        "p@ssword1234",
        "password!123",
        "mypassword123",
        "qwertyuiop12",
        "qwertyuiop123",
        "qwerty123456",
        "qwertyuiopasdf",
        "1qaz2wsx3edc",
        "1q2w3e4r5t6y",
        "zaq12wsxcde3",
        "asdfghjkl123",
        "asdfghjklqwe",
        "zxcvbnm12345",
        "iloveyou1234",
        "iloveyou12345",
        "welcome12345",
        "welcome@1234",
        "welcome123456",
        "letmein12345",
        "admin1234567",
        "admin@123456",
        "administrator",
        "administrator1",
        "superman1234",
        "football1234",
        "baseball1234",
        "princess1234",
        "sunshine1234",
        "trustno11234",
        "starwars1234",
        "monkey123456",
        "dragon123456",
        "shadow123456",
        "india1234567",
        "india@123456",
        "bharat123456",
        "jaihind12345",
        "dehradun1234",
        "dehradun@123",
        "uttarakhand1",
        "uttarakhand123",
        "uttarakhand@123",
        "solar1234567",
        "solarenergy1",
        "solarenergy123",
        "solarpower123",
        "changeme1234",
        "changeme12345",
        "temp12345678",
        "test12345678",
        "testing12345",
        "default12345",
        "secret123456",
    }
)

# Fragments that make a password guessable for this particular site.
_BANNED_FRAGMENTS = ("password", "passw0rd", "p@ssw0rd", "envex", "qwerty", "123456789")


def password_problem(password: str, email: str | None = None) -> str | None:
    """Why this password is not acceptable, or None if it is."""
    if len(password) < PASSWORD_MIN_LENGTH:
        return f"Use at least {PASSWORD_MIN_LENGTH} characters."
    if len(password.encode()) > PASSWORD_MAX_BYTES:
        return f"Use at most {PASSWORD_MAX_BYTES} bytes (about 70 characters)."
    if password.strip() != password:
        return "The password can't start or end with a space."

    lowered = password.lower()
    if lowered in COMMON_PASSWORDS:
        return "That password is too common. Choose something less predictable."
    if any(fragment in lowered for fragment in _BANNED_FRAGMENTS):
        return "Avoid common words and sequences like 'password', '123456789' or the company name."
    if len(set(lowered)) < 5:
        return "Use a wider mix of characters."
    if re.fullmatch(r"(.{1,4})\1+", lowered):
        return "Avoid repeating the same short pattern."
    if email:
        local = email.split("@", 1)[0].lower()
        if len(local) >= 4 and local in lowered:
            return "Don't include your email address in the password."
    return None
