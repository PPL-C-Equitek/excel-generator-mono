import logging
from datetime import timedelta
from django.core.cache import cache
from django.core.exceptions import ObjectDoesNotExist

from django.core.signing import TimestampSigner, SignatureExpired, BadSignature
from rest_framework import status
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import APIView

from authentication.models import User
from authentication.serializers import VerifyEmailSerializer, LoginSerializer
from authentication.services import send_verification_email, generate_tokens

logger = logging.getLogger(__name__)
SERVER_ERROR_MESSAGE = "An internal server error occurred. Please try again later."


class ResendVerificationThrottle(SimpleRateThrottle):
    scope = "resend_verification"
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

# LoginView with JWT token generation and rate limiting
class LoginFailureTracker:
    """Track failed login attempts for rate limiting (5 attempts per 15 minutes)"""
    FAILURE_LIMIT = 5
    TIME_WINDOW = 15 * 60  # 15 minutes in seconds
    
    @staticmethod
    def get_cache_key(email):
        return f"login_failures:{email.lower().strip()}"
    
    @classmethod
    def is_rate_limited(cls, email):
        """Check if user has exceeded login attempt limit"""
        cache_key = cls.get_cache_key(email)
        failures = cache.get(cache_key, 0)
        return failures >= cls.FAILURE_LIMIT
    
    @classmethod
    def record_failure(cls, email):
        """Record a failed login attempt using atomic increment."""
        cache_key = cls.get_cache_key(email)
        cache.add(cache_key, 0, cls.TIME_WINDOW)

        try:
            return cache.incr(cache_key)
        except ValueError:
            cache.set(cache_key, 1, cls.TIME_WINDOW)
            return 1
    
    @classmethod
    def reset_failures(cls, email):
        """Reset failure count on successful login"""
        cache_key = cls.get_cache_key(email)
        cache.delete(cache_key)


class LoginView(APIView):
    """Login endpoint with JWT token generation and rate limiting"""
    
    def post(self, request):
        # Validate input
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        # Check rate limiting
        email = serializer.validated_data["email"].lower().strip()
        if LoginFailureTracker.is_rate_limited(email):
            return Response(
                {"message": "Terlalu banyak percobaan gagal. Coba lagi dalam beberapa menit."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        
        password = serializer.validated_data["password"]
        
        try:
            # Find user by email
            user = User.objects.get(email=email)
        except ObjectDoesNotExist:
            LoginFailureTracker.record_failure(email)
            return Response(
                {"message": "Email atau password salah"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        except Exception:
            logger.exception("Unexpected error during login lookup for email: %s", email)
            return Response(
                {"message": SERVER_ERROR_MESSAGE},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        
        # Verify password
        if not user.check_password(password):
            LoginFailureTracker.record_failure(email)
            return Response(
                {"message": "Email atau password salah"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        
        # Check email verification
        if user.status != "verified":
            LoginFailureTracker.record_failure(email)
            return Response(
                {"message": "Email Anda belum diverifikasi. Cek email untuk link verifikasi."},
                status=status.HTTP_403_FORBIDDEN,
            )
        
        try:
            # Generate tokens
            tokens = generate_tokens(user.id, user.email)
            
            # Reset failure count on success
            LoginFailureTracker.reset_failures(email)
            
            return Response(
                {
                    "accessToken": tokens["accessToken"],
                    "refreshToken": tokens["refreshToken"],
                    "user": {
                        "id": str(user.id),
                        "email": user.email,
                        "name": user.name,
                    },
                },
                status=status.HTTP_200_OK,
            )
        except Exception:
            logger.exception("Unexpected error during login for email: %s", email)
            return Response(
                {"message": SERVER_ERROR_MESSAGE},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

