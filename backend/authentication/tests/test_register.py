import uuid
from unittest.mock import patch, MagicMock

from rest_framework.test import APISimpleTestCase
from rest_framework import status


class RegisterViewTest(APISimpleTestCase):
    def setUp(self):
        self.url = "/auth/register/"
        self.valid_payload = {
            "name": "John Doe",
            "email": "john@example.com",
            "password": "securePass1",
        }

    @patch("authentication.views.User")
    @patch("authentication.views.bcrypt")
    def test_register_valid_data_returns_201(self, mock_bcrypt, mock_user_model):
        mock_user_model.objects.filter.return_value.exists.return_value = False
        mock_bcrypt.hashpw.return_value = b"$2b$12$hashedpassword"
        mock_bcrypt.gensalt.return_value = b"$2b$12$salt"

        saved_user = MagicMock()
        saved_user.id = uuid.uuid4()
        mock_user_model.objects.create.return_value = saved_user

        response = self.client.post(self.url, self.valid_payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("userId", response.data)
        self.assertEqual(response.data["message"], "Cek email Anda")

        mock_bcrypt.gensalt.assert_called_once()
        mock_bcrypt.hashpw.assert_called_once()

        mock_user_model.objects.create.assert_called_once()
        call_kwargs = mock_user_model.objects.create.call_args[1]
        self.assertEqual(call_kwargs["status"], "unverified")
        self.assertEqual(call_kwargs["name"], "John Doe")
        self.assertEqual(call_kwargs["email"], "john@example.com")

    @patch("authentication.views.User")
    def test_register_duplicate_email_returns_409(self, mock_user_model):
        mock_user_model.objects.filter.return_value.exists.return_value = True

        response = self.client.post(self.url, self.valid_payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["message"], "Email sudah terdaftar")

    @patch("authentication.views.User")
    @patch("authentication.views.bcrypt")
    def test_register_password_min_length_returns_201(
        self, mock_bcrypt, mock_user_model
    ):
        mock_user_model.objects.filter.return_value.exists.return_value = False
        mock_bcrypt.hashpw.return_value = b"$2b$12$hashedpassword"
        mock_bcrypt.gensalt.return_value = b"$2b$12$salt"

        saved_user = MagicMock()
        saved_user.id = uuid.uuid4()
        mock_user_model.objects.create.return_value = saved_user

        payload = {
            "name": "Jane Doe",
            "email": "jane@example.com",
            "password": "pass1234",
        }

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("userId", response.data)

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
    @patch("authentication.views.bcrypt")
    def test_register_server_error_returns_500(self, mock_bcrypt, mock_user_model):
        mock_user_model.objects.filter.return_value.exists.return_value = False
        mock_bcrypt.hashpw.return_value = b"$2b$12$hashedpassword"
        mock_bcrypt.gensalt.return_value = b"$2b$12$salt"

        mock_user_model.objects.create.side_effect = Exception("DB connection lost")

        response = self.client.post(self.url, self.valid_payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(response.data["message"], "Terjadi kesalahan pada server")
