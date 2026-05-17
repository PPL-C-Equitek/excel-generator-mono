from collections.abc import Callable

from django.conf import settings


def _resolve_positive_number_setting(
    name: str,
    default,
    parser: Callable[[object], int | float],
):
    raw_value = getattr(settings, name, default)
    if isinstance(raw_value, bool):
        return default

    if isinstance(raw_value, (int, float)):
        numeric_value = parser(raw_value)
        return numeric_value if numeric_value > 0 else default

    if isinstance(raw_value, str):
        stripped_value = raw_value.strip()
        if not stripped_value:
            return default
        try:
            numeric_value = parser(stripped_value)
        except (TypeError, ValueError):
            return default
        return numeric_value if numeric_value > 0 else default

    return default


def resolve_positive_int_setting(name: str, default: int) -> int:
    return _resolve_positive_number_setting(name, default, int)


def resolve_positive_float_setting(name: str, default: float) -> float:
    return _resolve_positive_number_setting(name, default, float)
