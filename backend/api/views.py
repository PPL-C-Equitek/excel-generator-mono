import os

from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework import status
from .models import GroupMember

from file_processing.services.upload_service import (
    validate_file,
    validate_pdf_not_corrupt,
    save_temp_file,
    validate_pdf_not_password_protected,
)

ALLOWED_EXTENSIONS = [".pdf", ".xls", ".xlsx"]
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


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

    if "file" not in request.FILES:
        return Response(
            {"status": "error", "message": "No file provided"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    uploaded_file = request.FILES["file"]

    is_valid, error = validate_file(uploaded_file)
    if not is_valid:
        return Response(
            {"status": "error", "message": error}, status=status.HTTP_400_BAD_REQUEST
        )

    if os.path.splitext(uploaded_file.name)[1].lower() == ".pdf":
        is_valid, error = validate_pdf_not_corrupt(uploaded_file)
        if not is_valid:
            return Response(
                {"status": "error", "message": error},
                status=status.HTTP_400_BAD_REQUEST,
            )

        is_valid, error = validate_pdf_not_password_protected(uploaded_file)
        if not is_valid:
            return Response(
                {"status": "error", "message": error},
                status=status.HTTP_400_BAD_REQUEST,
            )

    file_path = save_temp_file(uploaded_file)

    return Response(
        {
            "status": "success",
            "message": "File uploaded successfully",
            "filename": uploaded_file.name,
            "path": file_path,
        },
        status=status.HTTP_200_OK,
    )
