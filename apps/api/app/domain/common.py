"""Shared request/response building blocks: email normalization and cursor pagination."""

import base64
import json
import re
from typing import Annotated, Any

from pydantic import AfterValidator, BaseModel

from app.errors import Problem

_EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,255}\.[^@\s.]{2,}$")


def normalize_email(value: str) -> str:
    v = value.strip().lower()
    if not _EMAIL_RE.match(v):
        raise ValueError("Enter a valid email address")
    return v


# email-validator rejects reserved TLDs such as .local, which local development and tests rely on.
EmailAddress = Annotated[str, AfterValidator(normalize_email)]


class Page[T](BaseModel):
    items: list[T]
    next_cursor: str | None = None


def encode_cursor(*parts: Any) -> str:
    raw = json.dumps(list(parts), default=str, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(cursor: str | None) -> list[Any] | None:
    if not cursor:
        return None
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        parts = json.loads(base64.urlsafe_b64decode(padded.encode()))
        if not isinstance(parts, list):
            raise ValueError
        return parts
    except (ValueError, json.JSONDecodeError) as exc:
        raise Problem(400, "bad_cursor", "Invalid cursor", "The pagination cursor is not valid.") from exc


def page_of(rows: list[Any], limit: int, cursor_for: Any) -> tuple[list[Any], str | None]:
    """rows were fetched with limit + 1; returns the visible slice and the cursor for the next page."""
    if len(rows) > limit:
        rows = rows[:limit]
        return rows, cursor_for(rows[-1])
    return rows, None
