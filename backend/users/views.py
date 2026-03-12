import pyotp
import qrcode
import io
import base64
from .utils import log_user_activity
from datetime import timedelta
from rest_framework import status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken
from rest_framework_simplejwt.exceptions import TokenError
from .models import User, Role, Permission, MFAMethod, BiometricProfile, TrustedDevice
from .serializers import (
    UserSerializer, RoleSerializer, PermissionSerializer,
    MFAMethodSerializer, BiometricProfileSerializer, TrustedDeviceSerializer,
    UserRegistrationSerializer, LoginSerializer,
    TOTPVerifySerializer, TOTPDisableSerializer
)
from .permissions import HasPermission, IsOwner
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from oauth2_provider.contrib.rest_framework import OAuth2Authentication
from rest_framework_simplejwt.authentication import JWTAuthentication


class UserInfoView(APIView):
    
    authentication_classes = [JWTAuthentication, OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        
        data = {
            "sub": str(user.id),                
            "email": user.email,
            "email_verified": True,              
            "phone": user.phone,
            "phone_verified": False,               
            "preferred_username": user.email.split('@')[0] if user.email else "",
        }
        
        return Response(data, status=status.HTTP_200_OK)
    

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = 'users.view_user'

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return User.objects.all()
        # Récupérer les IDs des clients de l'utilisateur
        client_ids = user.client_memberships.values_list('client_id', flat=True)
        if not client_ids:
            return User.objects.none()
        # Retourner les utilisateurs qui sont membres de ces clients
        return User.objects.filter(client_memberships__client_id__in=client_ids).distinct()
    def get_permissions(self):
        if self.action == 'create':
            self.required_permission = 'users.add_user'
        elif self.action in ['update', 'partial_update']:
            self.required_permission = 'users.change_user'
        elif self.action == 'destroy':
            self.required_permission = 'users.delete_user'
        return super().get_permissions()

    def perform_create(self, serializer):
        """Ajoute automatiquement le nouvel utilisateur aux clients de l'utilisateur connecté"""
        user = serializer.save()
        
        # Récupérer les clients de l'utilisateur connecté
        request_user = self.request.user
        client_ids = request_user.client_memberships.values_list('client_id', flat=True)
        
        # Ajouter le nouvel utilisateur comme membre de ces clients
        from clients.models import ClientUser  # Import ici pour éviter les imports circulaires
        for client_id in client_ids:
            ClientUser.objects.create(
                client_id=client_id,
                user=user,
                role='member'  # ou le rôle par défaut que vous voulez
            )
class RoleViewSet(viewsets.ModelViewSet):
    queryset = Role.objects.all()
    serializer_class = RoleSerializer
    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = 'roles.view_role'

    def get_permissions(self):
        if self.action == 'create':
            self.required_permission = 'roles.add_role'
        elif self.action in ['update', 'partial_update']:
            self.required_permission = 'roles.change_role'
        elif self.action == 'destroy':
            self.required_permission = 'roles.delete_role'
        return super().get_permissions()

class PermissionViewSet(viewsets.ModelViewSet):
    queryset = Permission.objects.all()
    serializer_class = PermissionSerializer
    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = 'permissions.view_permission'

    def get_permissions(self):
        if self.action == 'create':
            self.required_permission = 'permissions.add_permission'
        elif self.action in ['update', 'partial_update']:
            self.required_permission = 'permissions.change_permission'
        elif self.action == 'destroy':
            self.required_permission = 'permissions.delete_permission'
        return super().get_permissions()

class MFAMethodViewSet(viewsets.ModelViewSet):
    serializer_class = MFAMethodSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return MFAMethod.objects.all()
        return MFAMethod.objects.filter(user=user)

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission_classes = [IsAuthenticated]
        else:
            permission_classes = [IsAuthenticated, IsOwner]
        return [permission() for permission in permission_classes]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class BiometricProfileViewSet(viewsets.ModelViewSet):
    serializer_class = BiometricProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return BiometricProfile.objects.all()
        return BiometricProfile.objects.filter(user=user)

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission_classes = [IsAuthenticated]
        else:
            permission_classes = [IsAuthenticated, IsOwner]
        return [permission() for permission in permission_classes]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class TrustedDeviceViewSet(viewsets.ModelViewSet):
    serializer_class = TrustedDeviceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return TrustedDevice.objects.all()
        return TrustedDevice.objects.filter(user=user)

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission_classes = [IsAuthenticated]
        else:
            permission_classes = [IsAuthenticated, IsOwner]
        return [permission() for permission in permission_classes]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class SignupView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            refresh = RefreshToken.for_user(user)
            return Response({
                'user': {
                    'id': user.id,
                    'email': user.email,
                    'phone': user.phone,
                },
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class LoginView(APIView):
    """
    Endpoint de connexion.
    Retourne :
    - Si MFA désactivé : access + refresh tokens
    - Si MFA activé : mfa_token (JWT court) + liste des méthodes MFA disponibles
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']

            # Enregistrer la tentative de connexion (succès avant MFA)
            log_user_activity(
                user, 
                'login_attempt', 
                f"Connexion initiée depuis {request.META.get('REMOTE_ADDR', 'inconnue')}",
                request
            )

            # Vérifier si MFA activé
            if user.mfa_enabled:
                # Générer un token temporaire (valable 5 minutes)
                mfa_token = RefreshToken.for_user(user)
                mfa_token.access_token.set_exp(lifetime=timedelta(minutes=5))
                
                # Optionnel : stocker en session (mais on utilise le token)
                # request.session['pre_auth_user_id'] = user.id
                # request.session['pre_auth_expires'] = time.time() + 300

                # Récupérer les méthodes MFA actives
                mfa_methods = MFAMethod.objects.filter(
                    user=user, 
                    is_active=True
                ).values_list('method_type', flat=True)

                return Response({
                    'mfa_required': True,
                    'mfa_methods': list(mfa_methods),
                    'mfa_token': str(mfa_token.access_token)
                }, status=status.HTTP_200_OK)
            else:
                # Pas de MFA, générer les tokens finaux
                refresh = RefreshToken.for_user(user)
                
                # Enregistrer la connexion réussie
                log_user_activity(
                    user,
                    'login_success',
                    f"Connexion réussie depuis {request.META.get('REMOTE_ADDR', 'inconnue')}",
                    request
                )
                
                return Response({
                    'access': str(refresh.access_token),
                    'refresh': str(refresh),
                    'user': {
                        'id': user.id,
                        'email': user.email,
                        'phone': user.phone,
                    }
                })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get('refresh')
            if not refresh_token:
                return Response({'error': 'Refresh token is required'}, status=status.HTTP_400_BAD_REQUEST)
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response({'message': 'Déconnexion réussie'}, status=status.HTTP_205_RESET_CONTENT)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

class TOTPEnableView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if MFAMethod.objects.filter(user=user, method_type='totp', is_active=True).exists():
            return Response({'detail': 'TOTP déjà activé.'}, status=status.HTTP_400_BAD_REQUEST)

        secret = pyotp.random_base32()
        totp_uri = pyotp.totp.TOTP(secret).provisioning_uri(name=user.email, issuer_name="MaPlateforme")
        qr = qrcode.make(totp_uri)
        buffer = io.BytesIO()
        qr.save(buffer, format="PNG")
        qr_base64 = base64.b64encode(buffer.getvalue()).decode()
        request.session['totp_secret'] = secret
        request.session['totp_secret_expires'] = 600
        return Response({
            'secret': secret,
            'uri': totp_uri,
            'qr_code': f"data:image/png;base64,{qr_base64}"
        })

    def post(self, request):
        secret = request.session.get('totp_secret')
        if not secret:
            return Response({'detail': 'Session expirée ou secret manquant. Recommencez.'},
                            status=status.HTTP_400_BAD_REQUEST)
        data = request.data.copy()
        data['secret'] = secret
        serializer = TOTPVerifySerializer(data=data, context={'request': request})
        if serializer.is_valid():
            user = request.user
            MFAMethod.objects.filter(user=user, method_type='totp').delete()
            MFAMethod.objects.create(
                user=user,
                method_type='totp',
                secret=secret,
                is_active=True
            )
            user.mfa_enabled = True
            user.save(update_fields=['mfa_enabled'])
            del request.session['totp_secret']
            return Response({'detail': 'TOTP activé avec succès.'})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class TOTPDisableView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = TOTPDisableSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            user = request.user
            deleted, _ = MFAMethod.objects.filter(user=user, method_type='totp').delete()
            if deleted:
                if not MFAMethod.objects.filter(user=user, is_active=True).exists():
                    user.mfa_enabled = False
                    user.save(update_fields=['mfa_enabled'])
                return Response({'detail': 'TOTP désactivé.'})
            else:
                return Response({'detail': 'Aucune méthode TOTP active.'}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class TOTPVerifyView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        identifier = request.data.get('identifier')
        code = request.data.get('code')
        if not identifier or not code:
            return Response({'detail': 'Identifiant et code requis.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            if '@' in identifier:
                user = User.objects.get(email=identifier)
            else:
                user = User.objects.get(phone=identifier)
        except User.DoesNotExist:
            return Response({'detail': 'Utilisateur non trouvé.'}, status=status.HTTP_404_NOT_FOUND)
        try:
            mfa_method = MFAMethod.objects.get(user=user, method_type='totp', is_active=True)
        except MFAMethod.DoesNotExist:
            return Response({'detail': 'TOTP non activé pour cet utilisateur.'}, status=status.HTTP_400_BAD_REQUEST)
        totp = pyotp.TOTP(mfa_method.secret)
        if totp.verify(code, valid_window=1):
            refresh = RefreshToken.for_user(user)
            return Response({
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'user': {
                    'id': user.id,
                    'email': user.email,
                    'phone': user.phone,
                }
            })
        else:
            return Response({'detail': 'Code invalide.'}, status=status.HTTP_400_BAD_REQUEST)

class MFAVerifyView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        mfa_token_str = request.data.get('mfa_token')
        code = request.data.get('code')
        method = request.data.get('method')
        if not mfa_token_str or not code or not method:
            return Response({'detail': 'mfa_token, code et method requis.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            mfa_token = AccessToken(mfa_token_str)
            if not mfa_token.get('mfa', False):
                return Response({'detail': 'Token MFA invalide.'}, status=status.HTTP_401_UNAUTHORIZED)
            user_id = mfa_token['user_id']
            user = User.objects.get(id=user_id)
        except (TokenError, User.DoesNotExist):
            return Response({'detail': 'Token MFA invalide ou expiré.'}, status=status.HTTP_401_UNAUTHORIZED)
        if method == 'totp':
            try:
                mfa_method = MFAMethod.objects.get(user=user, method_type='totp', is_active=True)
            except MFAMethod.DoesNotExist:
                return Response({'detail': 'Méthode TOTP non active.'}, status=status.HTTP_400_BAD_REQUEST)
            totp = pyotp.TOTP(mfa_method.secret)
            if not totp.verify(code, valid_window=1):
                return Response({'detail': 'Code invalide.'}, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response({'detail': 'Méthode non supportée.'}, status=status.HTTP_400_BAD_REQUEST)
        refresh = RefreshToken.for_user(user)
        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': {
                'id': user.id,
                'email': user.email,
                'phone': user.phone,
            }
        })