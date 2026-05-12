import pyotp
import qrcode
import io
import base64
from datetime import timedelta
from django.conf import settings
from rest_framework import status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.decorators import action
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken
from rest_framework_simplejwt.exceptions import TokenError
from oauth2_provider.contrib.rest_framework import OAuth2Authentication
from rest_framework_simplejwt.authentication import JWTAuthentication
from .models import PasswordResetToken, User, Role, Permission, MFAMethod, BiometricProfile, TrustedDevice, LoginLockout
from .serializers import (
    UserSerializer, RoleSerializer, PermissionSerializer,
    MFAMethodSerializer, BiometricProfileSerializer, TrustedDeviceSerializer,
    UserRegistrationSerializer, LoginSerializer,
    TOTPVerifySerializer, TOTPDisableSerializer
)
from .permissions import HasPermission, IsOwner
from .utils import (
    log_user_activity,
    generate_otp,
    send_password_reset_email, store_otp, verify_otp,
    send_email_otp, send_sms_otp, send_verification_email,
)


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
                "email_verified": user.email_verified,
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
                "phone_number_verified": bool(user.phone),
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
            "email_verified": user.email_verified,
            "phone": str(user.phone) if user.phone else None,
            "phone_verified": bool(user.phone),
            "preferred_username": user.email.split('@')[0] if user.email else "",
        }
        return Response(data, status=status.HTTP_200_OK)


class UserMeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)

    def patch(self, request):
        allowed = {k: v for k, v in request.data.items() if k in ('first_name', 'last_name', 'phone')}
        serializer = UserSerializer(request.user, data=allowed, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        current = request.data.get('current_password')
        new_pw = request.data.get('new_password')
        if not current or not new_pw:
            return Response({'error': 'current_password et new_password requis.'}, status=status.HTTP_400_BAD_REQUEST)
        if not request.user.check_password(current):
            return Response({'error': 'Mot de passe actuel incorrect.'}, status=status.HTTP_400_BAD_REQUEST)
        if len(new_pw) < 8:
            return Response({'error': 'Le mot de passe doit contenir au moins 8 caractères.'}, status=status.HTTP_400_BAD_REQUEST)
        request.user.set_password(new_pw)
        request.user.save(update_fields=['password'])
        return Response({'message': 'Mot de passe modifié avec succès.'})


class FCMTokenView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from .models import FCMToken
        token = request.data.get('token')
        platform = request.data.get('platform', 'android')
        if not token:
            return Response({'error': 'token requis'}, status=status.HTTP_400_BAD_REQUEST)
        FCMToken.objects.update_or_create(token=token, defaults={'user': request.user, 'platform': platform})
        return Response({'message': 'Token enregistré'})

    def delete(self, request):
        from .models import FCMToken
        token = request.data.get('token')
        if token:
            FCMToken.objects.filter(user=request.user, token=token).delete()
        return Response({'message': 'Token supprimé'})


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
    

@method_decorator(ratelimit(key='ip', rate='10/h', method='POST', block=True), name='post')
class SignupView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            send_verification_email(user)
            return Response({
                'message': 'Compte créé. Vérifiez votre email pour activer votre compte.',
                'email': user.email,
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@method_decorator(ratelimit(key='ip', rate='10/h', method='POST', block=True), name='post')
@method_decorator(ratelimit(key='ip', rate='30/h', method='GET', block=True), name='get')
class VerifyEmailView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get('email', '').strip().lower()
        code = request.data.get('code', '').strip()
        if not email or not code:
            return Response({'error': 'email et code requis.'}, status=400)
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({'error': 'Utilisateur introuvable.'}, status=404)
        if user.email_verified:
            return Response({'message': 'Email déjà vérifié. Vous pouvez vous connecter.'})
        if not verify_otp(f'email_verify:{user.id}', code):
            return Response({'error': 'Code invalide ou expiré.'}, status=400)
        user.email_verified = True
        user.save(update_fields=['email_verified'])
        refresh = RefreshToken.for_user(user)
        return Response({
            'message': 'Email vérifié avec succès.',
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': UserSerializer(user).data,
        })

    def get(self, request):
        """Renvoie un nouveau code de vérification."""
        email = request.query_params.get('email', '').strip().lower()
        if not email:
            return Response({'error': 'email requis.'}, status=400)
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({'error': 'Utilisateur introuvable.'}, status=404)
        if user.email_verified:
            return Response({'message': 'Email déjà vérifié.'})
        send_verification_email(user)
        masked = f"{email[:3]}***@{email.split('@')[-1]}"
        return Response({'message': f'Code renvoyé à {masked}.'})
        
@method_decorator(ratelimit(key='ip', rate='100/m', method='POST', block=True), name='post')
@method_decorator(csrf_exempt, name='dispatch')
class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        raw_id = request.data.get('identifier', '').lower().strip()

        # ── Lockout check ────────────────────────────────────────────────
        if raw_id:
            lockout, _ = LoginLockout.objects.get_or_create(identifier=raw_id)
            if lockout.is_locked():
                has_mfa = False
                try:
                    u = User.objects.get(email=raw_id) if '@' in raw_id else User.objects.get(phone=raw_id)
                    has_mfa = u.mfa_enabled
                except User.DoesNotExist:
                    pass
                return Response({
                    'error': 'account_locked',
                    'locked_until': lockout.locked_until.isoformat(),
                    'remaining_seconds': lockout.remaining_seconds(),
                    'can_unlock_with_mfa': has_mfa,
                }, status=429)

        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']

            if not user.email_verified:
                return Response({
                    'error': 'email_not_verified',
                    'message': 'Veuillez vérifier votre adresse email avant de vous connecter.',
                    'email': user.email,
                }, status=status.HTTP_403_FORBIDDEN)

            # Reset lockout on successful password auth
            if raw_id:
                LoginLockout.objects.filter(identifier=raw_id).update(attempts=0, locked_until=None)

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
                access_token['mfa'] = True
                access_token.set_exp(lifetime=timedelta(minutes=5))
                mfa_methods = list(MFAMethod.objects.filter(user=user, is_active=True).values_list('method_type', flat=True))
                if not getattr(settings, 'SMS_ENABLED', False):
                    mfa_methods = [m for m in mfa_methods if m != 'sms']
                if not mfa_methods:
                    # All configured methods are unavailable (e.g. only SMS, not yet enabled).
                    # Fall through to a normal login so the user is not permanently locked out.
                    refresh = RefreshToken.for_user(user)
                    user_data = UserSerializer(user).data
                    return Response({
                        'access': str(refresh.access_token),
                        'refresh': str(refresh),
                        'user': user_data,
                    })
                return Response({
                    'mfa_required': True,
                    'mfa_methods': mfa_methods,
                    'mfa_token': str(access_token)
                })
            else:
                refresh = RefreshToken.for_user(user)
                user_data = UserSerializer(user).data
                return Response({
                    'access': str(refresh.access_token),
                    'refresh': str(refresh),
                    'user': user_data,
                })

        # ── Increment failed attempt counter ─────────────────────────────
        if raw_id:
            lockout, _ = LoginLockout.objects.get_or_create(identifier=raw_id)
            lockout.attempts += 1
            if lockout.attempts >= 5:
                lockout.locked_until = timezone.now() + timedelta(minutes=15)
            lockout.save()

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
        totp_uri = pyotp.totp.TOTP(secret).provisioning_uri(name=user.email, issuer_name="NovaGard")
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


@method_decorator(ratelimit(key='ip', rate='10/m', method='POST', block=True), name='post')
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


@method_decorator(ratelimit(key='ip', rate='100/m', method='POST', block=True), name='post')
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
        
        if method == 'totp':
            try:
                mfa_method = MFAMethod.objects.get(user=user, method_type='totp', is_active=True)
            except MFAMethod.DoesNotExist:
                return Response({'detail': 'Méthode TOTP non active.'}, status=400)
            totp = pyotp.TOTP(mfa_method.secret)
            if not totp.verify(code, valid_window=1):
                return Response({'detail': 'Code invalide.'}, status=400)
        elif method in ('email', 'sms'):
            try:
                MFAMethod.objects.get(user=user, method_type=method, is_active=True)
            except MFAMethod.DoesNotExist:
                return Response({'detail': f'Méthode {method} non active.'}, status=400)
            redis_key = f'mfa_otp:{method}:{user.id}'
            if not verify_otp(redis_key, code):
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

@method_decorator(ratelimit(key='ip', rate='5/h', method='POST', block=True), name='post')
class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get('email')
        if not email:
            return Response({'error': 'Email required'}, status=400)
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            # Do not reveal existence – return generic success
            return Response({'message': 'If an account with that email exists, a reset link has been sent.'}, status=200)
        send_password_reset_email(user, request)
        return Response({'message': 'Reset link sent.'}, status=200)


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        token = request.query_params.get('token')
        invalid = True
        if token:
            try:
                reset = PasswordResetToken.objects.get(token=token, used=False)
                if reset.created_at >= timezone.now() - timedelta(hours=1):
                    invalid = False
            except PasswordResetToken.DoesNotExist:
                pass
        return render(request, 'users/password_reset_confirm.html', {'invalid': invalid})

    def post(self, request):
        token = request.query_params.get('token')
        new_password = request.data.get('new_password')
        if not token or not new_password:
            return Response({'error': 'Token and new password required'}, status=400)

        try:
            reset = PasswordResetToken.objects.get(token=token, used=False)
        except PasswordResetToken.DoesNotExist:
            return Response({'error': 'Invalid or expired token'}, status=400)

        # Optional: expire after 1 hour
        if reset.created_at < timezone.now() - timedelta(hours=1):
            return Response({'error': 'Token expired'}, status=400)

        user = reset.user
        user.set_password(new_password)
        user.save()
        reset.used = True
        reset.save()
        return Response({'message': 'Password reset successful'}, status=200)

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


@method_decorator(ratelimit(key='ip', rate='100/m', method='POST', block=True), name='post')
class SendOTPView(APIView):
    """
    Trigger sending an email or SMS OTP during the MFA login flow.
    Called after LoginView returns mfa_required=True.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        mfa_token_str = request.data.get('mfa_token')
        method = request.data.get('method')

        if not mfa_token_str or not method:
            return Response({'detail': 'mfa_token et method requis.'}, status=400)
        if method not in ('email', 'sms'):
            return Response({'detail': 'Méthode invalide. Utilisez email ou sms.'}, status=400)

        try:
            mfa_token = AccessToken(mfa_token_str)
            if not mfa_token.get('mfa', False):
                return Response({'detail': 'Token MFA invalide.'}, status=401)
            user = User.objects.get(id=mfa_token['user_id'])
        except (TokenError, User.DoesNotExist):
            return Response({'detail': 'Token MFA invalide ou expiré.'}, status=401)

        try:
            mfa_method = MFAMethod.objects.get(user=user, method_type=method, is_active=True)
        except MFAMethod.DoesNotExist:
            return Response({'detail': f'Méthode {method} non activée pour cet utilisateur.'}, status=400)

        otp = generate_otp()
        store_otp(f'mfa_otp:{method}:{user.id}', otp, ttl=300)

        if method == 'email':
            destination = mfa_method.destination or user.email
            send_email_otp(destination, otp)
            masked = f"{destination[:3]}***@{destination.split('@')[-1]}"
        else:
            if not getattr(settings, 'SMS_ENABLED', False):
                return Response({'detail': 'Le MFA par SMS n\'est pas disponible pour le moment.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            destination = mfa_method.destination or str(user.phone)
            send_sms_otp(destination, otp)
            masked = f"***{destination[-4:]}"

        return Response({'detail': f'Code envoyé via {method}.', 'destination': masked})


class EmailOTPEnableView(APIView):
    """Enable email OTP as an MFA method for the authenticated user."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Step 1 — send a verification OTP to the user's email."""
        user = request.user
        if not user.email:
            return Response({'detail': 'Aucun email associé au compte.'}, status=400)

        otp = generate_otp()
        store_otp(f'email_enable_otp:{user.id}', otp, ttl=300)
        send_email_otp(user.email, otp)

        masked = f"{user.email[:3]}***@{user.email.split('@')[-1]}"
        return Response({'detail': 'Code envoyé à votre email.', 'email': masked})

    def post(self, request):
        """Step 2 — verify the OTP and activate email MFA."""
        user = request.user
        code = request.data.get('code')
        if not code:
            return Response({'detail': 'Code requis.'}, status=400)

        if not verify_otp(f'email_enable_otp:{user.id}', code):
            return Response({'detail': 'Code invalide ou expiré.'}, status=400)

        MFAMethod.objects.update_or_create(
            user=user,
            method_type='email',
            defaults={'destination': user.email, 'is_active': True},
        )
        user.mfa_enabled = True
        user.save(update_fields=['mfa_enabled'])
        return Response({'detail': 'Email OTP activé avec succès.'})


class SMSOTPEnableView(APIView):
    """Enable SMS OTP as an MFA method for the authenticated user."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Step 1 — send a verification OTP to the user's phone."""
        if not getattr(settings, 'SMS_ENABLED', False):
            return Response({'detail': 'Le MFA par SMS n\'est pas disponible pour le moment.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        user = request.user
        if not user.phone:
            return Response({'detail': 'Aucun numéro de téléphone associé au compte.'}, status=400)

        phone = str(user.phone)
        otp = generate_otp()
        store_otp(f'sms_enable_otp:{user.id}', otp, ttl=300)
        send_sms_otp(phone, otp)

        masked = f"***{phone[-4:]}"
        return Response({'detail': 'Code envoyé à votre téléphone.', 'phone': masked})

    def post(self, request):
        """Step 2 — verify the OTP and activate SMS MFA."""
        user = request.user
        code = request.data.get('code')
        if not code:
            return Response({'detail': 'Code requis.'}, status=400)

        if not verify_otp(f'sms_enable_otp:{user.id}', code):
            return Response({'detail': 'Code invalide ou expiré.'}, status=400)

        phone = str(user.phone)
        MFAMethod.objects.update_or_create(
            user=user,
            method_type='sms',
            defaults={'destination': phone, 'is_active': True},
        )
        user.mfa_enabled = True
        user.save(update_fields=['mfa_enabled'])
        return Response({'detail': 'SMS OTP activé avec succès.'})


class UnlockWithMFAView(APIView):
    """Unlock a locked account using TOTP. Issues tokens on success."""
    permission_classes = [AllowAny]

    def post(self, request):
        identifier = request.data.get('identifier', '').strip()
        code = request.data.get('code', '').strip()
        if not identifier or not code:
            return Response({'error': 'identifier et code requis'}, status=400)

        try:
            user = User.objects.get(email=identifier) if '@' in identifier else User.objects.get(phone=identifier)
        except User.DoesNotExist:
            return Response({'error': 'Utilisateur introuvable'}, status=404)

        try:
            mfa_method = MFAMethod.objects.get(user=user, method_type='totp', is_active=True)
        except MFAMethod.DoesNotExist:
            return Response({'error': 'TOTP non activé pour ce compte'}, status=400)

        totp = pyotp.TOTP(mfa_method.secret)
        if not totp.verify(code, valid_window=1):
            return Response({'error': 'Code invalide'}, status=400)

        # Clear lockout
        LoginLockout.objects.filter(identifier=identifier.lower()).update(attempts=0, locked_until=None)

        refresh = RefreshToken.for_user(user)
        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': {'id': user.id, 'email': user.email, 'phone': str(user.phone) if user.phone else None},
        })