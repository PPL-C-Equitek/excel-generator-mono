import logging
from datetime import timedelta
from django.core.cache import cache
from django.core.exceptions import ObjectDoesNotExist

from django.core.signing import TimestampSigner, SignatureExpired, BadSignature
from django.db import IntegrityError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import APIView

from authentication.models import User
from authentication.serializers import RegisterSerializer, LoginSerializer
from authentication.services import send_verification_email, generate_tokens

logger = logging.getLogger(__name__)
SERVER_ERROR_MESSAGE = "Terjadi kesalahan pada server"


class ResendVerificationThrottle(SimpleRateThrottle):
    scope = "resend_verification"
    rate = "3/15min"

    def get_cache_key(self, request, view):
        email = request.data.get("email", "")
        ident = email.lower().strip() if email else self.get_ident(request)
        return self.cache_format % {"scope": self.scope, "ident": ident}

    def parse_rate(self, rate):
        return (3, 900)


class RegisterView(APIView):
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        validated = serializer.validated_data
        name = validated["name"]
        email = validated["email"].lower().strip()
        password = validated["password"]

        if User.objects.filter(email=email).exists():
            return Response(
                {"message": "Email sudah terdaftar"},
                status=status.HTTP_409_CONFLICT,
            )

        try:
            user = User.objects.create_user(
                name=name,
                email=email,
                password=password,
                status="unverified",
            )

            send_verification_email(user.email)

            return Response(
                {
                    "userId": str(user.id),
                    "message": "Cek email Anda",
                },
                status=status.HTTP_201_CREATED,
            )
        except IntegrityError:
            return Response(
                {"message": "Email sudah terdaftar"},
                status=status.HTTP_409_CONFLICT,
            )
        except Exception:
            logger.exception("Unexpected error during user registration.")
            return Response(
                {"message": SERVER_ERROR_MESSAGE},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class VerifyEmailView(APIView):
    def get(self, request):
        token = request.query_params.get("token")
        if not token:
            return Response(
                {"message": "Token tidak ditemukan"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        signer = TimestampSigner()
        try:
            email = signer.unsign(token, max_age=timedelta(hours=24))
        except SignatureExpired:
            return Response(
                {"message": "Token expired. Silakan minta verifikasi ulang."},
                status=status.HTTP_410_GONE,
            )
        except BadSignature:
            return Response(
                {"message": "Token tidak valid"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                {"message": "User tidak ditemukan"},
                status=status.HTTP_404_NOT_FOUND,
            )

        user.status = "verified"
        user.save()

        return Response(
            {"message": "Email berhasil diverifikasi"},
            status=status.HTTP_200_OK,
        )


class ResendVerificationView(APIView):
    throttle_classes = [ResendVerificationThrottle]

    def post(self, request):
        email = request.data.get("email")
        if not email:
            return Response(
                {"message": "Email harus diisi"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                {"message": "User tidak ditemukan"},
                status=status.HTTP_404_NOT_FOUND,
            )

        if user.status == "verified":
            return Response(
                {"message": "Email sudah diverifikasi"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        send_verification_email(user.email)

        return Response(
            {"message": "Email verifikasi telah dikirim ulang"},
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
        """Record a failed login attempt"""
        cache_key = cls.get_cache_key(email)
        failures = cache.get(cache_key, 0)
        cache.set(cache_key, failures + 1, cls.TIME_WINDOW)
    
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

