from django.urls import path

from chat_sessions.views import session_list, session_resource


urlpatterns = [
    path("sessions/", session_list, name="session-list"),
    path("sessions/<uuid:session_id>/", session_resource, name="session-resource"),
]
