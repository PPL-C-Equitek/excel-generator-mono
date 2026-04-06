from rest_framework.permissions import BasePermission


class IsVerifiedUser(BasePermission):
    message = "Your account is not verified. Please check your email."

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            getattr(request.user, "status", None) == "verified"
        )
