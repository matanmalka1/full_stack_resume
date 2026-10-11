"""Sign-in identity rules: how an email is stored and what a password must be.

Pure functions with no persistence or hashing. The application layer maps a rule that
fails to its refusal (architecture §18.4).
"""

from __future__ import annotations

import unicodedata

PASSWORD_MIN_LENGTH = 12
PASSWORD_MAX_LENGTH = 256


class EmailRejected(ValueError):
    """The text cannot be an email address."""


class PasswordRejected(ValueError):
    """The password is outside the policy; the message names only the rule."""


def normalize_email(raw: str) -> str:
    """NFC, trimmed, lowercased, nothing else; refuse what cannot be an address."""
    email = unicodedata.normalize("NFC", raw).strip().lower()
    local, separator, domain = email.partition("@")
    if not separator or not local or not domain or "@" in domain:
        raise EmailRejected("An email address has one @ with text on both sides.")
    if any(character.isspace() for character in email):
        raise EmailRejected("An email address contains no whitespace.")
    return email


def check_password_policy(password: str) -> None:
    """12 to 256 characters and no composition rules."""
    if len(password) < PASSWORD_MIN_LENGTH:
        raise PasswordRejected(f"A password has at least {PASSWORD_MIN_LENGTH} characters.")
    if len(password) > PASSWORD_MAX_LENGTH:
        raise PasswordRejected(f"A password has at most {PASSWORD_MAX_LENGTH} characters.")
