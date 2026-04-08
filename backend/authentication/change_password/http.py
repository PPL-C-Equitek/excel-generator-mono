from __future__ import annotations

import logging

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.change_password.adapters import build_change_password_use_case
from authentication.change_password.constants import (
    CHANGE_PASSWORD_CURRENT_PASSWORD_REQUIRED_MESSAGE,
    CHANGE_PASSWORD_INVALID_CURRENT_PASSWORD_MESSAGE,
    CHANGE_PASSWORD_PASSWORD_REUSE_MESSAGE,
    CHANGE_PASSWORD_SERVER_ERROR_MESSAGE,
)
from authentication.change_password.exceptions import (
    ChangePasswordServiceError,
    CurrentPasswordRequiredError,
    InvalidCurrentPasswordError,
    PasswordReuseError,
)
from authentication.change_password.serializers import ChangePasswordSerializer
from authentication.jwt_authentication import JWTAuthentication

logger = logging.getLogger(__name__)


class ChangePasswordView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get_change_password_use_case(self):
        return build_change_password_use_case()

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            result = self.get_change_password_use_case().execute(
                serializer.to_command(request.user)
            )
            return Response(
                {"message": result.message},
                status=status.HTTP_200_OK,
            )
        except CurrentPasswordRequiredError:
            return Response(
                {"message": CHANGE_PASSWORD_CURRENT_PASSWORD_REQUIRED_MESSAGE},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except InvalidCurrentPasswordError:
            return Response(
                {"message": CHANGE_PASSWORD_INVALID_CURRENT_PASSWORD_MESSAGE},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except PasswordReuseError:
            return Response(
                {"message": CHANGE_PASSWORD_PASSWORD_REUSE_MESSAGE},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except ChangePasswordServiceError:
            logger.exception("Unexpected error during password change.")
            return Response(
                {"message": CHANGE_PASSWORD_SERVER_ERROR_MESSAGE},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except Exception:
            logger.exception("Unhandled error during password change.")
            return Response(
                {"message": CHANGE_PASSWORD_SERVER_ERROR_MESSAGE},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
