from artifact_history.models import ArtifactHistory


def create_artifact_history(
    owner,
    file_id,
    original_name,
    custom_name,
    file_name,
    file_type,
    status_processing,
    size_bytes,
    created_at,
):
    return ArtifactHistory.objects.create(
        owner=owner,
        file_id=file_id,
        original_name=original_name,
        custom_name=custom_name,
        file_name=file_name,
        file_type=file_type,
        status_processing=status_processing,
        size_bytes=size_bytes,
        created_at=created_at,
    )


def list_artifact_history_for_user(user, limit, offset):
    if not isinstance(limit, int) or limit <= 0:
        raise ValueError("limit must be a positive integer.")
    if not isinstance(offset, int) or offset < 0:
        raise ValueError("offset must be a non-negative integer.")

    return ArtifactHistory.objects.filter(owner=user)[offset: offset + limit]
