from rest_framework.permissions import BasePermission, SAFE_METHODS
from clients.models import ClientUser
class IsAdminOrReadOnly(BasePermission):
    """Autorise les méthodes safe (GET, HEAD, OPTIONS) pour tout le monde,
    mais les modifications seulement pour les administrateurs (is_staff)."""
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return request.user and request.user.is_staff


class HasPermission(BasePermission):
    """
    Vérifie que l'utilisateur possède une permission spécifique.
    La permission requise doit être définie dans la vue via l'attribut `required_permission`.
    Pour les actions spécifiques, on peut modifier cet attribut dans `get_permissions()`.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        required_perm = getattr(view, 'required_permission', None)
        if required_perm is None:
            
            return True
        return request.user.has_permission(required_perm)


class HasRole(BasePermission):
    """
    Vérifie que l'utilisateur possède un rôle spécifique.
    Le rôle requis doit être défini dans la vue via l'attribut `required_role`.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        required_role = getattr(view, 'required_role', None)
        if required_role is None:
            return True
        return request.user.has_role(required_role)
    
class IsOwner(BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj.user == request.user   
    
class IsClientAdmin(BasePermission):
    def has_permission(self, request, view):
        # Pour les actions de détail, on vérifie dans has_object_permission
        return True

    def has_object_permission(self, request, view, obj):
        # obj est une instance de Client
        return ClientUser.objects.filter(
            client=obj,
            user=request.user,
            role='admin'
        ).exists()
