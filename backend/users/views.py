import pyotp
import qrcode
import io
import base64
from datetime import timedelta
from rest_framework import status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.decorators import action        
from django.utils import timezone
from datetime import timedelta
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken
from rest_framework_simplejwt.exceptions import TokenError
from oauth2_provider.contrib.rest_framework import OAuth2Authentication
from rest_framework_simplejwt.authentication import JWTAuthentication
from oauth2_provider.views.oidc import UserInfoView as BaseUserInfoView
from .models import User, Role, Permission, MFAMethod, BiometricProfile, TrustedDevice   
from .serializers import (
    UserSerializer, RoleSerializer, PermissionSerializer,
    MFAMethodSerializer, BiometricProfileSerializer, TrustedDeviceSerializer,
    UserRegistrationSerializer, LoginSerializer,
    TOTPVerifySerializer, TOTPDisableSerializer
)
from .permissions import HasPermission, IsOwner
from .utils import log_user_activity 

class OIDCUserInfoView(APIView):
    """
    Custom OpenID Connect userinfo endpoint that returns full user claims.
    Uses OAuth2 authentication (valid access token required).
    """
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        data = {
            "sub": str(user.id),
            "email": user.email,
            "email_verified": True,
            "given_name": user.first_name or "",
            "family_name": user.last_name or "",
            "name": f"{user.first_name} {user.last_name}".strip(),
            "preferred_username": user.email.split('@')[0] if user.email else "",
            "phone_number": str(user.phone) if user.phone else None,
            "phone_number_verified": False,
        }
        return Response(data)

