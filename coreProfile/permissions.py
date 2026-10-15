from rest_framework.permissions import BasePermission, SAFE_METHODS


def is_owner(user):
    return bool(user and user.is_authenticated and user.is_superuser)


class IsOwnerOrReadOnly(BasePermission):
    """GET/HEAD/OPTIONS সবার জন্য। লেখার কাজ (POST/PATCH/DELETE) শুধু owner (superuser)।"""

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return is_owner(request.user)


class IsOwner(BasePermission):
    """সব method-ই শুধু owner-এর জন্য (যেমন moderation list, inbox)।"""

    def has_permission(self, request, view):
        return is_owner(request.user)