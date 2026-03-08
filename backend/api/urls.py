from django.urls import path
from . import views

urlpatterns = [
    path('health/', views.health),
    path('about/', views.about),
    path('members/', views.members),
    path('upload/', views.upload),
    path('export/csv', views.export_csv),
    path('export/csv/download/<str:file_id>', views.download_csv),
]
