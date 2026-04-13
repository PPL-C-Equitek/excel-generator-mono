from __future__ import annotations

import logging
from functools import wraps

from rest_framework import status
from rest_framework import serializers as drf_serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from api.decorators import rate_limit
from authentication.register import RegisterCommand, RegistrationServiceError, build_register_user_use_case
from authentication.register.exceptions import RegistrationConflictError, UnverifiedRegistrationError
from authentication.serializers import RegisterSerializer, validate_password_strength

logger = logging.getLogger(__name__)


def apply_rate_limit_to_method(**rate_limit_kwargs):
    """Adapter to apply the function-based rate-limit decorator to APIView methods."""

    def decorator(method):
        @wraps(method)
        def wrapped(self, request, *args, **kwargs):
            @rate_limit(**rate_limit_kwargs)
            def method_wrapper(inner_request, *_args, **_kwargs):
                return method(self, inner_request, *args, **kwargs)

            return method_wrapper(request)

        return wrapped

    return decorator


class RegisterView(APIView):
    def get_register_use_case(self):
        return build_register_user_use_case()

    @apply_rate_limit_to_method(max_requests=60, per="minute")
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        password = request.data.get("password")
        password_error_response = self._validate_password_if_provided(password=password)
        if password_error_response is not None:
            return password_error_response

        try:
            validated = serializer.validated_data
            result = self.get_register_use_case().execute(
                RegisterCommand(
                    name=validated["name"],
                    email=validated["email"],
                ),
                password=password,
            )
            return Response(
                {"message": result.message},
                status=status.HTTP_201_CREATED,
            )
        except UnverifiedRegistrationError:
            return Response(
                {
                    "code": "UNVERIFIED_EMAIL",
                    "message": "Email registered but unverified. A new link has been sent.",
                },
                status=status.HTTP_409_CONFLICT,
            )
        except RegistrationServiceError:
            logger.exception("Unexpected error during user registration.")
            return Response(
                {"message": "An internal server error occurred"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except RegistrationConflictError:
            return Response(
                {"message": "Email is already registered."},
                status=status.HTTP_409_CONFLICT,
            )
        except Exception:
            logger.exception("Unhandled error during user registration.")
            return Response(
                {"message": "An internal server error occurred"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _validate_password_if_provided(self, password: str | None) -> Response | None:
        if password is None:
            return None

        try:
            validate_password_strength(password)
        except drf_serializers.ValidationError as exc:
            detail = exc.detail if isinstance(exc.detail, list) else [exc.detail]
            return Response(
                {"errors": {"password": detail}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return None
