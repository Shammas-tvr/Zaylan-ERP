import zoneinfo
from functools import lru_cache

from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator

validate_hex_color = RegexValidator(r"^#[0-9A-Fa-f]{6}$", "Enter a color in #RRGGBB format.")
validate_currency_code = RegexValidator(r"^[A-Z]{3}$", "Enter a 3-letter ISO 4217 currency code.")
validate_country_code = RegexValidator(r"^[A-Z]{2}$", "Enter a 2-letter ISO 3166 country code.")


@lru_cache(maxsize=1)
def _timezones() -> frozenset[str]:
    return frozenset(zoneinfo.available_timezones())


def validate_timezone(value: str) -> None:
    if value not in _timezones():
        raise ValidationError("Enter a valid IANA timezone, for example Asia/Kolkata.")


def normalize_email(value: str) -> str:
    return value.strip().lower()


def _relative_luminance(hex_color: str) -> float:
    channels = [int(hex_color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast_ratio(foreground: str, background: str) -> float:
    lighter, darker = sorted(
        (_relative_luminance(foreground), _relative_luminance(background)), reverse=True
    )
    return (lighter + 0.05) / (darker + 0.05)
