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


class PaginatedChatMessageCollectionSerializer(serializers.Serializer):
    count = serializers.IntegerField(min_value=0)
    limit = serializers.IntegerField(min_value=1)
    offset = serializers.IntegerField(min_value=0)
    results = ChatMessageSerializer(many=True)


class PaginatedGeneratedOutputCollectionSerializer(serializers.Serializer):
    count = serializers.IntegerField(min_value=0)
    limit = serializers.IntegerField(min_value=1)
    offset = serializers.IntegerField(min_value=0)
    results = GeneratedOutputSerializer(many=True)


class SessionListItemSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    title = serializers.CharField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()
    last_message_at = serializers.DateTimeField(allow_null=True)
    last_output_at = serializers.DateTimeField(allow_null=True)


class SessionDetailSerializer(SessionListItemSerializer):
    messages = PaginatedChatMessageCollectionSerializer()
    generated_outputs = PaginatedGeneratedOutputCollectionSerializer()


class SessionTitleUpdateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=120)

    def validate_title(self, value):
        trimmed_value = value.strip()
        if not trimmed_value:
            raise serializers.ValidationError("This field may not be blank.")
        return trimmed_value
