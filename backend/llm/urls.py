from django.urls import path

from . import views

urlpatterns = [
    path("generate/", views.llm_generate),
    path("send-message/", views.send_message),
    path("send-message/stream/", views.stream_send_message),
    path("reasoning/", views.llm_reasoning),
    path("thinking-logs/", views.thinking_log_list),
    path("thinking-logs/<uuid:session_id>/", views.thinking_log_session_list),
    path("thinking-logs/output/<uuid:output_id>/", views.thinking_log_detail),
]

