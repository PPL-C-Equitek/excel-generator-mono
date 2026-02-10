from django.shortcuts import render
from rest_framework.decorators import api_view
from rest_framework.response import Response

# Create your views here.
@api_view(['GET'])
def health(request):
    return Response({"status": "ok", "message": "Backend is running!"})

@api_view(['GET'])
def about(request):
    return Response({"team": "PPL C - Equitek", "project": "Excel Generator"})