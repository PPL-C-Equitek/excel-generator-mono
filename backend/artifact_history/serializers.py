from rest_framework import serializers

from artifact_history.models import ArtifactHistory

HISTORY_CUSTOM_NAME_MAX_LENGTH = 120


class HistoryItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = ArtifactHistory
        fields = (
            "id",
            "original_name",
            "custom_name",
            "status_processing",
            "created_at",
        )
        read_only_fields = fields


class HistoryRenameSerializer(serializers.ModelSerializer):
    custom_name = serializers.CharField(
        max_length=HISTORY_CUSTOM_NAME_MAX_LENGTH,
        allow_blank=True,
        trim_whitespace=True,
    )

    class Meta:
        model = ArtifactHistory
        fields = ("custom_name",)
