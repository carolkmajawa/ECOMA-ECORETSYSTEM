from rest_framework.permissions import BasePermission

class IsAdminUser(BasePermission):
    """
    Allows access only to admin users.
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.role == 'admin'

class IsChairmanOrSecretary(BasePermission):
    """
    Allows access only to chairman or secretary.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.role in ['chairman', 'secretary']

class IsGroupMember(BasePermission):
    """
    Allows access only to group members.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.role in ['chairman', 'secretary', 'member', 'treasurer']