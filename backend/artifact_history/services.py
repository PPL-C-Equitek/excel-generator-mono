from artifact_history.models import ArtifactHistory


def create_artifact_history(
    owner,
    original_name,
    custom_name,
    output_json,
    status_processing,
    created_at=None,
):
    create_kwargs = {
        "owner": owner,
        "original_name": original_name,
        "custom_name": custom_name or "",
        "output_json": output_json,
        "status_processing": status_processing,
    }
    if created_at is not None:
        create_kwargs["created_at"] = created_at

    return ArtifactHistory.objects.create(
        **create_kwargs,
    )


def list_artifact_history_for_user(user, limit, offset):
    if not isinstance(limit, int) or limit <= 0:
        raise ValueError("limit must be a positive integer.")
    if not isinstance(offset, int) or offset < 0:
        raise ValueError("offset must be a non-negative integer.")

    return ArtifactHistory.objects.filter(owner=user)[offset: offset + limit]
