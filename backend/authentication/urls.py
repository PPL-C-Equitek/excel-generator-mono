from django.urls import path

from authentication.change_password.http import ChangePasswordView
from authentication.register.http import RegisterView
from authentication import views

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("verify-email/", views.VerifyEmailView.as_view(), name="verify-email"),
    path("resend-verification/", views.ResendVerificationView.as_view(), name="resend-verification"),
    path("forgot-password/", views.ForgotPasswordView.as_view(), name="forgot-password"),
    path("resend-password-reset/", views.ResendPasswordResetView.as_view(), name="resend-password-reset"),
    path("reset-password/", views.ResetPasswordView.as_view(), name="reset-password"),
    path("login/", views.LoginView.as_view(), name="login"),
    path("refresh/", views.RefreshTokenView.as_view(), name="refresh"),
    path("google-oauth/", views.google_oauth_callback, name="google-oauth"),
    path("logout/", views.LogoutView.as_view(), name="logout"),
    path("change-password/", ChangePasswordView.as_view(), name="change-password"),
]
