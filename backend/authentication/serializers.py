import re

from rest_framework import serializers


def validate_password_strength(value):
    if len(value) < 8:
        raise serializers.ValidationError(
            "Password must be at least 8 characters long"
        )
    if not re.search(r'[a-zA-Z]', value):
        raise serializers.ValidationError(
            "Password must contain at least one letter"
        )
    if not re.search(r'\d', value):
        raise serializers.ValidationError(
            "Password must contain at least one number"
        )
    if not re.search(r'[^A-Za-z0-9]', value):
        raise serializers.ValidationError(
            "Password must contain at least one special character"
        )
    return value


class RegisterSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150, required=True)
    email = serializers.EmailField(required=True)
    password = serializers.CharField(
        max_length=128,
        required=False,
        write_only=True,
        validators=[validate_password_strength],
    )


class EmailRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)


class TokenValidationSerializer(serializers.Serializer):
    token = serializers.CharField(required=True)


class VerifyEmailSerializer(serializers.Serializer):
    token = serializers.CharField(required=True)
    password = serializers.CharField(
        max_length=128,
        required=True,
        write_only=True,
        validators=[validate_password_strength],
    )
    password_confirm = serializers.CharField(
        max_length=128,
        required=True,
        write_only=True,
    )

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError(
                {"password_confirm": "Password confirmation does not match"}
            )
        return attrs


class ResetPasswordSerializer(VerifyEmailSerializer):
    pass


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    password = serializers.CharField(
        max_length=128,
        required=True,
        write_only=True,
    )


class RefreshTokenSerializer(serializers.Serializer):
    refresh_token = serializers.CharField(required=True, write_only=True)
