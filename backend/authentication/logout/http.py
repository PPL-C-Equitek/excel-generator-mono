from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.jwt_authentication import JWTAuthentication
from authentication.logout.adapters import build_logout_user_use_case
from authentication.logout.entities import LogoutCommand


class LogoutView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get_logout_use_case(self):
        # This base factory is used outside the legacy wrapper in authentication.views.
        return build_logout_user_use_case()  # pragma: no cover

    def post(self, request):
        refresh_token = request.data.get("refresh_token")
        if not isinstance(refresh_token, str) or not refresh_token.strip():
            return Response(
                {"message": "refresh_token is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            command = LogoutCommand(refresh_token=refresh_token)
            self.get_logout_use_case().execute(command)
            request.user.session_version += 1
            request.user.save(update_fields=["session_version"])
            return Response(status=status.HTTP_200_OK)
        except ValueError:
            return Response(
                {"message": "Unauthorized"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
