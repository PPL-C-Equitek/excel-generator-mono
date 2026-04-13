import uuid
from unittest.mock import patch, MagicMock

from django.core.cache import cache
from django.db import IntegrityError
from rest_framework.test import APISimpleTestCase, APITestCase
from rest_framework import status

from authentication.models import User


class RegisterViewTest(APISimpleTestCase):
    def setUp(self):
        cache.clear()
        self.url = "/auth/register/"
        self.success_message = "Jika email valid, link verifikasi telah dikirim ke kotak masuk Anda."
        self.valid_payload = {
            "name": "John Doe",
            "email": "john@example.com",
        }

    @patch("authentication.register.adapters.send_verification_email")
    @patch("authentication.register.adapters.User")
    def test_register_valid_data_returns_201(self, mock_user_model, mock_send_email):
        mock_user_model.objects.filter.return_value.first.return_value = None

        saved_user = MagicMock()
        saved_user.id = uuid.uuid4()
        saved_user.email = "john@example.com"
        mock_user_model.objects.create_user.return_value = saved_user

        response = self.client.post(self.url, self.valid_payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["message"], self.success_message)

        mock_user_model.objects.create_user.assert_called_once()
        call_kwargs = mock_user_model.objects.create_user.call_args[1]
        self.assertEqual(call_kwargs["status"], "unverified")
        self.assertEqual(call_kwargs["name"], "John Doe")
        self.assertEqual(call_kwargs["email"], "john@example.com")

    @patch("authentication.register.adapters.send_verification_email")
    @patch("authentication.register.adapters.User")
    def test_register_sends_verification_email(self, mock_user_model, mock_send_email):
        mock_user_model.objects.filter.return_value.first.return_value = None

        saved_user = MagicMock()
        saved_user.id = uuid.uuid4()
        saved_user.email = "john@example.com"
        mock_user_model.objects.create_user.return_value = saved_user

        response = self.client.post(self.url, self.valid_payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        mock_send_email.assert_called_once_with(saved_user.email)

    @patch("authentication.register.adapters.send_verification_email")
    @patch("authentication.register.adapters.User")
    def test_register_normalizes_email(self, mock_user_model, mock_send_email):
        mock_user_model.objects.filter.return_value.first.return_value = None

        saved_user = MagicMock()
        saved_user.id = uuid.uuid4()
        saved_user.email = "john@example.com"
        mock_user_model.objects.create_user.return_value = saved_user

        payload = {
            "name": "John Doe",
            "email": "  John@Example.COM  ",
        }
        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["message"], self.success_message)

        mock_user_model.objects.filter.assert_called_once_with(
            email="john@example.com"
        )
        mock_user_model.objects.create_user.assert_called_once()
        call_kwargs = mock_user_model.objects.create_user.call_args[1]
        self.assertEqual(call_kwargs["email"], "john@example.com")
        mock_send_email.assert_called_once()

    @patch("authentication.register.adapters.send_verification_email")
    @patch("authentication.register.adapters.User")
    def test_register_duplicate_email_returns_409_conflict(self, mock_user_model, mock_send_email):
        existing_user = MagicMock()
        existing_user.status = "unverified"
        existing_user.email = "john@example.com"
        mock_user_model.objects.filter.return_value.first.return_value = existing_user

        payload = {
            "name": "John Doe",
            "email": "  JOHN@EXAMPLE.COM  ",
        }

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        mock_user_model.objects.create_user.assert_not_called()
        mock_user_model.objects.filter.assert_called_once_with(email="john@example.com")
        mock_send_email.assert_not_called()

    @patch("authentication.register.adapters.send_verification_email")
    @patch("authentication.register.adapters.User")
    def test_register_duplicate_verified_user_returns_409_conflict_without_resend(
        self, mock_user_model, mock_send_email
    ):
        existing_user = MagicMock()
        existing_user.status = "verified"
        existing_user.email = "john@example.com"

        mock_user_model.objects.filter.return_value.first.return_value = existing_user

        payload = {
            "name": "John Doe",
            "email": "  JOHN@EXAMPLE.COM  ",
        }

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        mock_user_model.objects.filter.assert_called_once_with(email="john@example.com")
        mock_send_email.assert_not_called()
        mock_user_model.objects.create_user.assert_not_called()

    def test_register_invalid_email_returns_400(self):
        payload = {
            "name": "Bad Email",
            "email": "not-an-email",
        }

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_requires_name_and_email_only(self):
        response = self.client.post(self.url, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        payload = {"name": "Only Name"}
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        payload = {"email": "only@example.com"}
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("authentication.register.adapters.User")
    def test_register_server_error_returns_500(self, mock_user_model):
        mock_user_model.objects.filter.return_value.first.side_effect = Exception("DB connection lost")

        response = self.client.post(self.url, self.valid_payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(response.data["message"], "An internal server error occurred")

    @patch("authentication.register.adapters.User")
    def test_register_integrity_error_returns_409_conflict(self, mock_user_model):
        mock_user_model.objects.filter.return_value.first.return_value = None
        mock_user_model.objects.create_user.side_effect = IntegrityError(
            "duplicate key value violates unique constraint"
        )

        response = self.client.post(self.url, self.valid_payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    @patch("authentication.register.adapters.send_verification_email")
    @patch("authentication.register.adapters.User")
    def test_register_rate_limit_returns_429_on_61st_request(
        self, mock_user_model, mock_send_email
    ):
        mock_user_model.objects.filter.return_value.first.return_value = None
        saved_user = MagicMock()
        saved_user.email = "ratelimit@example.com"
        mock_user_model.objects.create_user.return_value = saved_user

        payload = {
            "name": "Rate Limited",
            "email": "ratelimit@example.com",
        }

        for i in range(60):
            response = self.client.post(self.url, payload, format="json")
            self.assertEqual(
                response.status_code,
                status.HTTP_201_CREATED,
                f"Request {i + 1} should succeed but got {response.status_code}",
            )

        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(response["X-RateLimit-Limit"], "60")
        self.assertEqual(response["X-RateLimit-Remaining"], "0")


class UserManagerTest(APISimpleTestCase):
    @patch.object(User, "save")
    def test_create_user_hashes_password_and_sets_defaults(self, mock_save):
        user = User.objects.create_user(
            email="test@example.com",
            name="Test User",
            password="securePass1",
        )

        self.assertEqual(user.email, "test@example.com")
        self.assertEqual(user.name, "Test User")
        self.assertTrue(user.check_password("securePass1"))
        mock_save.assert_called_once()

    def test_create_user_raises_error_when_email_is_empty(self):
        with self.assertRaises(ValueError) as ctx:
            User.objects.create_user(email="", name="No Email")

        self.assertIn("Email is required", str(ctx.exception))

    @patch.object(User, "save")
    def test_create_user_normalizes_email(self, mock_save):
        user = User.objects.create_user(
            email="Test@Example.COM",
            name="Normalize Test",
            password="securePass1",
        )

        self.assertEqual(user.email, "Test@example.com")

    @patch.object(User, "save")
    def test_create_user_without_password(self, mock_save):
        user = User.objects.create_user(
            email="nopwd@example.com",
            name="No Password",
        )

        self.assertFalse(user.check_password("anything"))
        mock_save.assert_called_once()


class UserStrTest(APISimpleTestCase):
    def test_str_returns_email(self):
        user = User(email="repr@example.com", name="Repr User")
        self.assertEqual(str(user), "repr@example.com")


class UnverifiedUserReregistrationFlowTest(APITestCase):
    def setUp(self):
        cache.clear()
        self.url = "/auth/register/"
        self.old_password = "OldPassword#123"
        self.new_password = "NewPassword#456"
        self.user = User.objects.create_user(
            email="pending@example.com",
            name="Pending User",
            password=self.old_password,
            status="unverified",
        )
        self.previous_nonce = self.user.email_verification_nonce

    @patch("authentication.register.adapters.send_verification_email")
    def test_reregister_unverified_user_updates_password_rotates_nonce_resends_email_and_returns_conflict(
        self, mock_send_verification_email
    ):
        response = self.client.post(
            self.url,
            {
                "name": "Pending User",
                "email": "pending@example.com",
                "password": self.new_password,
            },
            format="json",
        )

        self.user.refresh_from_db()

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(
            response.json(),
            {
                "code": "UNVERIFIED_EMAIL",
                "message": "Email registered but unverified. A new link has been sent.",
            },
        )
        self.assertTrue(self.user.check_password(self.new_password))
        self.assertFalse(self.user.check_password(self.old_password))
        self.assertNotEqual(
            self.user.email_verification_nonce,
            self.previous_nonce,
        )
        mock_send_verification_email.assert_called_once_with(self.user.email)
