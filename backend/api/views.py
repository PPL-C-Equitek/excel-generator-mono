import os
from uuid import uuid4
from django.conf import settings
from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework import status
from .models import GroupMember

ALLOWED_EXTENSIONS = [".pdf", ".xls", ".xlsx"]

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
    filename = uploaded_file.name
    ext = os.path.splitext(filename)[1].lower()

    if ext not in ALLOWED_EXTENSIONS:
        return Response(
            {
                "status": "error",
                "message": "Unsupported file type. Only PDF, XLS, and XLSX are allowed."
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    os.makedirs(settings.UPLOAD_TEMP_DIR, exist_ok=True)

    unique_name = f"{uuid4()}_{filename}"
    file_path = os.path.join(settings.UPLOAD_TEMP_DIR, unique_name)

    with open(file_path, "wb+") as destination:
        for chunk in uploaded_file.chunks():
            destination.write(chunk)

    return Response(
        {
            "status": "success",
            "message": "File uploaded successfully",
            "filename": filename,
            "path": file_path
        },
        status=status.HTTP_200_OK
    )