class UserInfoView(APIView):
    authentication_classes = [JWTAuthentication, OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        data = {
            "sub": str(user.id),
            "email": user.email,
            "email_verified": True,
            "phone": str(user.phone) if user.phone else None,
            "phone_verified": False,
            "preferred_username": user.email.split('@')[0] if user.email else "",
        }
        return Response(data, status=status.HTTP_200_OK)


class UserMeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = 'users.view_user'

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return User.objects.all()
        client_ids = user.client_memberships.values_list('client_id', flat=True)
        if not client_ids:
            return User.objects.none()
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
        user = serializer.save()
        request_user = self.request.user
        client_ids = request_user.client_memberships.values_list('client_id', flat=True)
        from clients.models import ClientUser
        for client_id in client_ids:
            ClientUser.objects.create(client_id=client_id, user=user, role='member')


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
        return TrustedDevice.objects.filter(user=self.request.user)

    @action(detail=False, methods=['delete'], url_path='revoke-all')
    def revoke_all(self, request):
        self.get_queryset().delete()
        return Response(status=204)
    

class SignupView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            refresh = RefreshToken.for_user(user)
            return Response({
                'user': UserSerializer(user).data,
                'access': str(refresh.access_token),
                'refresh': str(refresh),
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            
            # Get device fingerprint from request headers (client must send)
            fingerprint = request.headers.get('X-Device-Fingerprint')
            trusted_device = None
            if fingerprint:
                try:
                    trusted_device = TrustedDevice.objects.get(
                        user=user,
                        device_fingerprint=fingerprint,
                        expires_at__gt=timezone.now()
                    )
                except TrustedDevice.DoesNotExist:
                    pass
            
            # If trusted device found and still valid, skip MFA
            if trusted_device:
                # Update last_used
                trusted_device.last_used = timezone.now()
                trusted_device.save()
                refresh = RefreshToken.for_user(user)
                user_data = UserSerializer(user).data
                return Response({
                    'access': str(refresh.access_token),
                    'refresh': str(refresh),
                    'user': user_data,
                    'trusted_device': True
                })
            
            # Otherwise, proceed with normal MFA flow
            log_user_activity(user, 'login_attempt', f"Login from {request.META.get('REMOTE_ADDR')}", request)
            
            if user.mfa_enabled:
                refresh = RefreshToken.for_user(user)
                access_token = refresh.access_token
                access_token['mfa'] = True                   # add claim
                access_token.set_exp(lifetime=timedelta(minutes=5))
                mfa_methods = MFAMethod.objects.filter(user=user, is_active=True).values_list('method_type', flat=True)
                return Response({
                    'mfa_required': True,
                    'mfa_methods': list(mfa_methods),
                    'mfa_token': str(access_token)          # return access token
                }) 
            else:
                refresh = RefreshToken.for_user(user)
                user_data = UserSerializer(user).data
                return Response({
                    'access': str(refresh.access_token),
                    'refresh': str(refresh),
                    'user': user_data,
                })
        return Response(serializer.errors, status=400)
    

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
            return Response({'detail': 'TOTP already activated.'}, status=status.HTTP_400_BAD_REQUEST)

        secret = pyotp.random_base32()
        totp_uri = pyotp.totp.TOTP(secret).provisioning_uri(name=user.email, issuer_name="MaPlateforme")
        qr = qrcode.make(totp_uri)
        buffer = io.BytesIO()
        qr.save(buffer, format="PNG")
        qr_base64 = base64.b64encode(buffer.getvalue()).decode()
        return Response({
            'secret': secret,
            'uri': totp_uri,
            'qr_code': f"data:image/png;base64,{qr_base64}"
        })

    def post(self, request):
        secret = request.data.get('secret')
        code = request.data.get('code')
        if not secret or not code:
            return Response({'detail': 'Secret and code are required.'}, status=status.HTTP_400_BAD_REQUEST)

        totp = pyotp.TOTP(secret)
        if not totp.verify(code, valid_window=1):
            return Response({'detail': 'Invalid code.'}, status=status.HTTP_400_BAD_REQUEST)

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
        return Response({'detail': 'TOTP activated successfully.'})


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
                    'phone': str(user.phone) if user.phone else None,
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
        trust_device = request.data.get('trust_device', False)  # new
        device_name = request.data.get('device_name', 'Unknown Device')
        
        if not mfa_token_str or not code or not method:
            return Response({'detail': 'mfa_token, code et method requis.'}, status=400)
        
        try:
            mfa_token = AccessToken(mfa_token_str)
            if not mfa_token.get('mfa', False):
                return Response({'detail': 'Token MFA invalide.'}, status=401)
            user_id = mfa_token['user_id']
            user = User.objects.get(id=user_id)
        except (TokenError, User.DoesNotExist):
            return Response({'detail': 'Token MFA invalide ou expiré.'}, status=401)
        
        # Verify code (TOTP or other)
        # ... (existing verification logic) ...
        if method == 'totp':
            try:
                mfa_method = MFAMethod.objects.get(user=user, method_type='totp', is_active=True)
            except MFAMethod.DoesNotExist:
                return Response({'detail': 'Méthode TOTP non active.'}, status=400)
            totp = pyotp.TOTP(mfa_method.secret)
            if not totp.verify(code, valid_window=1):
                return Response({'detail': 'Code invalide.'}, status=400)
        else:
            return Response({'detail': 'Méthode non supportée.'}, status=400)
        
        # If trust_device is requested, create/update trusted device
        fingerprint = request.headers.get('X-Device-Fingerprint')
        if trust_device and fingerprint:
            # Generate fingerprint if not provided (simplified: use user-agent + IP? 
            # Better: client generates a persistent random ID)
            expires_at = timezone.now() + timedelta(days=30)  # 30 days trust
            TrustedDevice.objects.update_or_create(
                user=user,
                device_fingerprint=fingerprint,
                defaults={
                    'device_name': device_name,
                    'expires_at': expires_at,
                    'last_used': timezone.now()
                }
            )
        
        refresh = RefreshToken.for_user(user)
        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': {
                'id': user.id,
                'email': user.email,
                'phone': str(user.phone) if user.phone else None,
            }
        })

class UserAuthMethodsView(APIView):
    permission_classes = [AllowAny]
    def get(self, request):
        identifier = request.query_params.get('identifier')
        if not identifier:
            return Response({'error': 'identifier required'}, status=400)
        try:
            if '@' in identifier:
                user = User.objects.get(email=identifier)
            else:
                user = User.objects.get(phone=identifier)
        except User.DoesNotExist:
            return Response({'exists': False, 'has_password': False, 'has_mfa': False, 'has_biometric': False})
        
        return Response({
            'exists': True,
            'has_password': True,  
            'has_mfa': user.mfa_enabled,
            'has_biometric': user.biometric_enabled,
            'mfa_methods': list(MFAMethod.objects.filter(user=user, is_active=True).values_list('method_type', flat=True)) if user.mfa_enabled else []
        })        