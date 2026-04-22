from django.urls import path

from . import views

urlpatterns = [
    path("generate/", views.llm_generate),
    path("reasoning/", views.llm_reasoning),
    path("thinking-logs/", views.thinking_log_list),
    path("thinking-logs/<uuid:history_id>/", views.thinking_log_detail),
]

