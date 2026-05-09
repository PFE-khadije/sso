from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from oauth2_provider.models import RefreshToken, AccessToken
from django.utils import timezone
from django.shortcuts import get_object_or_404
from users.serializers import TrustedDeviceSerializer
from users.serializers import UserActivitySerializer
from users.models import TrustedDevice, UserActivity

class UserAuthorizedAppsView(APIView):
    """
    Liste des applications auxquelles l'utilisateur a donné accès.
    Basé sur les refresh tokens actifs.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Récupérer tous les refresh tokens actifs de l'utilisateur
        refresh_tokens = RefreshToken.objects.filter(
            user=request.user,
            revoked__isnull=True
        ).select_related('application')

        apps_data = []
        for token in refresh_tokens:
            app = token.application
            # Compter le nombre d'access tokens actifs associés (optionnel)
            access_tokens_count = AccessToken.objects.filter(
                refresh_token=token,
                expires__gt=timezone.now()
            ).count()

            apps_data.append({
                'application_id': app.id,
                'name': app.name,
                'client_id': app.client_id,
                'logo': None,  # optionnel : si vous avez un logo pour l'app
                'authorized_at': token.created,
                'last_used': token.updated,
                'active_sessions': access_tokens_count,
            })

        return Response(apps_data)


class UserRevokeAppView(APIView):
    """
    Révoquer l'accès à une application (supprime tous les tokens associés).
    """
    permission_classes = [IsAuthenticated]

    def delete(self, request, app_id):
        # Trouver tous les refresh tokens pour cette application et cet utilisateur
        refresh_tokens = RefreshToken.objects.filter(
            user=request.user,
            application_id=app_id,
            revoked__isnull=True
        )
        count = refresh_tokens.count()
        # Révoquer tous ces tokens
        refresh_tokens.update(revoked=timezone.now())
        return Response({
            'message': f'Accès révoqué pour {count} session(s)'
        }, status=200)
    


class UserDevicesView(APIView):
    """Liste des appareils de confiance de l'utilisateur"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        devices = TrustedDevice.objects.filter(user=request.user)
        serializer = TrustedDeviceSerializer(devices, many=True)
        return Response(serializer.data)


class UserDeviceDetailView(APIView):
    """Supprimer un appareil de confiance"""
    permission_classes = [IsAuthenticated]

    def delete(self, request, device_id):
        device = get_object_or_404(TrustedDevice, id=device_id, user=request.user)
        device.delete()
        return Response({'message': 'Appareil supprimé'}, status=204)    
    


class UserActivityView(APIView):
    """Historique des actions de l'utilisateur"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Limiter à 100 derniers événements
        activities = UserActivity.objects.filter(user=request.user)[:100]
        # Vous pouvez ajouter des filtres (type, date) via query params
        serializer = UserActivitySerializer(activities, many=True)
        return Response(serializer.data)    