import os
import logging
from dataclasses import dataclass

from django.conf import settings
from django.core.exceptions import SuspiciousFileOperation
from django.http import FileResponse
from django.utils._os import safe_join
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView
from .models import GroupMember
from artifact_history.serializers import HistoryItemSerializer, HistoryRenameSerializer
from artifact_history.services import (
    delete_artifact_history,
    get_artifact_history_for_user,
    create_history_export_artifact,
    get_history_export_artifact,
    list_artifact_history_for_user,
    update_artifact_history_custom_name,
)
from authentication.permissions import IsVerifiedUser
from chat_sessions.serializers import (
    SessionDetailSerializer,
    SessionListItemSerializer,
    SessionResumeSerializer,
    SessionTitleUpdateSerializer,
)
from chat_sessions.services import (
    build_resume_context_for_user,
    delete_session,
    get_generated_output_for_session_user,
    get_default_session_detail_pagination,
    get_paginated_session_detail_for_user,
    get_session_for_user,
    list_sessions_for_user,
    SESSION_DETAIL_MAX_LIMIT,
    SESSION_DETAIL_LIMIT_FIELDS,
    SESSION_DETAIL_OFFSET_FIELDS,
    SESSION_LIST_DEFAULT_LIMIT,
    SESSION_LIST_MAX_LIMIT,
    update_session_title,
    validate_session_detail_pagination_params as validate_session_detail_pagination_params_service,
)
from file_processing.services.upload_service import (
    FILE_TOO_LARGE_ERROR,
    MAX_FILE_SIZE,
    process_upload,
)
from file_processing.serializers import (
    CsvExportRequestSerializer,
    CsvExportResponseSerializer,
    ExcelExportRequestSerializer,
    ExcelExportResponseSerializer,
)
from file_processing.services.export_service import (
    OutputCSVDownloadLookupError,
    OutputCSVGenerationError,
    OutputCSVMappingError,
    OutputExcelDownloadLookupError,
    OutputExcelDownloadStorageError,
    OutputExcelGenerationError,
    OutputLLMValidationError,
    export_csv_to_filesystem,
    export_excel_to_filesystem,
    resolve_csv_download_artifact,
    resolve_excel_download_artifact,
)
from llm.services.export_service import build_export_output_json

logger = logging.getLogger(__name__)
MAX_MULTIPART_OVERHEAD_BYTES = 256 * 1024  # multipart headers + boundaries
NOT_FOUND_DETAIL = "Not found."
INVALID_SESSION_LIST_PAGINATION_DETAIL = "Invalid session list pagination."
INVALID_SESSION_DETAIL_PAGINATION_DETAIL = "Invalid session detail pagination."
CSV_FILE_NOT_FOUND_MESSAGE = "CSV file not found."
CSV_DOWNLOAD_INTERNAL_ERROR_MESSAGE = "Failed to download CSV due to internal error."
EXCEL_FILE_NOT_FOUND_MESSAGE = "Excel file not found."
EXCEL_DOWNLOAD_INTERNAL_ERROR_MESSAGE = "Failed to download Excel due to internal error."
SESSION_LIST_PAGINATION_ERROR_DETAILS = {
    "limit must be an integer.",
    "offset must be an integer.",
    "offset must be greater than or equal to 0.",
    "limit must be greater than 0.",
    f"limit must be less than or equal to {SESSION_LIST_MAX_LIMIT}.",
}
SESSION_DETAIL_PAGINATION_ERROR_DETAILS = {
    f"{field} must be an integer."
    for field in (*SESSION_DETAIL_LIMIT_FIELDS, *SESSION_DETAIL_OFFSET_FIELDS)
} | {
    "messages_limit must be greater than 0.",
    f"messages_limit must be less than or equal to {SESSION_DETAIL_MAX_LIMIT}.",
    "messages_offset must be greater than or equal to 0.",
    "outputs_limit must be greater than 0.",
    f"outputs_limit must be less than or equal to {SESSION_DETAIL_MAX_LIMIT}.",
    "outputs_offset must be greater than or equal to 0.",
}


class SessionListPaginationError(Exception):
    def __init__(self, detail):
        super().__init__(detail)
        self.detail = detail


class SessionDetailPaginationError(Exception):
    def __init__(self, detail):
        super().__init__(detail)
        self.detail = detail


