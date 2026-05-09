from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    UserViewSet, RoleViewSet, PermissionViewSet,
    MFAMethodViewSet, BiometricProfileViewSet, TrustedDeviceViewSet, SignupView, LoginView, LogoutView,
    TOTPEnableView, TOTPDisableView, TOTPVerifyView, MFAVerifyView, UserInfoView, UserMeView,
    UserAuthMethodsView, MFASendEmailOTPView,
    EmailVerifyRequestView, EmailVerifyConfirmView,
    PasswordResetRequestView, PasswordResetConfirmView,
)
from .views_dashboard import UserAuthorizedAppsView, UserRevokeAppView, UserActivityView ,UserDevicesView, UserDeviceDetailView 
from rest_framework_simplejwt.views import TokenRefreshView
from .views_biometric import BiometricEnrollView, BiometricLoginView,BiometricStatusView, BiometricDeleteView
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
    path('userinfo/', UserInfoView.as_view(), name='userinfo'),
    path('signup/', SignupView.as_view(), name='signup'),
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('mfa/verify/', MFAVerifyView.as_view(), name='mfa_verify'),
    path('mfa/totp/enable/', TOTPEnableView.as_view(), name='totp_enable'),
    path('mfa/totp/disable/', TOTPDisableView.as_view(), name='totp_disable'),
    path('mfa/totp/verify/', TOTPVerifyView.as_view(), name='totp_verify'),
    path('user/apps/', UserAuthorizedAppsView.as_view(), name='user-apps'),
    path('user/apps/<int:app_id>/revoke/', UserRevokeAppView.as_view(), name='user-revoke-app'),
    path('user/devices/', UserDevicesView.as_view(), name='user-devices'),
    path('user/devices/<int:device_id>/', UserDeviceDetailView.as_view(), name='user-device-detail'),
    path('user/activity/', UserActivityView.as_view(), name='user-activity'),
    path('biometric/enroll/', BiometricEnrollView.as_view(), name='biometric-enroll'),
    path('biometric/login/', BiometricLoginView.as_view(), name='biometric-login'),
    path('biometric/status/', BiometricStatusView.as_view(), name='biometric-status'),
    path('biometric/delete/', BiometricDeleteView.as_view(), name='biometric-delete'),
    path('user/has-client/', UserHasClientView.as_view(), name='user-has-client'),
    path('user/auth-methods/', UserAuthMethodsView.as_view(), name='auth-methods'),
    path('mfa/email/send/', MFASendEmailOTPView.as_view(), name='mfa-email-send'),
    path('email/verify/request/', EmailVerifyRequestView.as_view(), name='email-verify-request'),
    path('email/verify/confirm/', EmailVerifyConfirmView.as_view(), name='email-verify-confirm'),
    path('password/reset/request/', PasswordResetRequestView.as_view(), name='password-reset-request'),
    path('password/reset/confirm/', PasswordResetConfirmView.as_view(), name='password-reset-confirm'),
]