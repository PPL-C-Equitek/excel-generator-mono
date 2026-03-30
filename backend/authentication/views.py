import logging
from datetime import timedelta

from django.core.signing import TimestampSigner, SignatureExpired, BadSignature
from django.db import IntegrityError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import APIView

from authentication.models import User
from authentication.serializers import RegisterSerializer
from authentication.services import send_verification_email

logger = logging.getLogger(__name__)


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
                {"message": "Terjadi kesalahan pada server"},
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
