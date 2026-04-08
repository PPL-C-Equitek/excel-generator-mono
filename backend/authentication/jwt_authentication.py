import jwt
from django.conf import settings
from rest_framework import authentication
from rest_framework import exceptions

from authentication.models import User


class JWTAuthentication(authentication.BaseAuthentication):
    keyword = "Bearer"
    algorithms = ["HS256"]

    def authenticate(self, request):
        auth_header = authentication.get_authorization_header(request).decode("utf-8")
        if not auth_header:
            return None

        parts = auth_header.split()
        if len(parts) != 2 or parts[0] != self.keyword:
            return None

        token = parts[1]
        payload = self._decode_token(token)

        token_type = payload.get("type")
        if token_type != "access":
            raise exceptions.AuthenticationFailed("Invalid token type.")

        user_id = payload.get("user_id")
        if not user_id:
            raise exceptions.AuthenticationFailed("Invalid token payload.")

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist as exc:
            raise exceptions.AuthenticationFailed("User not found.") from exc

        return (user, payload)

    def _decode_token(self, token):
        secret_key = getattr(settings, "JWT_SECRET_KEY", "")
        if not secret_key:
            raise exceptions.AuthenticationFailed("JWT secret is not configured.")

        try:
            return jwt.decode(token, secret_key, algorithms=self.algorithms)
        except jwt.ExpiredSignatureError as exc:
            raise exceptions.AuthenticationFailed("Token has expired.") from exc
        except jwt.InvalidTokenError as exc:
            raise exceptions.AuthenticationFailed("Invalid token.") from exc

    def authenticate_header(self, request):
        return self.keyword
