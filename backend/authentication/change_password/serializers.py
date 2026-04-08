from __future__ import annotations

from rest_framework import serializers

from authentication.change_password.entities import ChangePasswordCommand
from authentication.models import User
from authentication.serializers import validate_password_strength


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(
        max_length=128,
        required=False,
        allow_blank=True,
        write_only=True,
    )
    new_password = serializers.CharField(
        max_length=128,
        required=True,
        write_only=True,
        validators=[validate_password_strength],
    )
    new_password_confirm = serializers.CharField(
        max_length=128,
        required=True,
        write_only=True,
    )
    refresh_token = serializers.CharField(
        required=False,
        allow_blank=True,
        write_only=True,
    )

    def validate(self, attrs):
        if attrs["new_password"] != attrs["new_password_confirm"]:
            raise serializers.ValidationError(
                {"new_password_confirm": "Password confirmation does not match"}
            )
        return attrs

    def to_command(self, user: User) -> ChangePasswordCommand:
        return ChangePasswordCommand(
            user=user,
            current_password=self.validated_data.get("current_password", ""),
            new_password=self.validated_data["new_password"],
            refresh_token=self.validated_data.get("refresh_token") or None,
        )
