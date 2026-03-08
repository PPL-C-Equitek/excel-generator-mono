from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework import status
from .models import GroupMember

from file_processing.services.upload_service import (
    process_upload,
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


@api_view(["POST"])
@parser_classes([MultiPartParser])
def upload(request):

    if "file" not in request.FILES:
        return Response(
            {"status": "error", "message": "No file provided"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    uploaded_file = request.FILES["file"]

    success, error, _ = process_upload(uploaded_file)

    if not success:
        return Response(
            {"status": "error", "message": error},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response(
        {
            "status": "success",
            "message": "File uploaded successfully",
            "filename": uploaded_file.name,
        },
        status=status.HTTP_200_OK,
    )
