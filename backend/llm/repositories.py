from typing import Optional

from chat_sessions.models import GeneratedOutput


def get_thinking_log_queryset_for_user(user):
    """Return a base queryset of GeneratedOutput for `user` excluding empty thinking_log."""
    return GeneratedOutput.objects.filter(session__owner=user).exclude(thinking_log="")


def get_generated_output_for_user_by_id(user, output_id) -> Optional[GeneratedOutput]:
    try:
        return GeneratedOutput.objects.get(id=output_id, session__owner=user)
    except GeneratedOutput.DoesNotExist:
        return None
