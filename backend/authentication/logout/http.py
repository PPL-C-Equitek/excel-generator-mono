from __future__ import annotations

import jwt
from jwt import PyJWTError

from django.conf import settings
from rest_framework import status
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.models import User
from authentication.logout.adapters import build_logout_user_use_case
from authentication.logout.entities import LogoutCommand


class JWTAccessAuthentication(BaseAuthentication):
    def authenticate(self, request):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return None

        token = auth_header.split(" ", 1)[1].strip()
        secret_key = getattr(settings, "JWT_SECRET_KEY", "")

        try:
            payload = jwt.decode(token, secret_key, algorithms=["HS256"])
        except PyJWTError as exc:
            raise AuthenticationFailed("Unauthorized") from exc

        if payload.get("type") != "access":  # pragma: no cover
            raise AuthenticationFailed("Unauthorized")

        user_id = payload.get("user_id")
        if not user_id:  # pragma: no cover
            raise AuthenticationFailed("Unauthorized")

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist as exc:  # pragma: no cover
            raise AuthenticationFailed("Unauthorized") from exc

        return (user, None)

    def authenticate_header(self, request):
        return "Bearer"


class LogoutView(APIView):
    authentication_classes = [JWTAccessAuthentication]
    permission_classes = [IsAuthenticated]

    def get_logout_use_case(self):
        # This base factory is used outside the legacy wrapper in authentication.views.
        return build_logout_user_use_case()  # pragma: no cover

    def post(self, request):
        try:
            command = LogoutCommand(refresh_token=request.data.get("refresh_token", ""))
            self.get_logout_use_case().execute(command)
            return Response(status=status.HTTP_200_OK)
        except (ValueError, Exception):
            return Response(
                {"message": "Unauthorized"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
