from __future__ import annotations

import logging
from functools import wraps

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import APIView

from api.decorators import rate_limit
from authentication.password_reset import (
    CompletePasswordResetCommand,
    InvalidPasswordResetTokenError,
    PasswordResetEmailCommand,
    PasswordResetServiceError,
    PasswordResetTokenExpiredError,
    PasswordResetUserNotFoundError,
    build_complete_password_reset_use_case,
    build_request_password_reset_use_case,
    build_resend_password_reset_use_case,
)
from authentication.password_reset.constants import (
    PASSWORD_RESET_EXPIRED_TOKEN_MESSAGE,
    PASSWORD_RESET_INVALID_TOKEN_MESSAGE,
    PASSWORD_RESET_SERVER_ERROR_MESSAGE,
    PASSWORD_RESET_USER_NOT_FOUND_MESSAGE,
)
from authentication.serializers import EmailRequestSerializer, ResetPasswordSerializer

logger = logging.getLogger(__name__)


def apply_rate_limit_to_method(**rate_limit_kwargs):
    def decorator(method):
        @wraps(method)
        def wrapped(self, request, *args, **kwargs):
            @rate_limit(**rate_limit_kwargs)
            def method_wrapper(inner_request, *_args, **_kwargs):
                return method(self, inner_request, *args, **kwargs)

            return method_wrapper(request)

        return wrapped

    return decorator


def _reset_password_rate_limit_key(request):
    token = request.data.get("token", "")
    token_prefix = token[:16] if isinstance(token, str) and token else "no-token"
    client_ip = request.META.get("REMOTE_ADDR", "unknown")
    return f"ip:{client_ip}:token:{token_prefix}"


class EmailScopedThrottle(SimpleRateThrottle):
    rate = "3/15min"

    def get_cache_key(self, request, view):
        email = request.data.get("email", "")
        ident = email.lower().strip() if email else self.get_ident(request)
        return self.cache_format % {"scope": self.scope, "ident": ident}

    def parse_rate(self, rate):
        return (3, 900)


class PasswordResetRequestThrottle(EmailScopedThrottle):
    scope = "password_reset_request"


class ResendPasswordResetThrottle(EmailScopedThrottle):
    scope = "resend_password_reset"


class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [PasswordResetRequestThrottle]

    def get_request_password_reset_use_case(self):
        return build_request_password_reset_use_case()

    def post(self, request):
        serializer = EmailRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            result = self.get_request_password_reset_use_case().execute(
                PasswordResetEmailCommand(email=serializer.validated_data["email"])
            )
            return Response(
                {"message": result.message},
                status=status.HTTP_200_OK,
            )
        except PasswordResetServiceError:
            logger.exception("Unexpected error during password reset request.")
            return Response(
                {"message": PASSWORD_RESET_SERVER_ERROR_MESSAGE},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except Exception:
            logger.exception("Unhandled error during password reset request.")
            return Response(
                {"message": PASSWORD_RESET_SERVER_ERROR_MESSAGE},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ResendPasswordResetView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ResendPasswordResetThrottle]

    def get_resend_password_reset_use_case(self):
        return build_resend_password_reset_use_case()

    def post(self, request):
        serializer = EmailRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            result = self.get_resend_password_reset_use_case().execute(
                PasswordResetEmailCommand(email=serializer.validated_data["email"])
            )
            return Response(
                {"message": result.message},
                status=status.HTTP_200_OK,
            )
        except PasswordResetServiceError:
            logger.exception("Unexpected error during password reset resend.")
            return Response(
                {"message": PASSWORD_RESET_SERVER_ERROR_MESSAGE},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except Exception:
            logger.exception("Unhandled error during password reset resend.")
            return Response(
                {"message": PASSWORD_RESET_SERVER_ERROR_MESSAGE},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ResetPasswordView(APIView):
    permission_classes = [AllowAny]

    def get_complete_password_reset_use_case(self):
        return build_complete_password_reset_use_case()

    @apply_rate_limit_to_method(
        max_requests=5,
        per="minutes",
        key_func=_reset_password_rate_limit_key,
    )
    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            result = self.get_complete_password_reset_use_case().execute(
                CompletePasswordResetCommand(
                    token=serializer.validated_data["token"],
                    password=serializer.validated_data["password"],
                )
            )
            return Response(
                {"message": result.message},
                status=status.HTTP_200_OK,
            )
        except PasswordResetTokenExpiredError:
            return Response(
                {"message": PASSWORD_RESET_EXPIRED_TOKEN_MESSAGE},
                status=status.HTTP_410_GONE,
            )
        except InvalidPasswordResetTokenError:
            return Response(
                {"message": PASSWORD_RESET_INVALID_TOKEN_MESSAGE},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except PasswordResetUserNotFoundError:
            return Response(
                {"message": PASSWORD_RESET_USER_NOT_FOUND_MESSAGE},
                status=status.HTTP_404_NOT_FOUND,
            )
        except PasswordResetServiceError:
            logger.exception("Unexpected error during password reset completion.")
            return Response(
                {"message": PASSWORD_RESET_SERVER_ERROR_MESSAGE},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except Exception:
            logger.exception("Unhandled error during password reset completion.")
            return Response(
                {"message": PASSWORD_RESET_SERVER_ERROR_MESSAGE},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
