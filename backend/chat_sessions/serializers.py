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
    thinking_log = serializers.CharField(allow_blank=True)
    created_at = serializers.DateTimeField()


class ResumeHistoryMessageSerializer(serializers.Serializer):
    type = serializers.CharField()
    id = serializers.UUIDField()
    role = serializers.CharField()
    content = serializers.CharField()
    thinking_log = serializers.CharField(allow_blank=True)
    created_at = serializers.DateTimeField()


class ResumeHistoryOutputSerializer(serializers.Serializer):
    type = serializers.CharField()
    id = serializers.UUIDField()
    output_json = serializers.JSONField()
    thinking_log = serializers.CharField(allow_blank=True)
    created_at = serializers.DateTimeField()


class ResumeHistoryItemSerializer(serializers.Serializer):
    def to_representation(self, instance):
        item_type = getattr(instance, "type", None)
        if item_type == "message":
            return ResumeHistoryMessageSerializer(instance).data
        if item_type == "output":
            return ResumeHistoryOutputSerializer(instance).data
        raise serializers.ValidationError("Unsupported resume history item type.")


class PaginatedCollectionSerializer(serializers.Serializer):
    count = serializers.IntegerField(min_value=0)
    limit = serializers.IntegerField(min_value=1)
    offset = serializers.IntegerField(min_value=0)


class PaginatedChatMessageCollectionSerializer(PaginatedCollectionSerializer):
    results = ChatMessageSerializer(many=True)


class PaginatedGeneratedOutputCollectionSerializer(PaginatedCollectionSerializer):
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


class SessionResumeSerializer(SessionListItemSerializer):
    history = ResumeHistoryItemSerializer(many=True)


class SessionTitleUpdateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=120)

    def validate_title(self, value):
        trimmed_value = value.strip()
        if not trimmed_value:
            raise serializers.ValidationError("This field may not be blank.")
        return trimmed_value
