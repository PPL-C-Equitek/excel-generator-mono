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
    return value


class RegisterSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150, required=True)
    email = serializers.EmailField(required=True)
    password = serializers.CharField(
        max_length=128,
        required=True,
        write_only=True,
        validators=[validate_password_strength],
    )
