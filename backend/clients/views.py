from django.shortcuts import render

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from .models import Client, ClientUser, ClientApplication
from .serializers import (
    ClientSerializer, ClientDetailSerializer,
    ClientApplicationSerializer, ClientUserSerializer
)
from oauth2_provider.models import Application
from users.permissions import HasRole  # si vous avez cette classe, sinon à créer


class ClientViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour gérer le client de l'utilisateur connecté.
    Un utilisateur ne peut voir/modifier que les clients dont il est membre.
    """
    serializer_class = ClientSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # L'utilisateur ne voit que les clients dont il est membre
        return Client.objects.filter(members__user=self.request.user)

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ClientDetailSerializer
        return ClientSerializer

    def perform_create(self, serializer):
        # À la création, l'utilisateur devient owner et membre admin
        client = serializer.save(owner=self.request.user)
        ClientUser.objects.create(client=client, user=self.request.user, role='admin')

    @action(detail=True, methods=['get', 'post'], url_path='apps')
    def apps(self, request, pk=None):
        """Gérer les applications OAuth2 du client"""
        client = self.get_object()
        if request.method == 'GET':
            apps = ClientApplication.objects.filter(client=client)
            serializer = ClientApplicationSerializer(apps, many=True)
            return Response(serializer.data)

        elif request.method == 'POST':
            # Créer une nouvelle application OAuth2
            data = request.data
            # Créer l'application OAuth2
            app = Application.objects.create(
                name=data['name'],
                client_type=data.get('client_type', 'confidential'),
                authorization_grant_type=data.get('grant_type', 'authorization-code'),
                redirect_uris=data.get('redirect_uris', ''),
                user=request.user  # le propriétaire de l'application
            )
            # Lier au client
            client_app = ClientApplication.objects.create(
                client=client,
                application=app,
                is_active=True
            )
            serializer = ClientApplicationSerializer(client_app)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        
    @action(detail=True, methods=['get'], url_path='apps/(?P<app_id>[^/.]+)')
    def app_detail(self, request, pk=None, app_id=None):
        """Détail d'une application spécifique du client"""
        client = self.get_object()
        client_app = get_object_or_404(ClientApplication, client=client, application_id=app_id)
        serializer = ClientApplicationSerializer(client_app)
        return Response(serializer.data)  
    
    @action(detail=True, methods=['get', 'post'], url_path='team')
    def team(self, request, pk=None):
        """Gérer les membres du client"""
        client = self.get_object()
        if request.method == 'GET':
            members = ClientUser.objects.filter(client=client)
            serializer = ClientUserSerializer(members, many=True)
            return Response(serializer.data)

        elif request.method == 'POST':
            # Inviter un utilisateur (par email) – simplification : on reçoit user_id
            user_id = request.data.get('user_id')
            role = request.data.get('role', 'member')
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                return Response({'error': 'Utilisateur non trouvé'}, status=404)
            # Vérifier qu'il n'est pas déjà membre
            if ClientUser.objects.filter(client=client, user=user).exists():
                return Response({'error': 'Déjà membre'}, status=400)
            client_user = ClientUser.objects.create(client=client, user=user, role=role)
            serializer = ClientUserSerializer(client_user)
            return Response(serializer.data, status=201)

    @action(detail=True, methods=['patch'], url_path='team/(?P<user_id>[^/.]+)')
    def update_team(self, request, pk=None, user_id=None):
        """Modifier le rôle d'un membre (admin seulement)"""
        client = self.get_object()
        client_user = get_object_or_404(ClientUser, client=client, user_id=user_id)
       
        role = request.data.get('role')
        if role not in dict(ClientUser.ROLE_CHOICES).keys():
            return Response({'error': 'Rôle invalide'}, status=400)
        client_user.role = role
        client_user.save()
        return Response(ClientUserSerializer(client_user).data)

    @action(detail=True, methods=['delete'], url_path='team/(?P<user_id>[^/.]+)')
    def remove_team(self, request, pk=None, user_id=None):
        """Retirer un membre (ne peut pas retirer le owner)"""
        client = self.get_object()
        if user_id == str(client.owner.id):
            return Response({'error': 'Impossible de retirer le propriétaire'}, status=400)
        client_user = get_object_or_404(ClientUser, client=client, user_id=user_id)
        client_user.delete()
        return Response(status=204)
    
    @action(detail=True, methods=['get'], url_path='stats')
    def stats(self, request, pk=None):
        """Statistiques d'usage du client"""
        client = self.get_object()

        # Nombre total d'utilisateurs membres
        total_users = ClientUser.objects.filter(client=client).count()

        # Utilisateurs actifs (connectés dans les 30 derniers jours)
        thirty_days_ago = timezone.now() - timedelta(days=30)
        active_users = ClientUser.objects.filter(
            client=client,
            user__last_login__gte=thirty_days_ago
        ).count()

        # Nombre d'applications OAuth actives
        total_apps = ClientApplication.objects.filter(client=client, is_active=True).count()

        # Authentifications totales (via les tokens créés)
        # Récupérer les applications du client
        app_ids = ClientApplication.objects.filter(
            client=client
        ).values_list('application_id', flat=True)

        # Compter les access tokens créés pour ces applications (30 derniers jours)
        auth_count = AccessToken.objects.filter(
            application_id__in=app_ids,
            created__gte=thirty_days_ago
        ).count()

        # Répartition par méthode d'authentification (si vous avez enregistré dans UserActivity)
        # (optionnel)

        return Response({
            'total_users': total_users,
            'active_users_last_30_days': active_users,
            'total_applications': total_apps,
            'authentications_last_30_days': auth_count,
        })