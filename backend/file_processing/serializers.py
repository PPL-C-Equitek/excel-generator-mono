import os

from rest_framework import serializers


class CsvExportRequestSerializer(serializers.Serializer):
    output_json = serializers.JSONField()

    def validate_output_json(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError(
                "Field 'output_json' must be a JSON object."
            )
        if not value:
            raise serializers.ValidationError(
                "Field 'output_json' must not be empty."
            )
        return value


class CsvExportResponseSerializer(serializers.Serializer):
    file_id = serializers.RegexField(r"^csv_[a-zA-Z0-9]+$")
    file_name = serializers.CharField()
    artifact_type = serializers.ChoiceField(choices=["csv", "zip"])
    size_bytes = serializers.IntegerField(min_value=0)
    created_at = serializers.DateTimeField()

    def validate_file_name(self, value):
        if value != os.path.basename(value) or "/" in value or "\\" in value:
            raise serializers.ValidationError(
                "Field 'file_name' must be a safe filename without path separators."
            )
        return value