def _parse_session_list_pagination(request):
    limit_param = request.query_params.get("limit")
    offset_param = request.query_params.get("offset")

    if limit_param is None:
        limit = SESSION_LIST_DEFAULT_LIMIT
    else:
        try:
            limit = int(limit_param)
        except (TypeError, ValueError):
            raise SessionListPaginationError("limit must be an integer.")

    if offset_param is None:
        offset = 0
    else:
        try:
            offset = int(offset_param)
        except (TypeError, ValueError):
            raise SessionListPaginationError("offset must be an integer.")

    if offset < 0:
        raise SessionListPaginationError("offset must be greater than or equal to 0.")

    return limit, offset


def _build_session_list_pagination_error_response(detail):
    safe_detail = (
        detail
        if detail in SESSION_LIST_PAGINATION_ERROR_DETAILS
        else INVALID_SESSION_LIST_PAGINATION_DETAIL
    )
    return Response({"detail": safe_detail}, status=status.HTTP_400_BAD_REQUEST)


def _parse_session_detail_pagination(request):
    pagination = get_default_session_detail_pagination()
    for name, default in pagination.items():
        pagination[name] = _parse_session_detail_int_param(
            request,
            name,
            default=default,
        )
    _validate_session_detail_pagination_params(pagination)
    return pagination


def _parse_session_detail_int_param(request, name, default):
    value = request.query_params.get(name)
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        raise SessionDetailPaginationError(f"{name} must be an integer.")

def _validate_session_detail_pagination_params(pagination):
    try:
        validate_session_detail_pagination_params_service(pagination)
    except ValueError as exc:
        detail = exc.args[0] if exc.args else INVALID_SESSION_DETAIL_PAGINATION_DETAIL
        raise SessionDetailPaginationError(detail) from exc


def _build_session_detail_pagination_error_response(detail):
    safe_detail = (
        detail
        if detail in SESSION_DETAIL_PAGINATION_ERROR_DETAILS
        else INVALID_SESSION_DETAIL_PAGINATION_DETAIL
    )
    return Response({"detail": safe_detail}, status=status.HTTP_400_BAD_REQUEST)


def _sanitize_download_filename(candidate):
    if not isinstance(candidate, str):
        return None

    normalized = candidate.strip().replace("\r", "").replace("\n", "")
    if not normalized:
        return None
    if "\x00" in normalized:
        return None

    basename = os.path.basename(normalized)
    if basename in {"", ".", ".."}:
        return None
    if basename != normalized:
        return None

    return basename


def _resolve_download_filename(requested_name, default_name, artifact_type):
    safe_name = _sanitize_download_filename(requested_name)
    if not safe_name:
        return default_name

    if artifact_type == "zip":
        expected_ext = ".zip"
    elif artifact_type == "xlsx":
        expected_ext = ".xlsx"
    else:
        expected_ext = ".csv"
    root, ext = os.path.splitext(safe_name)
    if ext.lower() != expected_ext:
        if ext:
            return f"{root}{expected_ext}"
        return f"{safe_name}{expected_ext}"

    return safe_name


def _is_invalid_excel_download_id_error(error):
    return "format is invalid" in str(error).lower()


def _build_download_error_response(message, status_code):
    return Response(
        {
            "status": "error",
            "message": message,
        },
        status=status_code,
    )


def _excel_download_not_found_response():
    return _build_download_error_response(
        EXCEL_FILE_NOT_FOUND_MESSAGE,
        status.HTTP_404_NOT_FOUND,
    )


