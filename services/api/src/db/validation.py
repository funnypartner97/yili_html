from typing import Any

from src.core.errors import DomainError


def validate_persistence_text(value: Any) -> None:
    """Reject NUL in text and canonical JSON, including JSON object keys.

    PostgreSQL text/JSONB cannot store NUL even when JSON encodes it as an
    escape. Run before writes on every dialect so SQLite has the same boundary.
    Do not echo rejected values or user-controlled object keys in the error.
    """
    if isinstance(value, str):
        if "\u0000" in value:
            raise DomainError("validation_error", "Text must not contain NUL characters.")
    elif isinstance(value, dict):
        for key, item in value.items():
            validate_persistence_text(key)
            validate_persistence_text(item)
    elif isinstance(value, list):
        for item in value:
            validate_persistence_text(item)
