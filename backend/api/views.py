import logging

from django.conf import settings
from django.views.decorators.http import require_POST
from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework import status
from .models import GroupMember

from file_processing.services.upload_service import (
    process_upload,
)
from file_processing.serializers import (
    CsvExportRequestSerializer,
    CsvExportResponseSerializer,
)
from file_processing.services.export_service import (
    OutputCSVGenerationError,
    OutputCSVMappingError,
    OutputLLMValidationError,
    export_csv_to_filesystem,
)

logger = logging.getLogger(__name__)

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


@api_view(["POST"])
@parser_classes([MultiPartParser])
def upload(request):
    try:
        if "file" not in request.FILES:
        return Response(
            {"status": "error", "message": "No file provided"},
            status=status.HTTP_400_BAD_REQUEST,
        )

        uploaded_file = request.FILES["file"]

        success, error, file_path, extracted_text = process_upload(uploaded_file)

        if not success:
            return Response(
                {"status": "error", "message": error},
                status=status.HTTP_400_BAD_REQUEST,
            )

        response_data = {
            "status": "success",
            "message": "File uploaded successfully",
            "filename": uploaded_file.name,
            "path": file_path,
        }

        if extracted_text is not None:
            response_data["extracted_text"] = extracted_text

        return Response(
            response_data,
            status=status.HTTP_200_OK,
        )
      
    except Exception:
        return Response(
            {
                "status": "error",
                "message": "Internal server error while processing the file.",
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
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