def _excel_download_internal_error_response():
    return _build_download_error_response(
        EXCEL_DOWNLOAD_INTERNAL_ERROR_MESSAGE,
        status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


@dataclass(frozen=True)
class SessionOutputDownloadConfig:
    export_callable: callable
    storage_dir: str
    artifact_type: str
    validation_error_types: tuple[type[Exception], ...]
    generation_error_types: tuple[type[Exception], ...]
    invalid_request_message: str
    internal_error_message: str
    validation_log_message: str
    generation_log_message: str
    unexpected_log_message: str
    not_found_message: str
    download_internal_error_message: str


def _history_not_found_response():
    return Response(
        {
            "status": "error",
            "message": "History item not found.",
        },
        status=status.HTTP_404_NOT_FOUND,
    )


def _history_download_internal_error_response():
    return Response(
        {
            "status": "error",
            "message": "Failed to download history file due to internal error.",
        },
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


def _history_delete_internal_error_response():
    return Response(
        {
            "status": "error",
            "message": "Failed to delete history item due to internal error.",
        },
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


def _get_owned_history_or_not_found(user, history_id):
    history = get_artifact_history_for_user(user, history_id)
    if history is None:
        return None, _history_not_found_response()
    return history, None


def _get_history_download_storage_dir(artifact_type):
    if artifact_type == "xlsx":
        return settings.EXCEL_EXPORT_DIR
    return settings.CSV_EXPORT_DIR


def _get_history_download_content_type(artifact_type):
    if artifact_type == "zip":
        return "application/zip"
    if artifact_type == "xlsx":
        return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return "text/csv"


def _generate_history_download_artifact(history, owner, file_format):
    if file_format == "csv":
        artifact = export_csv_to_filesystem(
            output_json=history.output_json,
            storage_dir=settings.CSV_EXPORT_DIR,
        )
        safe_file_path = safe_join(settings.CSV_EXPORT_DIR, artifact["file_name"])
    else:
        artifact = export_excel_to_filesystem(
            output_json=history.output_json,
            storage_dir=settings.EXCEL_EXPORT_DIR,
        )
        safe_file_path = safe_join(settings.EXCEL_EXPORT_DIR, artifact["file_name"])

    cached_artifact = create_history_export_artifact(
        history=history,
        owner=owner,
        requested_format=file_format,
        artifact_type=artifact["artifact_type"],
        file_id=artifact["file_id"],
        file_name=artifact["file_name"],
        created_at=artifact.get("created_at"),
    )

    if (
        cached_artifact.file_name != artifact["file_name"]
        or cached_artifact.artifact_type != artifact["artifact_type"]
    ):
        try:
            os.remove(safe_file_path)
        except OSError:
            logger.warning("Failed to delete orphaned history download artifact.", exc_info=True)

    resolved_file_path = safe_join(
        _get_history_download_storage_dir(cached_artifact.artifact_type),
        cached_artifact.file_name,
    )
    return cached_artifact.file_name, cached_artifact.artifact_type, resolved_file_path


def _resolve_history_download_artifact(history, owner, file_format):
    cached_artifact = get_history_export_artifact(
        history=history,
        owner=owner,
        requested_format=file_format,
    )
    if cached_artifact is not None:
        file_name = cached_artifact.file_name
        artifact_type = cached_artifact.artifact_type
        safe_file_path = safe_join(
            _get_history_download_storage_dir(artifact_type),
            file_name,
        )
        return file_name, artifact_type, safe_file_path, True

    file_name, artifact_type, safe_file_path = _generate_history_download_artifact(
        history,
        owner,
        file_format,
    )
    return file_name, artifact_type, safe_file_path, False


def _regenerate_history_download_artifact_after_stale_cache(history, owner, file_format):
    history_export_artifact_model = history.export_artifacts.model
    history_export_artifact_model.objects.filter(
        history=history,
        owner=owner,
        requested_format=file_format,
    ).delete()
    file_name, artifact_type, safe_file_path = _generate_history_download_artifact(
        history,
        owner,
        file_format,
    )
    return file_name, artifact_type, safe_file_path


def _delete_history_artifact_file(artifact):
    try:
        safe_file_path = safe_join(
            _get_history_download_storage_dir(artifact.artifact_type),
            artifact.file_name,
        )
    except (KeyError, SuspiciousFileOperation, TypeError, ValueError):
        logger.warning(
            "History artifact cleanup skipped because the cached path is unsafe.",
            exc_info=True,
        )
        return

    try:
        os.remove(safe_file_path)
    except FileNotFoundError:
        return
    except OSError:
        logger.warning(
            "Failed to delete cached history artifact file during history removal.",
            exc_info=True,
        )


def _delete_history_cached_artifacts(history):
    for artifact in history.export_artifacts.all():
        _delete_history_artifact_file(artifact)


def _build_export_success_response(
    metadata,
    response_serializer_class,
    invalid_metadata_message,
):
    response_serializer = response_serializer_class(data=metadata)
    if not response_serializer.is_valid():
        return Response(
            {
                "status": "error",
                "message": invalid_metadata_message,
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return Response(response_serializer.validated_data, status=status.HTTP_200_OK)


def _build_export_error_response(
    error,
    validation_error_types,
    generation_error_types,
    invalid_request_message,
    internal_error_message,
    validation_log_message,
    generation_log_message,
    unexpected_log_message,
):
    if isinstance(error, validation_error_types):
        logger.warning(validation_log_message, exc_info=True)
        return Response(
            {
                "status": "error",
                "message": invalid_request_message,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    if isinstance(error, generation_error_types):
        logger.exception(generation_log_message)
        return Response(
            {
                "status": "error",
                "message": internal_error_message,
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    logger.exception(unexpected_log_message)
    return Response(
        {
            "status": "error",
            "message": internal_error_message,
        },
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


@api_view(["GET"])
def health(request):
    return Response({"status": "ok", "message": "Backend is running!"})


@api_view(["GET"])
def about(request):
    return Response({"team": "PPL C - Equitek", "project": "Excel Generator"})


@api_view(["GET"])
def members(request):
    data = list(GroupMember.objects.values("npm", "name"))
    return Response({"group": "Kelompok 7", "members": data})


def _parse_history_pagination(value, default, minimum=0):
    if value is None:
        return default

    parsed = int(value)
    if parsed < minimum:
        raise ValueError
    return parsed


@require_GET
@api_view(["GET"])
@permission_classes([IsAuthenticated, IsVerifiedUser])
def history_list(request):
    try:
        limit = _parse_history_pagination(
            request.query_params.get("limit"),
            default=10,
            minimum=1,
        )
        offset = _parse_history_pagination(
            request.query_params.get("offset"),
            default=0,
            minimum=0,
        )
        records = list_artifact_history_for_user(request.user, limit=limit, offset=offset)
    except (TypeError, ValueError):
        return Response(
            {
                "status": "error",
                "message": "Invalid history pagination request.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    total_count = request.user.artifact_histories.count()
    results = HistoryItemSerializer(records, many=True).data

    return Response(
        {
            "count": total_count,
            "limit": limit,
            "offset": offset,
            "results": results,
        },
        status=status.HTTP_200_OK,
    )


@require_http_methods(["PATCH"])
@api_view(["PATCH"])
@permission_classes([IsAuthenticated, IsVerifiedUser])
def history_rename(request, history_id):
    history, error_response = _get_owned_history_or_not_found(request.user, history_id)
    if error_response is not None:
        return error_response

    serializer = HistoryRenameSerializer(
        history,
        data=request.data,
        partial=False,
    )
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    updated_history = update_artifact_history_custom_name(
        history,
        serializer.validated_data["custom_name"],
    )
    return Response(
        HistoryItemSerializer(updated_history).data,
        status=status.HTTP_200_OK,
    )


@require_http_methods(["DELETE"])
@api_view(["DELETE"])
@permission_classes([IsAuthenticated, IsVerifiedUser])
def history_delete(request, history_id):
    history, error_response = _get_owned_history_or_not_found(request.user, history_id)
    if error_response is not None:
        return error_response

    try:
        _delete_history_cached_artifacts(history)
        delete_artifact_history(history)
    except Exception:
        logger.exception("Unexpected error while deleting history item.")
        return _history_delete_internal_error_response()

    return Response(status=status.HTTP_204_NO_CONTENT)


@require_GET
@api_view(["GET"])
@permission_classes([IsAuthenticated, IsVerifiedUser])
def history_download(request, history_id):
    file_format = (request.query_params.get("file_format") or "").strip().lower()
    if file_format not in {"csv", "xlsx"}:
        return Response(
            {
                "status": "error",
                "message": "Invalid history download format.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    history, error_response = _get_owned_history_or_not_found(request.user, history_id)
    if error_response is not None:
        return error_response

    try:
        file_name, artifact_type, safe_file_path, used_cached_artifact = _resolve_history_download_artifact(
            history=history,
            owner=request.user,
            file_format=file_format,
        )
        try:
            file_handle = open(safe_file_path, "rb")
        except OSError:
            if not used_cached_artifact:
                raise

            logger.warning(
                "History download cache artifact missing on disk; regenerating."
            )
            file_name, artifact_type, safe_file_path = (
                _regenerate_history_download_artifact_after_stale_cache(
                    history=history,
                    owner=request.user,
                    file_format=file_format,
                )
            )
            file_handle = open(safe_file_path, "rb")
    except (OutputLLMValidationError, OutputCSVMappingError):
        logger.exception("History download failed due to invalid stored output.")
        return _history_download_internal_error_response()
    except (
        OutputCSVGenerationError,
        OutputExcelGenerationError,
        SuspiciousFileOperation,
        ValueError,
        OSError,
        KeyError,
    ):
        logger.exception("History download failed while generating artifact.")
        return _history_download_internal_error_response()
    except Exception:
        logger.exception("Unexpected error while preparing history download.")
        return _history_download_internal_error_response()

    download_name = _resolve_download_filename(
        requested_name=request.query_params.get("filename"),
        default_name=file_name,
        artifact_type=artifact_type,
    )

    return FileResponse(
        file_handle,
        as_attachment=True,
        filename=download_name,
        content_type=_get_history_download_content_type(artifact_type),
    )


@api_view(["POST"])
@parser_classes([MultiPartParser])
def upload(request):
    try:
        raw_content_length = request.META.get("CONTENT_LENGTH")
        if raw_content_length is not None:
            try:
                content_length = int(raw_content_length)
            except (TypeError, ValueError):
                content_length = None

            content_type = (request.META.get("CONTENT_TYPE") or "").lower()
            max_request_size = MAX_FILE_SIZE
            if "multipart/form-data" in content_type:
                # CONTENT_LENGTH includes multipart framing, not only file bytes.
                max_request_size += MAX_MULTIPART_OVERHEAD_BYTES

            if content_length is not None and content_length > max_request_size:
                return Response(
                    {"status": "error", "message": FILE_TOO_LARGE_ERROR},
                    status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                )

        if "file" not in request.FILES:
            return Response(
                {"status": "error", "message": "No file provided"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        uploaded_file = request.FILES["file"]

        success, error, _, extracted = process_upload(uploaded_file)

        if not success:
            return Response(
                {"status": "error", "message": error},
                status=status.HTTP_400_BAD_REQUEST,
            )

        response_data = {
            "status": "success",
            "message": "File uploaded successfully",
            "filename": uploaded_file.name,
        }

        if extracted is not None:
            response_data["extracted"] = extracted

        return Response(
            response_data,
            status=status.HTTP_200_OK,
        )
              
    except Exception:
        logger.exception("Unexpected error during file upload")
        return Response(
            {
                "status": "error",
                "message": "Internal server error while processing the file.",
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@require_POST
@api_view(["POST"])
@permission_classes([IsAuthenticated, IsVerifiedUser])
def export_csv(request):
    serializer = CsvExportRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    try:
        metadata = export_csv_to_filesystem(
            output_json=serializer.validated_data["output_json"],
            storage_dir=settings.CSV_EXPORT_DIR,
        )
    except Exception as exc:
        return _build_export_error_response(
            error=exc,
            validation_error_types=(OutputLLMValidationError, OutputCSVMappingError),
            generation_error_types=(OutputCSVGenerationError,),
            invalid_request_message="Invalid CSV export request.",
            internal_error_message="Failed to generate CSV due to internal error.",
            validation_log_message="Validation or mapping error during CSV export.",
            generation_log_message="CSV generation error during CSV export.",
            unexpected_log_message="Unexpected error during CSV export.",
        )

    return _build_export_success_response(
        metadata=metadata,
        response_serializer_class=CsvExportResponseSerializer,
        invalid_metadata_message=(
            "Failed to generate CSV due to invalid response metadata."
        ),
    )


@require_POST
@api_view(["POST"])
@permission_classes([IsAuthenticated, IsVerifiedUser])
def export_excel(request):
    serializer = ExcelExportRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    try:
        metadata = export_excel_to_filesystem(
            output_json=serializer.validated_data["output_json"],
            storage_dir=settings.EXCEL_EXPORT_DIR,
        )
    except Exception as exc:
        return _build_export_error_response(
            error=exc,
            validation_error_types=(OutputLLMValidationError, OutputCSVMappingError),
            generation_error_types=(OutputExcelGenerationError,),
            invalid_request_message="Invalid Excel export request.",
            internal_error_message="Failed to generate Excel due to internal error.",
            validation_log_message="Validation or mapping error during Excel export.",
            generation_log_message="Excel generation error during Excel export.",
            unexpected_log_message="Unexpected error during Excel export.",
        )

    return _build_export_success_response(
        metadata=metadata,
        response_serializer_class=ExcelExportResponseSerializer,
        invalid_metadata_message=(
            "Failed to generate Excel due to invalid response metadata."
        ),
    )


@require_GET
@api_view(["GET"])
@permission_classes([IsAuthenticated, IsVerifiedUser])
def download_csv(request, file_id):
    try:
        artifact = resolve_csv_download_artifact(
            file_id=file_id,
            storage_dir=settings.CSV_EXPORT_DIR,
        )
    except OutputCSVDownloadLookupError:
        logger.warning("CSV download file not found or invalid file_id.", exc_info=True)
        return _build_download_error_response(
            CSV_FILE_NOT_FOUND_MESSAGE,
            status.HTTP_404_NOT_FOUND,
        )

    try:
        safe_file_path = safe_join(settings.CSV_EXPORT_DIR, artifact["file_name"])
        file_handle = open(safe_file_path, "rb")
    except (KeyError, SuspiciousFileOperation, ValueError):
        logger.warning("CSV download resolved unsafe artifact metadata.", exc_info=True)
        return _build_download_error_response(
            CSV_FILE_NOT_FOUND_MESSAGE,
            status.HTTP_404_NOT_FOUND,
        )
    except OSError:
        logger.exception("CSV download failed while reading generated artifact.")
        return _build_download_error_response(
            CSV_DOWNLOAD_INTERNAL_ERROR_MESSAGE,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    except Exception:
        logger.exception("Unexpected error while preparing CSV download.")
        return _build_download_error_response(
            CSV_DOWNLOAD_INTERNAL_ERROR_MESSAGE,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    download_name = _resolve_download_filename(
        requested_name=request.query_params.get("filename"),
        default_name=artifact["file_name"],
        artifact_type=artifact["artifact_type"],
    )

    return FileResponse(
        file_handle,
        as_attachment=True,
        filename=download_name,
        content_type=artifact["content_type"],
    )


@require_GET
@api_view(["GET"])
@permission_classes([IsAuthenticated, IsVerifiedUser])
def session_output_download_csv(request, session_id, output_id):
    return _build_session_output_download_response(
        request=request,
        session_id=session_id,
        output_id=output_id,
        config=SessionOutputDownloadConfig(
            export_callable=export_csv_to_filesystem,
            storage_dir=settings.CSV_EXPORT_DIR,
            artifact_type="csv",
            validation_error_types=(OutputLLMValidationError, OutputCSVMappingError),
            generation_error_types=(OutputCSVGenerationError,),
            invalid_request_message="Invalid CSV export request.",
            internal_error_message=CSV_DOWNLOAD_INTERNAL_ERROR_MESSAGE,
            validation_log_message="Validation or mapping error during session CSV download.",
            generation_log_message="CSV generation error during session CSV download.",
            unexpected_log_message="Unexpected error during session CSV download.",
            not_found_message=CSV_FILE_NOT_FOUND_MESSAGE,
            download_internal_error_message=CSV_DOWNLOAD_INTERNAL_ERROR_MESSAGE,
        ),
    )


@require_GET
@api_view(["GET"])
@permission_classes([IsAuthenticated, IsVerifiedUser])
def session_output_download_excel(request, session_id, output_id):
    return _build_session_output_download_response(
        request=request,
        session_id=session_id,
        output_id=output_id,
        config=SessionOutputDownloadConfig(
            export_callable=export_excel_to_filesystem,
            storage_dir=settings.EXCEL_EXPORT_DIR,
            artifact_type="xlsx",
            validation_error_types=(OutputLLMValidationError, OutputCSVMappingError),
            generation_error_types=(OutputExcelGenerationError,),
            invalid_request_message="Invalid Excel export request.",
            internal_error_message=EXCEL_DOWNLOAD_INTERNAL_ERROR_MESSAGE,
            validation_log_message="Validation or mapping error during session Excel download.",
            generation_log_message="Excel generation error during session Excel download.",
            unexpected_log_message="Unexpected error during session Excel download.",
            not_found_message=EXCEL_FILE_NOT_FOUND_MESSAGE,
            download_internal_error_message=EXCEL_DOWNLOAD_INTERNAL_ERROR_MESSAGE,
        ),
    )


def _session_csv_download_not_found_response():
    return _build_download_error_response(
        CSV_FILE_NOT_FOUND_MESSAGE,
        status.HTTP_404_NOT_FOUND,
    )


def _session_csv_download_internal_error_response():
    return _build_download_error_response(
        CSV_DOWNLOAD_INTERNAL_ERROR_MESSAGE,
        status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


def _normalize_session_output_export_payload(output):
    payload = getattr(output, "export_output_json", None) or {}
    if not payload:
        raw = getattr(output, "output_json", None)
        if raw:
            payload = build_export_output_json(input_json=raw, output_json=raw)
    if not isinstance(payload, dict):
        return payload

    normalized_payload = dict(payload)
    document_info = payload.get("document_info")
    if not isinstance(document_info, dict):
        return normalized_payload

    normalized_document_info = dict(document_info)
    source_type = normalized_document_info.get("source_type")
    if source_type in {"Excel", "PDF"}:
        normalized_payload["document_info"] = normalized_document_info
        return normalized_payload

    filename = normalized_document_info.get("filename")
    if isinstance(filename, str) and filename.strip().lower().endswith(".pdf"):
        normalized_document_info["source_type"] = "PDF"
    else:
        normalized_document_info["source_type"] = "Excel"

    normalized_payload["document_info"] = normalized_document_info
    return normalized_payload


def _build_session_output_download_response(
    *,
    request,
    session_id,
    output_id,
    config,
):
    output = get_generated_output_for_session_user(
        request.user,
        session_id,
        output_id,
    )
    if output is None:
        return Response({"detail": NOT_FOUND_DETAIL}, status=status.HTTP_404_NOT_FOUND)

    try:
        artifact = config.export_callable(
            output_json=_normalize_session_output_export_payload(output),
            storage_dir=config.storage_dir,
        )
    except Exception as exc:
        return _build_export_error_response(
            error=exc,
            validation_error_types=config.validation_error_types,
            generation_error_types=config.generation_error_types,
            invalid_request_message=config.invalid_request_message,
            internal_error_message=config.internal_error_message,
            validation_log_message=config.validation_log_message,
            generation_log_message=config.generation_log_message,
            unexpected_log_message=config.unexpected_log_message,
        )

    try:
        safe_file_path = safe_join(config.storage_dir, artifact["file_name"])
        file_handle = open(safe_file_path, "rb")
    except (KeyError, SuspiciousFileOperation, ValueError):
        logger.warning(
            "Session %s download resolved unsafe artifact metadata.",
            config.artifact_type.upper(),
            exc_info=True,
        )
        return _build_download_error_response(
            config.not_found_message,
            status.HTTP_404_NOT_FOUND,
        )
    except OSError:
        logger.exception(
            "Session %s download failed while reading generated artifact.",
            config.artifact_type.upper(),
        )
        return _build_download_error_response(
            config.download_internal_error_message,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    except Exception:
        logger.exception(
            "Unexpected error while preparing session %s download.",
            config.artifact_type.upper(),
        )
        return _build_download_error_response(
            config.download_internal_error_message,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    download_name = _resolve_download_filename(
        requested_name=request.query_params.get("filename"),
        default_name=artifact["file_name"],
        artifact_type=artifact["artifact_type"],
    )

    return FileResponse(
        file_handle,
        as_attachment=True,
        filename=download_name,
        content_type=_get_history_download_content_type(artifact["artifact_type"]),
    )


@require_GET
@api_view(["GET"])
@permission_classes([IsAuthenticated, IsVerifiedUser])
def session_list(request):
    try:
        limit, offset = _parse_session_list_pagination(request)
        sessions = list(list_sessions_for_user(request.user, limit=limit, offset=offset))
    except SessionListPaginationError as exc:
        return _build_session_list_pagination_error_response(exc.detail)
    except ValueError as exc:
        detail = exc.args[0] if exc.args else None
        return _build_session_list_pagination_error_response(detail)

    serializer = SessionListItemSerializer(sessions, many=True)
    return Response(
        {
            "count": len(sessions),
            "limit": limit,
            "offset": offset,
            "results": serializer.data,
        },
        status=status.HTTP_200_OK,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated, IsVerifiedUser])
def session_detail(request, session_id):
    return _build_session_detail_response(request, session_id)


def _build_session_detail_response(request, session_id):
    try:
        pagination = _parse_session_detail_pagination(request)
        session = get_paginated_session_detail_for_user(
            request.user,
            session_id,
            **pagination,
        )
    except SessionDetailPaginationError as exc:
        return _build_session_detail_pagination_error_response(exc.detail)
    except ValueError as exc:
        detail = exc.args[0] if exc.args else None
        return _build_session_detail_pagination_error_response(detail)

    if session is None:
        return Response({"detail": NOT_FOUND_DETAIL}, status=status.HTTP_404_NOT_FOUND)

    return Response(SessionDetailSerializer(session).data, status=status.HTTP_200_OK)

@require_GET
@api_view(["GET"])
@permission_classes([IsAuthenticated, IsVerifiedUser])
def session_resume(request, session_id):
    resume_context = build_resume_context_for_user(request.user, session_id)
    if resume_context is None:
        return Response({"detail": NOT_FOUND_DETAIL}, status=status.HTTP_404_NOT_FOUND)

    return Response(
        SessionResumeSerializer(resume_context).data,
        status=status.HTTP_200_OK,
    )


@api_view(["PATCH"])
@permission_classes([IsAuthenticated, IsVerifiedUser])
def session_update(request, session_id):
    return _build_session_update_response(request.user, request.data, session_id)


def _build_session_update_response(user, data, session_id):
    session = get_session_for_user(user, session_id)
    if session is None:
        return Response({"detail": NOT_FOUND_DETAIL}, status=status.HTTP_404_NOT_FOUND)

    serializer = SessionTitleUpdateSerializer(data=data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    updated_session = update_session_title(session, serializer.validated_data["title"])
    return Response(
        SessionListItemSerializer(updated_session).data,
        status=status.HTTP_200_OK,
    )


@api_view(["DELETE"])
@permission_classes([IsAuthenticated, IsVerifiedUser])
def session_delete(request, session_id):
    return _build_session_delete_response(request.user, session_id)


def _build_session_delete_response(user, session_id):
    session = get_session_for_user(user, session_id)
    if session is None:
        return Response({"detail": NOT_FOUND_DETAIL}, status=status.HTTP_404_NOT_FOUND)

    delete_session(session)
    return Response(status=status.HTTP_204_NO_CONTENT)


class SessionResourceView(APIView):
    permission_classes = [IsAuthenticated, IsVerifiedUser]

    def get(self, request, session_id):
        return _build_session_detail_response(request, session_id)

    def patch(self, request, session_id):
        return _build_session_update_response(request.user, request.data, session_id)

    def delete(self, request, session_id):
        return _build_session_delete_response(request.user, session_id)




@require_GET
@api_view(["GET"])
@permission_classes([IsAuthenticated, IsVerifiedUser])
def download_excel(request, export_id):
    try:
        artifact = resolve_excel_download_artifact(
            export_id=export_id,
            storage_dir=settings.EXCEL_EXPORT_DIR,
        )
    except OutputExcelDownloadLookupError as exc:
        if _is_invalid_excel_download_id_error(exc):
            logger.warning("Excel download received invalid export_id.", exc_info=True)
            return Response(
                {
                    "status": "error",
                    "message": "Invalid Excel export id.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        logger.warning("Excel download file not found.", exc_info=True)
        return _excel_download_not_found_response()
    except OutputExcelDownloadStorageError:
        logger.exception("Excel download storage is unavailable.")
        return _excel_download_internal_error_response()
    except Exception:
        logger.exception("Unexpected error while resolving Excel download artifact.")
        return _excel_download_internal_error_response()

    try:
        safe_file_path = safe_join(settings.EXCEL_EXPORT_DIR, artifact["file_name"])
        file_handle = open(safe_file_path, "rb")
    except (KeyError, SuspiciousFileOperation, ValueError):
        logger.warning("Excel download resolved unsafe artifact metadata.", exc_info=True)
        return _excel_download_not_found_response()
    except OSError:
        logger.exception("Excel download failed while reading generated artifact.")
        return _excel_download_internal_error_response()
    except Exception:
        logger.exception("Unexpected error while preparing Excel download.")
        return _excel_download_internal_error_response()
    download_name = _resolve_download_filename(
        requested_name=request.query_params.get("filename"),
        default_name=artifact["file_name"],
        artifact_type=artifact["artifact_type"],
    )

    return FileResponse(
        file_handle,
        as_attachment=True,
        filename=download_name,
        content_type=artifact["content_type"],
    )
