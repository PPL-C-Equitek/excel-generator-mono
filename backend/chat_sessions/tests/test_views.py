from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from authentication.models import User
from chat_sessions.views import (
    session_delete,
    session_detail,
    session_list,
    session_update,
)


class ChatSessionViewTest(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(
            email="owner@example.com",
            name="Owner",
            password="Test12345",
            status="verified",
        )
        self.unverified_user = User.objects.create_user(
            email="pending@example.com",
            name="Pending",
            password="Test12345",
            status="unverified",
        )

    @patch("chat_sessions.views.list_sessions_for_user")
    def test_list_sessions_requires_authentication(self, mock_list_sessions):
        request = self.factory.get("/sessions/")

        response = session_list(request)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        mock_list_sessions.assert_not_called()

    @patch("chat_sessions.views.list_sessions_for_user")
    def test_list_sessions_requires_verified_user(self, mock_list_sessions):
        request = self.factory.get("/sessions/")
        force_authenticate(request, user=self.unverified_user)

        response = session_list(request)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        mock_list_sessions.assert_not_called()

    @patch("chat_sessions.views.list_sessions_for_user")
    def test_list_sessions_returns_serialized_owned_sessions(self, mock_list_sessions):
        stub_session = SimpleNamespace(
            id="123e4567-e89b-12d3-a456-426614174000",
            title="April report",
            created_at="2026-04-21T10:00:00Z",
            updated_at="2026-04-21T10:05:00Z",
            last_message_at=None,
            last_output_at=None,
        )
        mock_list_sessions.return_value = [stub_session]
        request = self.factory.get("/sessions/")
        force_authenticate(request, user=self.user)

        response = session_list(request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["title"], "April report")
        mock_list_sessions.assert_called_once_with(self.user)

    @patch("chat_sessions.views.get_session_for_user")
    def test_session_detail_returns_not_found_when_missing(self, mock_get_session):
        mock_get_session.return_value = None
        request = self.factory.get("/sessions/session-1/")
        force_authenticate(request, user=self.user)

        response = session_detail(request, "session-1")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        mock_get_session.assert_called_once_with(self.user, "session-1")

    @patch("chat_sessions.views.update_session_title")
    @patch("chat_sessions.views.get_session_for_user")
    def test_session_update_rejects_blank_title(self, mock_get_session, mock_update_session_title):
        mock_get_session.return_value = SimpleNamespace(id="session-1", title="Old title")
        request = self.factory.patch(
            "/sessions/session-1/",
            {"title": "   "},
            format="json",
        )
        force_authenticate(request, user=self.user)

        response = session_update(request, "session-1")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        mock_get_session.assert_called_once_with(self.user, "session-1")
        mock_update_session_title.assert_not_called()

    @patch("chat_sessions.views.delete_session")
    @patch("chat_sessions.views.get_session_for_user")
    def test_session_delete_returns_no_content_for_owned_session(self, mock_get_session, mock_delete_session):
        stub_session = SimpleNamespace(id="session-1")
        mock_get_session.return_value = stub_session
        request = self.factory.delete("/sessions/session-1/")
        force_authenticate(request, user=self.user)

        response = session_delete(request, "session-1")

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        mock_get_session.assert_called_once_with(self.user, "session-1")
        mock_delete_session.assert_called_once_with(stub_session)
