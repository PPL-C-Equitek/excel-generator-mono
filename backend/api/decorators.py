"""
Reusable rate-limit decorator for DRF function-based views.

Usage:
    from api.decorators import rate_limit

    @api_view(["POST"])
    @rate_limit(max_requests=30, per="minute")
    def upload(request):
        ...

    # Custom identity key (e.g., per API key header)
    @api_view(["POST"])
    @rate_limit(
        max_requests=10,
        per="second",
        key_func=lambda request: request.headers.get("X-API-Key", "anonymous"),
    )
    def llm_generate(request):
        ...

    # Custom block response detail/status/code
    @api_view(["POST"])
    @rate_limit(
        max_requests=5,
        per="minute",
        error_detail="Too many uploads.",
        error_status=429,
        error_code="rate_limit_exceeded",
    )
    def upload_limited(request):
        ...
"""

from functools import wraps
from math import ceil
from time import monotonic

from django.core.cache import cache
from rest_framework.response import Response

WINDOW_SECONDS = {
    "second": 1,
    "seconds": 1,
    "minute": 60,
    "minutes": 60,
}


def _get_client_ip(request):
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "unknown")


def _default_key_func(request):
    return _get_client_ip(request)


def rate_limit(
    max_requests,
    per="minute",
    key_func=None,
    error_detail="Rate limit exceeded. Try again later.",
    error_status=429,
    error_code=None,
):
    window = WINDOW_SECONDS.get(str(per).lower())
    if window is None:
        raise ValueError("per must be one of: second, seconds, minute, minutes")
    if max_requests <= 0:
        raise ValueError("max_requests must be greater than 0")
    if key_func is not None and not callable(key_func):
        raise ValueError("key_func must be callable")
    if error_status <= 0:
        raise ValueError("error_status must be greater than 0")

    identity_func = key_func or _default_key_func

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            identity = str(identity_func(request))
            current_time = monotonic()
            bucket = int(current_time // window)
            key = (
                f"rl:{view_func.__module__}.{view_func.__name__}:"
                f"{request.method}:{request.path}:{identity}:{bucket}"
            )

            if not cache.add(key, 1, timeout=window + 1):
                try:
                    current = cache.incr(key)
                except ValueError:
                    cache.add(key, 1, timeout=window + 1)
                    current = 1
            else:
                current = 1

            remaining = max(max_requests - current, 0)
            if current > max_requests:
                reset_at = (bucket + 1) * window
                retry_after = max(1, ceil(reset_at - current_time))
                payload = {"detail": error_detail}
                if error_code:
                    payload["code"] = error_code
                response = Response(
                    payload,
                    status=error_status,
                )
                response["Retry-After"] = str(retry_after)
                response["X-RateLimit-Limit"] = str(max_requests)
                response["X-RateLimit-Remaining"] = "0"
                return response

            response = view_func(request, *args, **kwargs)
            response["X-RateLimit-Limit"] = str(max_requests)
            response["X-RateLimit-Remaining"] = str(remaining)
            return response

        return _wrapped

    return decorator
