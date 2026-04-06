from django.urls import path

from authentication.register.http import RegisterView
from authentication import views

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("verify-email/", views.VerifyEmailView.as_view(), name="verify-email"),
    path("resend-verification/", views.ResendVerificationView.as_view(), name="resend-verification"),
    path("login/", views.LoginView.as_view(), name="login"),
    path("refresh/", views.RefreshTokenView.as_view(), name="refresh"),
    path("google-oauth/", views.google_oauth_callback, name="google-oauth"),
    path("logout/", views.LogoutView.as_view(), name="logout"),
]
