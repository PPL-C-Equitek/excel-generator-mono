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
    "15 minutes": 900,
}


def _get_client_ip(request):
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "unknown")


def _default_key_func(request):
    return _get_client_ip(request)


def _validate_rate_limit_config(max_requests, per, key_func, error_status):
    window = WINDOW_SECONDS.get(str(per).lower())
    if window is None:
        raise ValueError("per must be one of: second, seconds, minute, minutes, 15 minutes")
    if max_requests <= 0:
        raise ValueError("max_requests must be greater than 0")
    if key_func is not None and not callable(key_func):
        raise ValueError("key_func must be callable")
    if error_status <= 0:
        raise ValueError("error_status must be greater than 0")
    return window, key_func or _default_key_func


def _build_cache_key(view_func, request, identity, bucket):
    return (
        f"rl:{view_func.__module__}.{view_func.__name__}:"
        f"{request.method}:{request.path}:{identity}:{bucket}"
    )


def _increment_request_count(key, window):
    if cache.add(key, 1, timeout=window + 1):
        return 1
    try:
        return cache.incr(key)
    except ValueError:
        cache.add(key, 1, timeout=window + 1)
        return 1


def _set_rate_limit_headers(response, max_requests, remaining):
    response["X-RateLimit-Limit"] = str(max_requests)
    response["X-RateLimit-Remaining"] = str(remaining)
    return response


def _build_rate_limited_response(
    current_time,
    bucket,
    window,
    max_requests,
    error_detail,
    error_status,
    error_code,
):
    reset_at = (bucket + 1) * window
    retry_after = max(1, ceil(reset_at - current_time))
    payload = {"detail": error_detail}
    if error_code:
        payload["code"] = error_code
    response = Response(payload, status=error_status)
    response["Retry-After"] = str(retry_after)
    return _set_rate_limit_headers(response, max_requests=max_requests, remaining=0)


def _execute_rate_limited_request(
    request,
    view_func,
    args,
    kwargs,
    max_requests,
    window,
    identity_func,
    error_detail,
    error_status,
    error_code,
):
    identity = str(identity_func(request))
    current_time = monotonic()
    bucket = int(current_time // window)
    key = _build_cache_key(view_func, request, identity, bucket)

    current = _increment_request_count(key, window)
    if current > max_requests:
        return _build_rate_limited_response(
            current_time=current_time,
            bucket=bucket,
            window=window,
            max_requests=max_requests,
            error_detail=error_detail,
            error_status=error_status,
            error_code=error_code,
        )

    remaining = max(max_requests - current, 0)
    response = view_func(request, *args, **kwargs)
    return _set_rate_limit_headers(response, max_requests=max_requests, remaining=remaining)


def rate_limit(
    max_requests,
    per="minute",
    key_func=None,
    error_detail="Rate limit exceeded. Try again later.",
    error_status=429,
    error_code=None,
):
    window, identity_func = _validate_rate_limit_config(
        max_requests=max_requests,
        per=per,
        key_func=key_func,
        error_status=error_status,
    )

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            return _execute_rate_limited_request(
                request=request,
                view_func=view_func,
                args=args,
                kwargs=kwargs,
                max_requests=max_requests,
                window=window,
                identity_func=identity_func,
                error_detail=error_detail,
                error_status=error_status,
                error_code=error_code,
            )

        return _wrapped

    return decorator
