import uuid
from unittest.mock import patch, MagicMock

from rest_framework.test import APISimpleTestCase
from rest_framework import status

from authentication.models import User


class LoginViewTest(APISimpleTestCase):
    """Test cases for the login endpoint using TDD approach (RED phase)"""
    
    def setUp(self):
        self.url = "/auth/login/"
        self.valid_payload = {
            "email": "user@example.com",
            "password": "securePass1",
        }

    # Input Validation Tests

    def test_login_missing_email_returns_400(self):
        """System should return 400 if email is missing"""
        payload = {
            "password": "securePass1",
        }
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("errors", response.data)

    def test_login_missing_password_returns_400(self):
        """System should return 400 if password is missing"""
        payload = {
            "email": "user@example.com",
        }
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("errors", response.data)

    def test_login_invalid_email_format_returns_400(self):
        """System should return 400 if email format is invalid"""
        payload = {
            "email": "invalid-email",
            "password": "securePass1",
        }
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("errors", response.data)

    def test_login_empty_email_returns_400(self):
        """System should return 400 if email is empty"""
        payload = {
            "email": "",
            "password": "securePass1",
        }
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("errors", response.data)

    def test_login_empty_password_returns_400(self):
        """System should return 400 if password is empty"""
        payload = {
            "email": "user@example.com",
            "password": "",
        }
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("errors", response.data)

    def test_login_extra_fields_are_ignored(self):
        """System should accept and ignore extra fields in request"""
        payload = {
            "email": "user@example.com",
            "password": "securePass1",
            "extra_field": "should_be_ignored",
            "another_field": 123,
        }
        with patch("authentication.views.User") as mock_user_model:
            mock_user = MagicMock()
            mock_user.id = uuid.uuid4()
            mock_user.email = "user@example.com"
            mock_user.name = "User"
            mock_user.status = "verified"
            
            mock_user_model.objects.get.return_value = mock_user
            mock_user.check_password.return_value = True
            
            with patch("authentication.views.generate_tokens") as mock_gen_tokens:
                mock_gen_tokens.return_value = {
                    "accessToken": "access_token",
                    "refreshToken": "refresh_token"
                }
                response = self.client.post(self.url, payload, format="json")
                # Should not return 400 for extra fields
                self.assertNotEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    #  Credential Validation Tests

    @patch("authentication.views.User")
    def test_login_user_not_found_returns_401(self, mock_user_model):
        """System should return 401 if user with email not found"""
        mock_user_model.objects.get.side_effect = User.DoesNotExist()
        
        response = self.client.post(self.url, self.valid_payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn("message", response.data)

    @patch("authentication.views.User")
    def test_login_wrong_password_returns_401(self, mock_user_model):
        """System should return 401 if password is incorrect"""
        mock_user = MagicMock()
        mock_user.id = uuid.uuid4()
        mock_user.email = "user@example.com"
        mock_user.name = "User"
        mock_user.status = "verified"
        mock_user.check_password.return_value = False
        
        mock_user_model.objects.get.return_value = mock_user
        
        response = self.client.post(self.url, self.valid_payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn("message", response.data)
        mock_user.check_password.assert_called_once_with("securePass1")

    # Email Verification Tests

    @patch("authentication.views.User")
    def test_login_unverified_email_returns_403(self, mock_user_model):
        """System should return 403 if email is not verified"""
        mock_user = MagicMock()
        mock_user.id = uuid.uuid4()
        mock_user.email = "user@example.com"
        mock_user.name = "User"
        mock_user.status = "unverified"
        mock_user.check_password.return_value = True
        
        mock_user_model.objects.get.return_value = mock_user
        
        response = self.client.post(self.url, self.valid_payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("message", response.data)
        # Should contain message to check email
        self.assertIn("cek email", response.data["message"].lower())

    # Successful Login Tests

    @patch("authentication.views.User")
    @patch("authentication.views.generate_tokens")
    def test_login_valid_credentials_returns_200(self, mock_gen_tokens, mock_user_model):
        """System should return 200 with tokens if login successful"""
        mock_user = MagicMock()
        mock_user.id = uuid.uuid4()
        mock_user.email = "user@example.com"
        mock_user.name = "John Doe"
        mock_user.status = "verified"
        mock_user.check_password.return_value = True
        
        mock_user_model.objects.get.return_value = mock_user
        mock_gen_tokens.return_value = {
            "accessToken": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
            "refreshToken": "refresh_token_value"
        }
        
        response = self.client.post(self.url, self.valid_payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @patch("authentication.views.User")
    @patch("authentication.views.generate_tokens")
    def test_login_response_contains_access_token(self, mock_gen_tokens, mock_user_model):
        """System should return accessToken in response"""
        mock_user = MagicMock()
        mock_user.id = uuid.uuid4()
        mock_user.email = "user@example.com"
        mock_user.name = "John Doe"
        mock_user.status = "verified"
        mock_user.check_password.return_value = True
        
        mock_user_model.objects.get.return_value = mock_user
        mock_gen_tokens.return_value = {
            "accessToken": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
            "refreshToken": "refresh_token_value"
        }
        
        response = self.client.post(self.url, self.valid_payload, format="json")
        self.assertIn("accessToken", response.data)
        self.assertEqual(response.data["accessToken"], "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...")

    @patch("authentication.views.User")
    @patch("authentication.views.generate_tokens")
    def test_login_response_contains_refresh_token(self, mock_gen_tokens, mock_user_model):
        """System should return refreshToken in response"""
        mock_user = MagicMock()
        mock_user.id = uuid.uuid4()
        mock_user.email = "user@example.com"
        mock_user.name = "John Doe"
        mock_user.status = "verified"
        mock_user.check_password.return_value = True
        
        mock_user_model.objects.get.return_value = mock_user
        mock_gen_tokens.return_value = {
            "accessToken": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
            "refreshToken": "refresh_token_value"
        }
        
        response = self.client.post(self.url, self.valid_payload, format="json")
        self.assertIn("refreshToken", response.data)
        self.assertEqual(response.data["refreshToken"], "refresh_token_value")

    @patch("authentication.views.User")
    @patch("authentication.views.generate_tokens")
    def test_login_response_contains_user_data(self, mock_gen_tokens, mock_user_model):
        """System should return user data in response"""
        user_id = uuid.uuid4()
        mock_user = MagicMock()
        mock_user.id = user_id
        mock_user.email = "user@example.com"
        mock_user.name = "John Doe"
        mock_user.status = "verified"
        mock_user.check_password.return_value = True
        
        mock_user_model.objects.get.return_value = mock_user
        mock_gen_tokens.return_value = {
            "accessToken": "access_token",
            "refreshToken": "refresh_token"
        }
        
        response = self.client.post(self.url, self.valid_payload, format="json")
        self.assertIn("user", response.data)
        self.assertEqual(response.data["user"]["id"], str(user_id))
        self.assertEqual(response.data["user"]["email"], "user@example.com")
        self.assertEqual(response.data["user"]["name"], "John Doe")

    @patch("authentication.views.User")
    @patch("authentication.views.generate_tokens")
    def test_login_normalizes_email(self, mock_gen_tokens, mock_user_model):
        """System should normalize email (lowercase, strip whitespace) before querying"""
        payload = {
            "email": "  USER@Example.COM  ",
            "password": "securePass1",
        }
        
        mock_user = MagicMock()
        mock_user.id = uuid.uuid4()
        mock_user.email = "user@example.com"
        mock_user.name = "User"
        mock_user.status = "verified"
        mock_user.check_password.return_value = True
        
        mock_user_model.objects.get.return_value = mock_user
        mock_gen_tokens.return_value = {
            "accessToken": "token",
            "refreshToken": "refresh"
        }
        
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Verify that get was called with normalized email
        mock_user_model.objects.get.assert_called()
        call_kwargs = mock_user_model.objects.get.call_args[1]
        self.assertEqual(call_kwargs["email"], "user@example.com")

    # Rate Limiting Tests

    @patch("authentication.views.LoginFailureTracker")
    @patch("authentication.views.User")
    def test_login_rate_limiting_blocks_after_5_failed_attempts(self, mock_user_model, mock_tracker):
        """System should block after 5 failed attempts within 15 minutes"""
        mock_tracker.is_rate_limited.return_value = True
        
        response = self.client.post(self.url, self.valid_payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertIn("message", response.data)

    @patch("authentication.views.LoginFailureTracker")
    @patch("authentication.views.User")
    def test_login_rate_limiting_message_on_exceed_limit(self, mock_user_model, mock_tracker):
        """System should return appropriate message when rate limit exceeded"""
        mock_tracker.is_rate_limited.return_value = True
        
        response = self.client.post(self.url, self.valid_payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertIn("Terlalu banyak percobaan", response.data["message"])

    @patch("authentication.views.LoginFailureTracker")
    @patch("authentication.views.User")
    def test_login_tracks_failed_attempts(self, mock_user_model, mock_tracker):
        """System should track failed login attempts"""
        mock_user_model.objects.get.side_effect = User.DoesNotExist()
        mock_tracker.is_rate_limited.return_value = False
        
        response = self.client.post(self.url, self.valid_payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        # Verify that tracker was called
        mock_tracker.record_failure.assert_called()

    @patch("authentication.views.LoginFailureTracker")
    @patch("authentication.views.User")
    @patch("authentication.views.generate_tokens")
    def test_login_resets_failure_count_on_success(self, mock_gen_tokens, mock_user_model, mock_tracker):
        """System should reset failure count on successful login"""
        mock_user = MagicMock()
        mock_user.id = uuid.uuid4()
        mock_user.email = "user@example.com"
        mock_user.name = "User"
        mock_user.status = "verified"
        mock_user.check_password.return_value = True
        
        mock_user_model.objects.get.return_value = mock_user
        mock_gen_tokens.return_value = {
            "accessToken": "token",
            "refreshToken": "refresh"
        }
        mock_tracker.is_rate_limited.return_value = False
        
        response = self.client.post(self.url, self.valid_payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Verify that tracker reset was called
        mock_tracker.reset_failures.assert_called()

    # Error Handling Tests

    @patch("authentication.views.User")
    def test_login_unexpected_error_returns_500(self, mock_user_model):
        """System should return 500 on unexpected internal error"""
        mock_user_model.objects.get.side_effect = Exception("Database connection error")
        
        response = self.client.post(self.url, {
            "email": "user@example.com",
            "password": "securePass1"
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn("message", response.data)

    @patch("authentication.views.generate_tokens")
    @patch("authentication.views.User")
    def test_login_token_generation_error_returns_500(self, mock_user_model, mock_gen_tokens):
        """System should return 500 if token generation fails"""
        mock_user = MagicMock()
        mock_user.id = uuid.uuid4()
        mock_user.email = "user@example.com"
        mock_user.name = "User"
        mock_user.status = "verified"
        mock_user.check_password.return_value = True
        
        mock_user_model.objects.get.return_value = mock_user
        mock_gen_tokens.side_effect = Exception("JWT encoding error")
        
        response = self.client.post(self.url, self.valid_payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)

    # Additional Edge Case Tests

    @patch("authentication.views.User")
    def test_login_case_insensitive_email_lookup(self, mock_user_model):
        """System should treat email lookup as case-insensitive"""
        payload = {
            "email": "USER@EXAMPLE.COM",
            "password": "securePass1",
        }
        
        mock_user = MagicMock()
        mock_user.id = uuid.uuid4()
        mock_user.email = "user@example.com"
        mock_user.name = "User"
        mock_user.status = "verified"
        mock_user.check_password.return_value = True
        
        mock_user_model.objects.get.return_value = mock_user
        
        with patch("authentication.views.generate_tokens") as mock_gen_tokens:
            mock_gen_tokens.return_value = {
                "accessToken": "token",
                "refreshToken": "refresh"
            }
            response = self.client.post(self.url, payload, format="json")
            self.assertEqual(response.status_code, status.HTTP_200_OK)

    @patch("authentication.views.User")
    def test_login_only_post_method_allowed(self, mock_user_model):
        """System should only allow POST method on login endpoint"""
        # GET should not be allowed
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        
        # PUT should not be allowed
        response = self.client.put(self.url, self.valid_payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        
        # DELETE should not be allowed
        response = self.client.delete(self.url)
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    @patch("authentication.views.User")
    @patch("authentication.views.generate_tokens")
    def test_login_user_data_does_not_include_password(self, mock_gen_tokens, mock_user_model):
        """System should not include password in user data response"""
        mock_user = MagicMock()
        mock_user.id = uuid.uuid4()
        mock_user.email = "user@example.com"
        mock_user.name = "John Doe"
        mock_user.status = "verified"
        mock_user.check_password.return_value = True
        
        mock_user_model.objects.get.return_value = mock_user
        mock_gen_tokens.return_value = {
            "accessToken": "token",
            "refreshToken": "refresh"
        }
        
        response = self.client.post(self.url, self.valid_payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn("password", response.data.get("user", {}))

    @patch("authentication.views.User")
    def test_login_invalid_json_returns_400(self, mock_user_model):
        """System should return 400 for invalid JSON"""
        response = self.client.post(
            self.url,
            "{invalid json}",
            content_type="application/json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
