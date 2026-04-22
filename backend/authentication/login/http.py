from __future__ import annotations

import logging

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.login import LoginCommand, build_login_use_case
from authentication.login.constants import (
    LOGIN_EMAIL_NOT_VERIFIED_MESSAGE,
    LOGIN_INVALID_CREDENTIALS_MESSAGE,
    LOGIN_RATE_LIMITED_MESSAGE,
    LOGIN_SERVER_ERROR_MESSAGE,
)
from authentication.login.exceptions import (
    EmailNotVerifiedError,
    InvalidCredentialsError,
    LoginRateLimitedError,
    LoginServiceError,
)
from authentication.serializers import LoginSerializer

logger = logging.getLogger(__name__)

LOGIN_HTTP_UNEXPECTED_ERRORS = (
    RuntimeError,
    ValueError,
    TypeError,
    KeyError,
    AttributeError,
    OSError,
)


class LoginView(APIView):
    permission_classes = [AllowAny]

    def get_login_use_case(self):
        return build_login_use_case()

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        validated = serializer.validated_data

        try:
            result = self.get_login_use_case().execute(
                LoginCommand(
                    email=validated["email"],
                    password=validated["password"],
                )
            )
            return Response(
                {
                    "access_token": result.tokens.access_token,
                    "refresh_token": result.tokens.refresh_token,
                    "user": {
                        "id": result.user.id,
                        "email": result.user.email,
                        "name": result.user.name,
                    },
                },
                status=status.HTTP_200_OK,
            )
        except LoginRateLimitedError:
            return Response(
                {"message": LOGIN_RATE_LIMITED_MESSAGE},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        except InvalidCredentialsError:
            return Response(
                {"message": LOGIN_INVALID_CREDENTIALS_MESSAGE},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        except EmailNotVerifiedError:
            return Response(
                {"message": LOGIN_EMAIL_NOT_VERIFIED_MESSAGE},
                status=status.HTTP_403_FORBIDDEN,
            )
        except LoginServiceError:
            logger.exception("Unexpected error during login.")
            return Response(
                {"message": LOGIN_SERVER_ERROR_MESSAGE},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except LOGIN_HTTP_UNEXPECTED_ERRORS:
            logger.exception("Unhandled error during login.")
            return Response(
                {"message": LOGIN_SERVER_ERROR_MESSAGE},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
