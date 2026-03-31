from unittest.mock import MagicMock

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.test import APISimpleTestCase, APIRequestFactory, force_authenticate

from authentication.permissions import IsVerifiedUser


@api_view(["GET"])
@permission_classes([IsAuthenticated, IsVerifiedUser])
def dummy_protected_view(request):
    return Response({"message": "Success!"})


class IsVerifiedUserPermissionTest(APISimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.url = "/dummy-protected-endpoint/"

    def test_unauthenticated_user_returns_401(self):
        request = self.factory.get(self.url)
        
        response = dummy_protected_view(request)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_authenticated_unverified_user_returns_403(self):
        user = MagicMock()
        user.is_authenticated = True
        user.status = "unverified"

        request = self.factory.get(self.url)
        force_authenticate(request, user=user)

        response = dummy_protected_view(request)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_authenticated_verified_user_returns_200(self):
        user = MagicMock()
        user.is_authenticated = True
        user.status = "verified"

        request = self.factory.get(self.url)
        force_authenticate(request, user=user)

        response = dummy_protected_view(request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
