from django.urls import path

from .views import CustomSchemaDetailView, CustomSchemaListCreateView


urlpatterns = [
    path("", CustomSchemaListCreateView.as_view(), name="custom-schema-list"),
    path("<int:pk>/", CustomSchemaDetailView.as_view(), name="custom-schema-detail"),
]
