import logging

import bcrypt
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from authentication.models import User
from authentication.serializers import RegisterSerializer

logger = logging.getLogger(__name__)


@api_view(["POST"])
def register(request):
    serializer = RegisterSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {"errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    validated = serializer.validated_data
    name = validated["name"]
    email = validated["email"]
    password = validated["password"]

    if User.objects.filter(email=email).exists():
        return Response(
            {"message": "Email sudah terdaftar"},
            status=status.HTTP_409_CONFLICT,
        )

    try:
        salt = bcrypt.gensalt()
        hashed_password = bcrypt.hashpw(password.encode("utf-8"), salt)

        user = User.objects.create(
            name=name,
            email=email,
            password=hashed_password.decode("utf-8"),
            status="unverified",
        )

        return Response(
            {
                "userId": str(user.id),
                "message": "Cek email Anda",
            },
            status=status.HTTP_201_CREATED,
        )
    except Exception:
        logger.exception("Unexpected error during user registration.")
        return Response(
            {"message": "Terjadi kesalahan pada server"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
