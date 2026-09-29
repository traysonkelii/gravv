"""Shared request/response building blocks."""

import re
from typing import Annotated

from pydantic import AfterValidator

_EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,255}\.[^@\s.]{2,}$")


def normalize_email(value: str) -> str:
    v = value.strip().lower()
    if not _EMAIL_RE.match(v):
        raise ValueError("Enter a valid email address")
    return v


# email-validator rejects reserved TLDs such as .local, which local development and tests rely on.
EmailAddress = Annotated[str, AfterValidator(normalize_email)]
