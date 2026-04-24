from django.urls import path

from . import views

urlpatterns = [
    path("generate/", views.llm_generate),
    path("send-message/", views.send_message),
    path("reasoning/", views.llm_reasoning),
]

