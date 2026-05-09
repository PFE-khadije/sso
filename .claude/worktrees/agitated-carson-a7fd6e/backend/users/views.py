import pyotp
import qrcode
import io
import base64
import uuid
from datetime import timedelta
from rest_framework import status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.decorators import action
from django.utils import timezone
from datetime import timedelta
from django.core.cache import cache
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
        token = request.auth  # OAuth2 access token instance
        scopes = token.scope.split() if token and token.scope else []

        # Always include the mandatory 'sub' claim
        claims = {"sub": str(user.id)}

        # Email scope
        if "email" in scopes:
            claims.update({
                "email": user.email,
                "email_verified": True,
            })

        # Profile scope
        if "profile" in scopes:
            claims.update({
                "given_name": user.first_name or "",
                "family_name": user.last_name or "",
                "name": f"{user.first_name} {user.last_name}".strip(),
                "preferred_username": user.email.split('@')[0] if user.email else "",
            })

        # Phone scope
        if "phone" in scopes:
            claims.update({
                "phone_number": str(user.phone) if user.phone else None,
                "phone_number_verified": False,
            })

        return Response(claims)

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


_TOTP_ENROLL_TTL = 300  # seconds — enrollment session expires in 5 min

class TOTPEnableView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if MFAMethod.objects.filter(user=user, method_type='totp', is_active=True).exists():
            return Response({'detail': 'TOTP already activated.'}, status=status.HTTP_400_BAD_REQUEST)

        secret = pyotp.random_base32()
        # Store secret server-side keyed by a short-lived enrollment token
        enrollment_token = uuid.uuid4().hex
        cache.set(f'totp_enroll:{user.id}:{enrollment_token}', secret, timeout=_TOTP_ENROLL_TTL)

        totp_uri = pyotp.totp.TOTP(secret).provisioning_uri(name=user.email, issuer_name="MaPlateforme")
        qr = qrcode.make(totp_uri)
        buffer = io.BytesIO()
        qr.save(buffer, format="PNG")
        qr_base64 = base64.b64encode(buffer.getvalue()).decode()
        # Return the enrollment_token instead of the raw secret
        return Response({
            'enrollment_token': enrollment_token,
            'uri': totp_uri,
            'qr_code': f"data:image/png;base64,{qr_base64}",
        })

    def post(self, request):
        enrollment_token = request.data.get('enrollment_token')
        code = request.data.get('code')
        if not enrollment_token or not code:
            return Response({'detail': 'enrollment_token and code are required.'}, status=status.HTTP_400_BAD_REQUEST)

        user = request.user
        cache_key = f'totp_enroll:{user.id}:{enrollment_token}'
        secret = cache.get(cache_key)
        if not secret:
            return Response({'detail': 'Enrollment session expired or invalid. Please restart.'}, status=status.HTTP_400_BAD_REQUEST)

        totp = pyotp.TOTP(secret)
        if not totp.verify(code, valid_window=1):
            return Response({'detail': 'Invalid code.'}, status=status.HTTP_400_BAD_REQUEST)

        # Consume the enrollment token so it cannot be replayed
        cache.delete(cache_key)

        from .utils import encrypt_secret, decrypt_secret
        MFAMethod.objects.filter(user=user, method_type='totp').delete()
        MFAMethod.objects.create(
            user=user,
            method_type='totp',
            secret=encrypt_secret(secret),
            is_active=True,
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

        _INVALID = Response({'detail': 'Code invalide.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            if '@' in identifier:
                user = User.objects.get(email=identifier)
            else:
                user = User.objects.get(phone=identifier)
        except User.DoesNotExist:
            # Return same response as wrong code to prevent user enumeration
            return _INVALID
        try:
            mfa_method = MFAMethod.objects.get(user=user, method_type='totp', is_active=True)
        except MFAMethod.DoesNotExist:
            return _INVALID
        from .utils import decrypt_secret
        totp = pyotp.TOTP(decrypt_secret(mfa_method.secret))
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
        return _INVALID


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
            from .utils import decrypt_secret
            totp = pyotp.TOTP(decrypt_secret(mfa_method.secret))
            if not totp.verify(code, valid_window=1):
                return Response({'detail': 'Code invalide.'}, status=400)
        elif method == 'email':
            from .utils import verify_otp
            otp_key = f'mfa_email:{user.id}'
            if not verify_otp(otp_key, code):
                return Response({'detail': 'Code invalide ou expiré.'}, status=400)
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

class MFASendEmailOTPView(APIView):
    """Send a one-time code to the user's email during the MFA step.

    Requires the mfa_token issued by LoginView so we know who to send to
    without exposing the user's email in the request body.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        mfa_token_str = request.data.get('mfa_token')
        if not mfa_token_str:
            return Response({'detail': 'mfa_token requis.'}, status=400)
        try:
            mfa_token = AccessToken(mfa_token_str)
            if not mfa_token.get('mfa', False):
                return Response({'detail': 'Token MFA invalide.'}, status=401)
            user = User.objects.get(id=mfa_token['user_id'])
        except (TokenError, User.DoesNotExist):
            return Response({'detail': 'Token MFA invalide ou expiré.'}, status=401)

        if not MFAMethod.objects.filter(user=user, method_type='email', is_active=True).exists():
            return Response({'detail': 'Email MFA non activé pour cet utilisateur.'}, status=400)

        from .utils import generate_otp, store_otp, send_email_otp
        otp = generate_otp()
        store_otp(f'mfa_email:{user.id}', otp, ttl=300)
        send_email_otp(user.email, otp)
        return Response({'detail': 'Code envoyé par email.'})


class UserAuthMethodsView(APIView):
    permission_classes = [AllowAny]
    def get(self, request):
        identifier = request.query_params.get('identifier')
        if not identifier:
            return Response({'error': 'identifier required'}, status=400)

        # Always return the same shape regardless of whether the user exists
        # to prevent account enumeration
        _default = {
            'has_password': False,
            'has_mfa': False,
            'has_biometric': False,
            'mfa_methods': [],
        }
        try:
            if '@' in identifier:
                user = User.objects.get(email=identifier)
            else:
                user = User.objects.get(phone=identifier)
        except User.DoesNotExist:
            return Response(_default)

        return Response({
            'has_password': True,
            'has_mfa': user.mfa_enabled,
            'has_biometric': user.biometric_enabled,
            'mfa_methods': list(MFAMethod.objects.filter(user=user, is_active=True).values_list('method_type', flat=True)) if user.mfa_enabled else [],
        })


# ── Email verification ────────────────────────────────────────────────────────

class EmailVerifyRequestView(APIView):
    """Send (or re-send) a verification link to the authenticated user's email."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        import secrets as _secrets
        from django.core.mail import send_mail
        from django.conf import settings as _settings

        user = request.user
        if user.email_verified:
            return Response({'detail': 'Email déjà vérifié.'}, status=400)

        token = _secrets.token_urlsafe(32)
        user.email_verification_token = token
        user.email_verification_sent_at = timezone.now()
        user.save(update_fields=['email_verification_token', 'email_verification_sent_at'])

        verify_url = f"{request.scheme}://{request.get_host()}/api/email/verify/confirm/?token={token}"
        send_mail(
            subject="Vérifiez votre adresse email",
            message=f"Cliquez sur ce lien pour vérifier votre email (valable 24h) :\n{verify_url}",
            from_email=getattr(_settings, 'DEFAULT_FROM_EMAIL', 'noreply@example.com'),
            recipient_list=[user.email],
        )
        return Response({'detail': 'Email de vérification envoyé.'})


class EmailVerifyConfirmView(APIView):
    """Confirm an email address using the token sent by EmailVerifyRequestView."""
    permission_classes = [AllowAny]

    def get(self, request):
        token = request.query_params.get('token')
        if not token:
            return Response({'detail': 'Token manquant.'}, status=400)
        try:
            user = User.objects.get(email_verification_token=token)
        except User.DoesNotExist:
            return Response({'detail': 'Token invalide.'}, status=400)

        # Token expires after 24 hours
        if user.email_verification_sent_at:
            age = timezone.now() - user.email_verification_sent_at
            if age.total_seconds() > 86400:
                return Response({'detail': 'Token expiré. Veuillez en demander un nouveau.'}, status=400)

        user.email_verified = True
        user.email_verification_token = None
        user.email_verification_sent_at = None
        user.save(update_fields=['email_verified', 'email_verification_token', 'email_verification_sent_at'])
        return Response({'detail': 'Email vérifié avec succès.'})


# ── Password reset ────────────────────────────────────────────────────────────

_RESET_OTP_TTL = 600  # 10 minutes

class PasswordResetRequestView(APIView):
    """Generate and email a 6-digit reset code. Always returns 200 to avoid enumeration."""
    permission_classes = [AllowAny]

    def post(self, request):
        from .utils import generate_otp, store_otp, send_email_otp
        email = request.data.get('email', '').strip().lower()
        if not email:
            return Response({'detail': 'Email requis.'}, status=400)
        try:
            user = User.objects.get(email=email)
            otp = generate_otp()
            store_otp(f'pwd_reset:{user.id}', otp, ttl=_RESET_OTP_TTL)
            send_email_otp(email, otp)
        except User.DoesNotExist:
            pass  # Silently ignore to prevent enumeration
        return Response({'detail': 'Si cet email existe, un code a été envoyé.'})


class PasswordResetConfirmView(APIView):
    """Verify the reset code and set a new password."""
    permission_classes = [AllowAny]

    def post(self, request):
        from .utils import verify_otp
        from django.contrib.auth.password_validation import validate_password
        from django.core.exceptions import ValidationError as DjangoValidationError

        email = request.data.get('email', '').strip().lower()
        code = request.data.get('code', '').strip()
        new_password = request.data.get('new_password', '')

        if not email or not code or not new_password:
            return Response({'detail': 'email, code et new_password sont requis.'}, status=400)

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({'detail': 'Code invalide ou expiré.'}, status=400)

        if not verify_otp(f'pwd_reset:{user.id}', code):
            return Response({'detail': 'Code invalide ou expiré.'}, status=400)

        try:
            validate_password(new_password, user)
        except DjangoValidationError as e:
            return Response({'detail': list(e.messages)}, status=400)

        user.set_password(new_password)
        user.save(update_fields=['password'])
        return Response({'detail': 'Mot de passe réinitialisé avec succès.'})