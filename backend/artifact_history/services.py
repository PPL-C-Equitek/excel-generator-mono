from django.db import IntegrityError, transaction

from artifact_history.models import ArtifactHistory, HistoryExportArtifact


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


def create_history_export_artifact(
    history,
    owner,
    requested_format,
    artifact_type,
    file_id,
    file_name,
    created_at=None,
):
    create_kwargs = {
        "history": history,
        "owner": owner,
        "requested_format": requested_format,
        "artifact_type": artifact_type,
        "file_id": file_id,
        "file_name": file_name,
    }
    if created_at is not None:
        create_kwargs["created_at"] = created_at

    try:
        with transaction.atomic():
            return _create_history_export_artifact_record(**create_kwargs)
    except IntegrityError:
        existing_artifact = get_history_export_artifact(
            history=history,
            owner=owner,
            requested_format=requested_format,
        )
        if existing_artifact is None:
            raise
        return existing_artifact


def _create_history_export_artifact_record(**create_kwargs):
    return HistoryExportArtifact.objects.create(**create_kwargs)


def get_history_export_artifact(history, owner, requested_format):
    return (
        HistoryExportArtifact.objects.filter(
            history=history,
            owner=owner,
            requested_format=requested_format,
        )
        .order_by("-created_at", "-id")
        .first()
    )
