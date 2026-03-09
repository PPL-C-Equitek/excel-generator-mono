import logging
import os

from django.conf import settings
from django.core.exceptions import SuspiciousFileOperation
from django.http import FileResponse
from django.utils._os import safe_join
from django.views.decorators.http import require_GET, require_POST
from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework import status
from .models import GroupMember

from file_processing.services.upload_service import (
    validate_file,
    save_temp_file,
)
from file_processing.serializers import (
    CsvExportRequestSerializer,
    CsvExportResponseSerializer,
)
from file_processing.services.export_service import (
    OutputCSVDownloadLookupError,
    OutputCSVGenerationError,
    OutputCSVMappingError,
    OutputLLMValidationError,
    export_csv_to_filesystem,
    resolve_csv_download_artifact,
)

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = [".pdf", ".xls", ".xlsx"]
MAX_FILE_SIZE = 10 * 1024 * 1024  #10MB


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

    expected_ext = ".zip" if artifact_type == "zip" else ".csv"
    root, ext = os.path.splitext(safe_name)
    if ext.lower() != expected_ext:
        if ext:
            return f"{root}{expected_ext}"
        return f"{safe_name}{expected_ext}"

    return safe_name

@api_view(['GET'])
def health(request):
    return Response({"status": "ok", "message": "Backend is running!"})

@api_view(['GET'])
def about(request):
    return Response({"team": "PPL C - Equitek", "project": "Excel Generator"})


@api_view(['GET'])
def members(request):
    data = list(GroupMember.objects.values("npm", "name"))
    return Response({"group": "Kelompok 7", "members": data})


@api_view(["POST"])
@parser_classes([MultiPartParser])
def upload(request):

    if "file" not in request.FILES:
        return Response(
            {
                "status": "error",
                "message": "No file provided"
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    uploaded_file = request.FILES["file"]

    is_valid, error = validate_file(uploaded_file)
    if not is_valid:
        return Response(
            {
                "status": "error",
                "message": error
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    file_path = save_temp_file(uploaded_file)

    return Response(
        {
            "status": "success",
            "message": "File uploaded successfully",
            "filename": uploaded_file.name,
            "path": file_path
        },
        status=status.HTTP_200_OK
    )


@require_POST
@api_view(["POST"])
def export_csv(request):
    serializer = CsvExportRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    try:
        metadata = export_csv_to_filesystem(
            output_json=serializer.validated_data["output_json"],
            storage_dir=settings.CSV_EXPORT_DIR,
        )
    except (OutputLLMValidationError, OutputCSVMappingError):
        logger.warning("Validation or mapping error during CSV export.", exc_info=True)
        return Response(
            {
                "status": "error",
                "message": "Invalid CSV export request.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    except OutputCSVGenerationError:
        logger.exception("CSV generation error during CSV export.")
        return Response(
            {
                "status": "error",
                "message": "Failed to generate CSV due to internal error.",
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    except Exception:
        logger.exception("Unexpected error during CSV export.")
        return Response(
            {
                "status": "error",
                "message": "Failed to generate CSV due to internal error.",
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    response_serializer = CsvExportResponseSerializer(data=metadata)
    if not response_serializer.is_valid():
        return Response(
            {
                "status": "error",
                "message": "Failed to generate CSV due to invalid response metadata.",
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return Response(response_serializer.validated_data, status=status.HTTP_200_OK)

@require_GET
@api_view(["GET"])
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
