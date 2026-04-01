import logging
from datetime import timedelta
from functools import wraps

from django.core.signing import TimestampSigner, SignatureExpired, BadSignature
from django.db import IntegrityError
from api.decorators import rate_limit
from rest_framework import status
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import APIView

from authentication.models import User
from authentication.serializers import RegisterSerializer, VerifyEmailSerializer
from authentication.services import send_verification_email

logger = logging.getLogger(__name__)
REGISTER_SUCCESS_MESSAGE = "Jika email valid, link verifikasi telah dikirim ke kotak masuk Anda."


def apply_rate_limit_to_method(**rate_limit_kwargs):
    """Adapter to apply function-based rate_limit decorator on APIView methods."""

    def decorator(method):
        @wraps(method)
        def wrapped(self, request, *args, **kwargs):
            @rate_limit(**rate_limit_kwargs)
            def method_wrapper(inner_request, *_args, **_kwargs):
                return method(self, inner_request, *args, **kwargs)

            return method_wrapper(request)

        return wrapped

    return decorator


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
    @apply_rate_limit_to_method(max_requests=5, per="15min")
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

        try:
            existing_user_qs = User.objects.filter(email=email)
            if existing_user_qs.exists():
                existing_user = existing_user_qs.first()
                if existing_user and existing_user.status != "verified":
                    send_verification_email(existing_user.email)

                return Response(
                    {"message": REGISTER_SUCCESS_MESSAGE},
                    status=status.HTTP_200_OK,
                )

            user = User.objects.create_user(
                name=name,
                email=email,
                status="unverified",
            )
            user.set_unusable_password()
            user.save(update_fields=["password"])

            send_verification_email(user.email)

            return Response(
                {"message": REGISTER_SUCCESS_MESSAGE},
                status=status.HTTP_200_OK,
            )
        except IntegrityError:
            return Response(
                {"message": REGISTER_SUCCESS_MESSAGE},
                status=status.HTTP_200_OK,
            )
        except Exception:
            logger.exception("Unexpected error during user registration.")
            return Response(
                {"message": "An internal server error occurred"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


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
