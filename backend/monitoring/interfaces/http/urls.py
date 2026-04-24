from django.urls import path

from . import views


urlpatterns = [
    path("monitoring/live/", views.live),
    path("monitoring/ready/", views.ready),
    path("monitoring/stats/", views.stats),
    path("monitoring/access/", views.access),
]
