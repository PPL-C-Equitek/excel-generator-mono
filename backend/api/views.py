from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import GroupMember

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

