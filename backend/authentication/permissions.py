from rest_framework.permissions import BasePermission


class IsVerifiedUser(BasePermission):
    message = "Akun Anda belum diverifikasi. Silakan cek email Anda."

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            getattr(request.user, "status", None) == "verified"
        )
