import os
import logging

from django.conf import settings
from django.core.exceptions import SuspiciousFileOperation
from django.http import FileResponse
from django.utils._os import safe_join
from django.views.decorators.http import require_GET, require_POST
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from .models import GroupMember
from artifact_history.models import ArtifactHistory
from artifact_history.services import list_artifact_history_for_user
from authentication.permissions import IsVerifiedUser
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

logger = logging.getLogger(__name__)
MAX_MULTIPART_OVERHEAD_BYTES = 256 * 1024  # multipart headers + boundaries


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


def _excel_download_not_found_response():
    return Response(
        {
            "status": "error",
            "message": "Excel file not found.",
        },
        status=status.HTTP_404_NOT_FOUND,
    )


def _excel_download_internal_error_response():
    return Response(
        {
            "status": "error",
            "message": "Failed to download Excel due to internal error.",
        },
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


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
    results = [
        {
            "id": str(record.id),
            "original_name": record.original_name,
            "custom_name": record.custom_name,
            "status_processing": record.status_processing,
            "created_at": record.created_at,
        }
        for record in records
    ]

    return Response(
        {
            "count": total_count,
            "limit": limit,
            "offset": offset,
            "results": results,
        },
        status=status.HTTP_200_OK,
    )


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

    history = ArtifactHistory.objects.filter(owner=request.user, id=history_id).first()
    if history is None:
        return _history_not_found_response()

    try:
        if file_format == "csv":
            artifact = export_csv_to_filesystem(
                output_json=history.output_json,
                storage_dir=settings.CSV_EXPORT_DIR,
            )
            content_type = (
                "application/zip"
                if artifact["artifact_type"] == "zip"
                else "text/csv"
            )
            safe_file_path = safe_join(settings.CSV_EXPORT_DIR, artifact["file_name"])
        else:
            artifact = export_excel_to_filesystem(
                output_json=history.output_json,
                storage_dir=settings.EXCEL_EXPORT_DIR,
            )
            content_type = (
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            safe_file_path = safe_join(settings.EXCEL_EXPORT_DIR, artifact["file_name"])

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
        default_name=artifact["file_name"],
        artifact_type=artifact["artifact_type"],
    )

    return FileResponse(
        file_handle,
        as_attachment=True,
        filename=download_name,
        content_type=content_type,
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
        return Response(
            {
                "status": "error",
                "message": "CSV file not found.",
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    try:
        safe_file_path = safe_join(settings.CSV_EXPORT_DIR, artifact["file_name"])
        file_handle = open(safe_file_path, "rb")
    except (KeyError, SuspiciousFileOperation, ValueError):
        logger.warning("CSV download resolved unsafe artifact metadata.", exc_info=True)
        return Response(
            {
                "status": "error",
                "message": "CSV file not found.",
            },
            status=status.HTTP_404_NOT_FOUND,
        )
    except OSError:
        logger.exception("CSV download failed while reading generated artifact.")
        return Response(
            {
                "status": "error",
                "message": "Failed to download CSV due to internal error.",
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    except Exception:
        logger.exception("Unexpected error while preparing CSV download.")
        return Response(
            {
                "status": "error",
                "message": "Failed to download CSV due to internal error.",
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
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
