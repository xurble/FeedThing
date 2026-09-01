from urllib.parse import urlsplit, urlunsplit

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator

_navigation_url_validator = URLValidator(schemes=["http", "https"])


def normalize_navigation_url(value):
    if not isinstance(value, str):
        return ""

    value = value.strip()
    if not value:
        return ""

    try:
        _navigation_url_validator(value)
        parsed = urlsplit(value)
    except (ValidationError, ValueError):
        return ""

    if parsed.scheme.lower() not in ("http", "https") or not parsed.hostname:
        return ""

    return urlunsplit(
        (
            parsed.scheme.lower(),
            parsed.netloc,
            parsed.path,
            parsed.query,
            parsed.fragment,
        )
    )
