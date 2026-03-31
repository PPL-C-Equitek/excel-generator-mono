from rest_framework import generics

from .models import CustomSchema
from .serializers import CustomSchemaSerializer


class CustomSchemaListCreateView(generics.ListCreateAPIView):
    serializer_class = CustomSchemaSerializer

    def get_queryset(self):
        queryset = CustomSchema.objects.all()
        active = self.request.query_params.get("active")
        if active is None:
            return queryset

        normalized = active.strip().lower()
        if normalized in {"true", "1", "yes"}:
            return queryset.filter(is_active=True)
        if normalized in {"false", "0", "no"}:
            return queryset.filter(is_active=False)
        return queryset


class CustomSchemaDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = CustomSchema.objects.all()
    serializer_class = CustomSchemaSerializer
