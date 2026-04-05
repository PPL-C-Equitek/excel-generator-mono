from __future__ import annotations

import logging
from functools import wraps

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from api.decorators import rate_limit
from authentication.register import RegisterCommand, RegistrationServiceError, build_register_user_use_case
from authentication.serializers import RegisterSerializer

logger = logging.getLogger(__name__)


def apply_rate_limit_to_method(**rate_limit_kwargs):
    """Adapter to apply the function-based rate-limit decorator to APIView methods."""

    def decorator(method):
        @wraps(method)
        def wrapped(self, request, *args, **kwargs):
            @rate_limit(**rate_limit_kwargs)
            def method_wrapper(inner_request, *_args, **_kwargs):
                return method(self, inner_request, *args, **kwargs)

            return method_wrapper(request)

        return wrapped

    return decorator


class RegisterView(APIView):
    def get_register_use_case(self):
        return build_register_user_use_case()

    @apply_rate_limit_to_method(max_requests=60, per="minute")
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            validated = serializer.validated_data
            result = self.get_register_use_case().execute(
                RegisterCommand(
                    name=validated["name"],
                    email=validated["email"],
                )
            )
            return Response(
                {"message": result.message},
                status=status.HTTP_200_OK,
            )
        except RegistrationServiceError:
            logger.exception("Unexpected error during user registration.")
            return Response(
                {"message": "An internal server error occurred"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except Exception:
            logger.exception("Unhandled error during user registration.")
            return Response(
                {"message": "An internal server error occurred"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
