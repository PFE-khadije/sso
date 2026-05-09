from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    UserViewSet, RoleViewSet, PermissionViewSet,
    MFAMethodViewSet, BiometricProfileViewSet, TrustedDeviceViewSet,
    SignupView, LoginView, LogoutView,
    TOTPEnableView, TOTPDisableView, TOTPVerifyView, MFAVerifyView,
    UserInfoView, UserMeView, UserAuthMethodsView, ChangePasswordView,
    SendOTPView, EmailOTPEnableView, SMSOTPEnableView, PasswordResetRequestView, PasswordResetConfirmView,
    FCMTokenView, UnlockWithMFAView,
)
from .views_qr import QRLoginGenerateView, QRLoginConfirmView, QRLoginStatusView
from .views_dashboard import UserAuthorizedAppsView, UserRevokeAppView, UserActivityView ,UserDevicesView, UserDeviceDetailView
from rest_framework_simplejwt.views import TokenRefreshView
from .views_biometric import BiometricEnrollView, BiometricLoginView, BiometricStatusView, BiometricDeleteView, BiometricIdentifyView
from .views_identity import IdentityStatusView, IdentityUploadView
from clients.views import UserHasClientView
router = DefaultRouter()
router.register(r'users', UserViewSet)
router.register(r'roles', RoleViewSet)
router.register(r'permissions', PermissionViewSet)
router.register(r'mfa-methods', MFAMethodViewSet,basename='mfamethod')
router.register(r'biometric-profiles', BiometricProfileViewSet, basename='biometricprofile')
router.register(r'trusted-devices', TrustedDeviceViewSet,basename='trusteddevice' )

urlpatterns = [
    path('', include(router.urls)),
    path('user/me/', UserMeView.as_view(), name='user-me'),
    path('user/change-password/', ChangePasswordView.as_view(), name='change-password'),
    path('userinfo/', UserInfoView.as_view(), name='userinfo'),
    path('signup/', SignupView.as_view(), name='signup'),
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('mfa/verify/', MFAVerifyView.as_view(), name='mfa_verify'),
    path('mfa/send-otp/', SendOTPView.as_view(), name='mfa_send_otp'),
    path('mfa/totp/enable/', TOTPEnableView.as_view(), name='totp_enable'),
    path('mfa/totp/disable/', TOTPDisableView.as_view(), name='totp_disable'),
    path('mfa/totp/verify/', TOTPVerifyView.as_view(), name='totp_verify'),
    path('mfa/email/enable/', EmailOTPEnableView.as_view(), name='email_otp_enable'),
    path('mfa/sms/enable/', SMSOTPEnableView.as_view(), name='sms_otp_enable'),
    path('user/apps/', UserAuthorizedAppsView.as_view(), name='user-apps'),
    path('user/apps/<int:app_id>/revoke/', UserRevokeAppView.as_view(), name='user-revoke-app'),
    path('user/devices/', UserDevicesView.as_view(), name='user-devices'),
    path('user/devices/<int:device_id>/', UserDeviceDetailView.as_view(), name='user-device-detail'),
    path('user/activity/', UserActivityView.as_view(), name='user-activity'),
    path('biometric/enroll/', BiometricEnrollView.as_view(), name='biometric-enroll'),
    path('biometric/login/', BiometricLoginView.as_view(), name='biometric-login'),
    path('biometric/status/', BiometricStatusView.as_view(), name='biometric-status'),
    path('biometric/delete/', BiometricDeleteView.as_view(), name='biometric-delete'),
    path('biometric/identify/', BiometricIdentifyView.as_view(), name='biometric-identify'),
    path('user/has-client/', UserHasClientView.as_view(), name='user-has-client'),
    path('user/auth-methods/', UserAuthMethodsView.as_view(), name='auth-methods'),
    path('password-reset/request/', PasswordResetRequestView.as_view(), name='password-reset-request'),
    path('password-reset/confirm/', PasswordResetConfirmView.as_view(), name='password-reset-confirm'),
    path('identity/status/', IdentityStatusView.as_view(), name='identity-status'),
    path('identity/upload/', IdentityUploadView.as_view(), name='identity-upload'),
    path('user/fcm-token/', FCMTokenView.as_view(), name='fcm-token'),
    path('login/unlock-with-mfa/', UnlockWithMFAView.as_view(), name='unlock-with-mfa'),
    path('qr-login/generate/', QRLoginGenerateView.as_view(), name='qr-login-generate'),
    path('qr-login/confirm/', QRLoginConfirmView.as_view(), name='qr-login-confirm'),
    path('qr-login/<uuid:token>/status/', QRLoginStatusView.as_view(), name='qr-login-status'),
]