from rest_framework.permissions import BasePermission


class IsVendor(BasePermission):
    """Allow authenticated users that have a vendor profile."""

    message = "A vendor account is required."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and hasattr(request.user, "vendor_profile")
        )
