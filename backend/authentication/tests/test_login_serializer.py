from rest_framework.test import APISimpleTestCase

from authentication.serializers import LoginSerializer


class LoginSerializerTest(APISimpleTestCase):
    # Positive
    def test_serializer_accepts_valid_payload(self):
        serializer = LoginSerializer(
            data={
                "email": "user@example.com",
                "password": "securePass#123",
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["email"], "user@example.com")
        self.assertEqual(serializer.validated_data["password"], "securePass#123")

    # Negative
    def test_serializer_rejects_empty_payload(self):
        serializer = LoginSerializer(data={})

        self.assertFalse(serializer.is_valid())
        self.assertIn("email", serializer.errors)
        self.assertIn("password", serializer.errors)

    def test_serializer_rejects_invalid_email_format(self):
        serializer = LoginSerializer(
            data={
                "email": "invalid-email",
                "password": "securePass#123",
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("email", serializer.errors)

    def test_serializer_rejects_blank_email(self):
        serializer = LoginSerializer(
            data={
                "email": "",
                "password": "securePass#123",
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("email", serializer.errors)

    def test_serializer_rejects_blank_password(self):
        serializer = LoginSerializer(
            data={
                "email": "user@example.com",
                "password": "",
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("password", serializer.errors)

    # Edge Case
    def test_serializer_rejects_password_over_max_length(self):
        serializer = LoginSerializer(
            data={
                "email": "user@example.com",
                "password": "x" * 129,
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("password", serializer.errors)
