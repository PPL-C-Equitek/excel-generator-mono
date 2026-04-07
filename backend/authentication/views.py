import logging
from datetime import timedelta
from django.core.cache import cache

from django.core.signing import TimestampSigner, SignatureExpired, BadSignature
from rest_framework import status
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from django.conf import settings
from authentication.oauth_services import GoogleOAuthService

from authentication.logout.adapters import (
    CallableTokenBlacklistRepository,
    DjangoTokenBlacklistRepository,
    build_logout_user_use_case,
)
from authentication.logout.http import LogoutView as CleanLogoutView
from authentication.models import User
from authentication.serializers import (
    EmailRequestSerializer,
    LoginSerializer,
    RefreshTokenSerializer,
    ResetPasswordSerializer,
    VerifyEmailSerializer,
)
from authentication.services import (
    PASSWORD_RESET_RESEND_SUCCESS_MESSAGE,
    PASSWORD_RESET_SUCCESS_MESSAGE,
    decode_password_reset_token,
    send_verification_email,
    send_password_reset_email,
    generate_tokens,
    LoginFailureTracker as BaseLoginFailureTracker,
    LoginService,
    RefreshTokenService,
    LoginRateLimitedError,
    InvalidCredentialsError,
    EmailNotVerifiedError,
    BlacklistedRefreshTokenError,
    RefreshTokenExpiredError,
    InvalidRefreshTokenError,
)

logger = logging.getLogger(__name__)
SERVER_ERROR_MESSAGE = "An internal server error occurred. Please try again later."

class GoogleOAuthRateThrottle(AnonRateThrottle):
    rate = "10/hour"

def blacklist_refresh_token(refresh_token: str) -> None:
    DjangoTokenBlacklistRepository().blacklist(refresh_token)


class ResendVerificationThrottle(SimpleRateThrottle):
    scope = "resend_verification"
    rate = "3/15min"

    def get_cache_key(self, request, view):
        email = request.data.get("email", "")
        ident = email.lower().strip() if email else self.get_ident(request)
        return self.cache_format % {"scope": self.scope, "ident": ident}

    def parse_rate(self, rate):
        return (3, 900)


class PasswordResetRequestThrottle(SimpleRateThrottle):
    scope = "password_reset_request"
    rate = "3/15min"

    def get_cache_key(self, request, view):
        email = request.data.get("email", "")
        ident = email.lower().strip() if email else self.get_ident(request)
        return self.cache_format % {"scope": self.scope, "ident": ident}

    def parse_rate(self, rate):
        return (3, 900)


class ResendPasswordResetThrottle(SimpleRateThrottle):
    scope = "resend_password_reset"
    rate = "3/15min"

    def get_cache_key(self, request, view):
        email = request.data.get("email", "")
        ident = email.lower().strip() if email else self.get_ident(request)
        return self.cache_format % {"scope": self.scope, "ident": ident}

    def parse_rate(self, rate):
        return (3, 900)


