from django.urls import path, include
from . import views

urlpatterns = [
    path('health/', views.health),
    path('about/', views.about),
    path('members/', views.members),
    path('upload/', views.upload),
    path('export/csv', views.export_csv),
]
