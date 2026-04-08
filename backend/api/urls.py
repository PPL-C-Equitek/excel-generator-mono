from django.urls import path
from . import views

urlpatterns = [
    path("health/", views.health),
    path("about/", views.about),
    path("members/", views.members),
    path("upload/", views.upload),
    path("export/csv", views.export_csv),
    path("export/excel", views.export_excel),
    path("export/csv/<str:file_id>/download", views.download_csv),
    path("export/excel/<str:export_id>/download", views.download_excel),
]
