import uuid
from unittest.mock import patch, MagicMock

from django.db import IntegrityError
from rest_framework.test import APISimpleTestCase
from rest_framework import status

from authentication.models import User


class RegisterViewTest(APISimpleTestCase):
    def setUp(self):
        self.url = "/auth/register/"
        self.valid_payload = {
            "name": "John Doe",
            "email": "john@example.com",
            "password": "securePass1",
        }

    @patch("authentication.views.send_verification_email")
    @patch("authentication.views.User")
    def test_register_valid_data_returns_201(self, mock_user_model, mock_send_email):
        mock_user_model.objects.filter.return_value.exists.return_value = False

        saved_user = MagicMock()
        saved_user.id = uuid.uuid4()
        saved_user.email = "john@example.com"
        mock_user_model.objects.create_user.return_value = saved_user

        response = self.client.post(self.url, self.valid_payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("userId", response.data)
        self.assertEqual(response.data["message"], "Please check your email")

        mock_user_model.objects.create_user.assert_called_once()
        call_kwargs = mock_user_model.objects.create_user.call_args[1]
        self.assertEqual(call_kwargs["status"], "unverified")
        self.assertEqual(call_kwargs["name"], "John Doe")
        self.assertEqual(call_kwargs["email"], "john@example.com")
        self.assertEqual(call_kwargs["password"], "securePass1")

    @patch("authentication.views.send_verification_email")
    @patch("authentication.views.User")
    def test_register_sends_verification_email(self, mock_user_model, mock_send_email):
        mock_user_model.objects.filter.return_value.exists.return_value = False

        saved_user = MagicMock()
        saved_user.id = uuid.uuid4()
        saved_user.email = "john@example.com"
        mock_user_model.objects.create_user.return_value = saved_user

        response = self.client.post(self.url, self.valid_payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        mock_send_email.assert_called_once_with(saved_user.email)

    @patch("authentication.views.User")
    def test_register_normalizes_email(self, mock_user_model):
        mock_user_model.objects.filter.return_value.exists.return_value = True

        payload = {
            "name": "John Doe",
            "email": "  John@Example.COM  ",
            "password": "securePass1",
        }
        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["message"], "Email is already registered")

        mock_user_model.objects.filter.assert_called_once_with(
            email="john@example.com"
        )

    @patch("authentication.views.User")
    def test_register_duplicate_email_returns_409(self, mock_user_model):
        mock_user_model.objects.filter.return_value.exists.return_value = True

        response = self.client.post(self.url, self.valid_payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["message"], "Email is already registered")

    @patch("authentication.views.send_verification_email")
    @patch("authentication.views.User")
    def test_register_password_min_length_returns_201(
        self, mock_user_model, mock_send_email
    ):
        mock_user_model.objects.filter.return_value.exists.return_value = False

        saved_user = MagicMock()
        saved_user.id = uuid.uuid4()
        mock_user_model.objects.create_user.return_value = saved_user

        payload = {
            "name": "Jane Doe",
            "email": "jane@example.com",
            "password": "pass1234",
        }

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("userId", response.data)
        mock_send_email.assert_called_once()

    def test_register_invalid_email_returns_400(self):
        payload = {
            "name": "Bad Email",
            "email": "not-an-email",
            "password": "securePass1",
        }

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_short_password_returns_400(self):
        payload = {
            "name": "Short Pass",
            "email": "short@example.com",
            "password": "abc12",
        }

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_password_without_numbers_returns_400(self):
        payload = {
            "name": "No Numbers",
            "email": "nonum@example.com",
            "password": "abcdefgh",
        }

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_password_without_letters_returns_400(self):
        payload = {
            "name": "No Letters",
            "email": "nolet@example.com",
            "password": "12345678",
        }

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("authentication.views.User")
    def test_register_server_error_returns_500(self, mock_user_model):
        mock_user_model.objects.filter.return_value.exists.return_value = False
        mock_user_model.objects.create_user.side_effect = Exception("DB connection lost")

        response = self.client.post(self.url, self.valid_payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(response.data["message"], "An internal server error occurred")

    @patch("authentication.views.User")
    def test_register_integrity_error_returns_409(self, mock_user_model):
        mock_user_model.objects.filter.return_value.exists.return_value = False
        mock_user_model.objects.create_user.side_effect = IntegrityError(
            "duplicate key value violates unique constraint"
        )

        response = self.client.post(self.url, self.valid_payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["message"], "Email is already registered")


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