class VerifyEmailView(APIView):
    def post(self, request):
        serializer = VerifyEmailSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        token = serializer.validated_data["token"]
        password = serializer.validated_data["password"]

        signer = TimestampSigner()
        try:
            email = signer.unsign(token, max_age=timedelta(hours=24))
        except SignatureExpired:
            return Response(
                {"message": "Token expired. Please request a new verification email."},
                status=status.HTTP_410_GONE,
            )
        except BadSignature:
            return Response(
                {"message": "Invalid token"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                {"message": "User not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        user.set_password(password)
        user.status = "verified"
        user.save(update_fields=["password", "status"])

        return Response(
            {"message": "Email verified successfully"},
            status=status.HTTP_200_OK,
        )


class ResendVerificationView(APIView):
    throttle_classes = [ResendVerificationThrottle]

    def post(self, request):
        email = request.data.get("email")
        if not email:
            return Response(
                {"message": "Email is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                {"message": "User not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        if user.status == "verified":
            return Response(
                {"message": "Email is already verified"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        send_verification_email(user.email)

        return Response(
            {"message": "Verification email has been resent"},
            status=status.HTTP_200_OK,
        )


class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [PasswordResetRequestThrottle]

    def post(self, request):
        serializer = EmailRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        email = serializer.validated_data["email"].lower().strip()
        user = User.objects.filter(email=email, status="verified").first()

        if user is not None:
            send_password_reset_email(user.email)

        return Response(
            {"message": PASSWORD_RESET_SUCCESS_MESSAGE},
            status=status.HTTP_200_OK,
        )


class ResendPasswordResetView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ResendPasswordResetThrottle]

    def post(self, request):
        serializer = EmailRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        email = serializer.validated_data["email"].lower().strip()
        user = User.objects.filter(email=email, status="verified").first()

        if user is not None:
            send_password_reset_email(user.email)

        return Response(
            {"message": PASSWORD_RESET_RESEND_SUCCESS_MESSAGE},
            status=status.HTTP_200_OK,
        )


class ResetPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        token = serializer.validated_data["token"]
        password = serializer.validated_data["password"]

        try:
            email = decode_password_reset_token(token, max_age=timedelta(hours=1))
        except SignatureExpired:
            return Response(
                {"message": "Token expired. Please request a new password reset email."},
                status=status.HTTP_410_GONE,
            )
        except (BadSignature, ValueError):
            return Response(
                {"message": "Invalid token"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = User.objects.get(email=email, status="verified")
        except User.DoesNotExist:
            return Response(
                {"message": "User not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        user.set_password(password)
        user.save(update_fields=["password"])

        return Response(
            {"message": "Password reset successfully"},
            status=status.HTTP_200_OK,
        )


class LoginFailureTracker(BaseLoginFailureTracker):
    @classmethod
    def get_cache_backend(cls):
        return cache


class DjangoUserLookupGateway:
    def get_by_email(self, email: str) -> User:
        return User.objects.get(email=email)

class LoginView(APIView):
    """Login endpoint with JWT token generation and rate limiting"""

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )
        email = serializer.validated_data["email"]
        password = serializer.validated_data["password"]

        login_service = LoginService(
            user_gateway=DjangoUserLookupGateway(),
            failure_tracker=LoginFailureTracker,
            token_generator=generate_tokens,
        )

        try:
            result = login_service.authenticate(email=email, password=password)
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
                {"message": "Terlalu banyak percobaan gagal. Coba lagi dalam beberapa menit."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        except InvalidCredentialsError:
            return Response(
                {"message": "Email atau password salah"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        except EmailNotVerifiedError:
            return Response(
                {"message": "Email Anda belum diverifikasi. Cek email untuk link verifikasi."},
                status=status.HTTP_403_FORBIDDEN,
            )
        except Exception:
            logger.exception("Unexpected error during login for email: %s", email)
            return Response(
                {"message": SERVER_ERROR_MESSAGE},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class RefreshTokenView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RefreshTokenSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        refresh_token = serializer.validated_data["refresh_token"]
        refresh_service = RefreshTokenService(
            token_generator=generate_tokens,
            token_blacklist_port=DjangoTokenBlacklistRepository(),
        )

        try:
            tokens = refresh_service.refresh(refresh_token)
            return Response(
                {
                    "access_token": tokens["access_token"],
                    "refresh_token": tokens["refresh_token"],
                },
                status=status.HTTP_200_OK,
            )
        except RefreshTokenExpiredError:
            return Response(
                {"message": "Token expired. Silakan login ulang."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        except BlacklistedRefreshTokenError:
            return Response(
                {"message": "Refresh token sudah logout."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        except InvalidRefreshTokenError:
            return Response(
                {"message": "Refresh token tidak valid."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        except Exception:
            logger.exception("Unexpected error during refresh token exchange.")
            return Response(
                {"message": SERVER_ERROR_MESSAGE},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

class GoogleOAuthCallbackView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [GoogleOAuthRateThrottle]

    def post(self, request):
        token = request.data.get("token")

        if not request.is_secure() and not settings.DEBUG:
            return Response(
                {"message": "HTTPS required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not token:
            return Response(
                {"message": "Token tidak ditemukan"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not isinstance(token, str) or len(token) > 2048:
            return Response(
                {"message": "Format token tidak valid"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        google_client_id = getattr(settings, "GOOGLE_OAUTH_CLIENT_ID", "")
        if not google_client_id:
            logger.error("GOOGLE_OAUTH_CLIENT_ID not configured")
            return Response(
                {"message": SERVER_ERROR_MESSAGE},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        try:
            oauth_service = GoogleOAuthService(google_client_id)
            result = oauth_service.authenticate_or_create_user(token)

            return Response(
                {
                    "access_token": result["tokens"]["access_token"],
                    "refresh_token": result["tokens"]["refresh_token"],
                    "user": {
                        "id": result["user"].id,
                        "email": result["user"].email,
                        "name": result["user"].name,
                    },
                },
                status=status.HTTP_200_OK,
            )
        except ValueError as e:
            logger.warning(f"Google OAuth verification failed: {e}")
            return Response(
                {"message": "Invalid token atau gagal memverifikasi Google Token"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        except Exception:
            logger.exception("Unexpected error during Google OAuth")
            return Response(
                {"message": SERVER_ERROR_MESSAGE},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


google_oauth_callback = GoogleOAuthCallbackView.as_view()
class LogoutView(CleanLogoutView):
    def get_logout_use_case(self):
        return build_logout_user_use_case(
            token_blacklist_port=CallableTokenBlacklistRepository(blacklist_refresh_token)
        )

