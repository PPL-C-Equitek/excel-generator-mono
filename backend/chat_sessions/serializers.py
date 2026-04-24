from rest_framework import serializers


class ChatMessageSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    role = serializers.CharField()
    content = serializers.CharField()
    thinking_log = serializers.CharField(allow_blank=True)
    created_at = serializers.DateTimeField()


class GeneratedOutputSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    output_json = serializers.JSONField()
    created_at = serializers.DateTimeField()


class SessionListItemSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    title = serializers.CharField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()
    last_message_at = serializers.DateTimeField(allow_null=True)
    last_output_at = serializers.DateTimeField(allow_null=True)


class SessionDetailSerializer(SessionListItemSerializer):
    messages = ChatMessageSerializer(many=True)
    generated_outputs = GeneratedOutputSerializer(many=True)


class SessionTitleUpdateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=120)

    def validate_title(self, value):
        trimmed_value = value.strip()
        if not trimmed_value:
            raise serializers.ValidationError("This field may not be blank.")
        return trimmed_value
