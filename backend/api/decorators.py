from functools import wraps
from time import time

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


def rate_limit(max_requests, per="minute"):
    window = WINDOW_SECONDS.get(str(per).lower())
    if window is None:
        raise ValueError("per must be one of: second, seconds, minute, minutes")
    if max_requests <= 0:
        raise ValueError("max_requests must be greater than 0")

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            client_ip = _get_client_ip(request)
            bucket = int(time() // window)
            key = (
                f"rl:{view_func.__module__}.{view_func.__name__}:"
                f"{request.method}:{request.path}:{client_ip}:{bucket}"
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
                response = Response(
                    {"detail": "Rate limit exceeded. Try again later."},
                    status=429,
                )
                response["Retry-After"] = str(window)
                response["X-RateLimit-Limit"] = str(max_requests)
                response["X-RateLimit-Remaining"] = "0"
                return response

            response = view_func(request, *args, **kwargs)
            response["X-RateLimit-Limit"] = str(max_requests)
            response["X-RateLimit-Remaining"] = str(remaining)
            return response

        return _wrapped

    return decorator
