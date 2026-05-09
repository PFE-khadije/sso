from unittest.mock import patch, MagicMock
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase, APIClient
from rest_framework_simplejwt.tokens import RefreshToken
import pyotp

from .models import Role, Permission, MFAMethod

User = get_user_model()

# Override cache + ratelimit for all tests — no Redis needed locally
TEST_SETTINGS = dict(
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
    RATELIMIT_ENABLE=False,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_user(email='user@example.com', phone='+22612345678', password='StrongPass123!'):
    return User.objects.create_user(email=email, phone=phone, password=password)


# ---------------------------------------------------------------------------
# RBAC (existing tests, cleaned up)
# ---------------------------------------------------------------------------

@override_settings(**TEST_SETTINGS)
class PermissionTests(APITestCase):
    def setUp(self):
        self.view_perm = Permission.objects.create(code='users.view_user')
        self.add_perm = Permission.objects.create(code='users.add_user')
        self.admin_role = Role.objects.create(name='admin')
        self.admin_role.permissions.add(self.view_perm, self.add_perm)

        self.admin_user = make_user('admin@example.com', '+22611111111', 'adminpass123!')
        self.admin_user.roles.add(self.admin_role)
        self.normal_user = make_user('normal@example.com', '+22622222222', 'userpass123!')

    def test_admin_can_view_users(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(reverse('user-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_normal_user_cannot_view_users(self):
        self.client.force_authenticate(user=self.normal_user)
        response = self.client.get(reverse('user-list'))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_create_user(self):
        self.client.force_authenticate(user=self.admin_user)
        data = {
            'email': 'new@example.com',
            'phone': '+22633333333',
            'password': 'testpass123!',
            'password2': 'testpass123!',
        }
        response = self.client.post(reverse('user-list'), data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_normal_user_cannot_create_user(self):
        self.client.force_authenticate(user=self.normal_user)
        data = {
            'email': 'new@example.com',
            'phone': '+22633333333',
            'password': 'testpass123!',
            'password2': 'testpass123!',
        }
        response = self.client.post(reverse('user-list'), data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


# ---------------------------------------------------------------------------
# Signup
# ---------------------------------------------------------------------------

@override_settings(**TEST_SETTINGS)
class SignupTests(APITestCase):
    url = '/api/signup/'

    def test_signup_success(self):
        data = {
            'email': 'new@example.com',
            'phone': '+22699999999',
            'password': 'StrongPass123!',
            'password2': 'StrongPass123!',
        }
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)

    def test_signup_password_mismatch(self):
        data = {
            'email': 'mismatch@example.com',
            'password': 'StrongPass123!',
            'password2': 'Different456!',
        }
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('password2', response.data)

    def test_signup_duplicate_email(self):
        make_user('dup@example.com')
        data = {
            'email': 'dup@example.com',
            'password': 'StrongPass123!',
            'password2': 'StrongPass123!',
        }
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_signup_missing_email(self):
        data = {'password': 'StrongPass123!', 'password2': 'StrongPass123!'}
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

@override_settings(**TEST_SETTINGS)
class LoginTests(APITestCase):
    url = '/api/login/'

    def setUp(self):
        self.user = make_user()

    def test_login_with_email(self):
        response = self.client.post(self.url, {
            'identifier': 'user@example.com',
            'password': 'StrongPass123!',
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)

    def test_login_with_phone(self):
        response = self.client.post(self.url, {
            'identifier': '+22612345678',
            'password': 'StrongPass123!',
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_login_wrong_password(self):
        response = self.client.post(self.url, {
            'identifier': 'user@example.com',
            'password': 'WrongPassword!',
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_unknown_user(self):
        response = self.client.post(self.url, {
            'identifier': 'nobody@example.com',
            'password': 'SomePass123!',
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_returns_mfa_token_when_mfa_enabled(self):
        self.user.mfa_enabled = True
        self.user.save()
        MFAMethod.objects.create(user=self.user, method_type='totp',
                                 secret=pyotp.random_base32(), is_active=True)
        response = self.client.post(self.url, {
            'identifier': 'user@example.com',
            'password': 'StrongPass123!',
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data.get('mfa_required'))
        self.assertIn('mfa_token', response.data)


# ---------------------------------------------------------------------------
# Token refresh & logout
# ---------------------------------------------------------------------------

@override_settings(**TEST_SETTINGS)
class TokenTests(APITestCase):
    def setUp(self):
        self.user = make_user()
        self.refresh = RefreshToken.for_user(self.user)

    def test_token_refresh(self):
        response = self.client.post('/api/token/refresh/', {'refresh': str(self.refresh)})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)

    def test_logout_blacklists_token(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.refresh.access_token}')
        response = self.client.post('/api/logout/', {'refresh': str(self.refresh)})
        self.assertEqual(response.status_code, status.HTTP_205_RESET_CONTENT)

        response2 = self.client.post('/api/token/refresh/', {'refresh': str(self.refresh)})
        self.assertEqual(response2.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_without_refresh_token(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.refresh.access_token}')
        response = self.client.post('/api/logout/', {})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


# ---------------------------------------------------------------------------
# TOTP MFA
# ---------------------------------------------------------------------------

@override_settings(**TEST_SETTINGS)
class TOTPTests(APITestCase):
    def setUp(self):
        self.user = make_user()
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(self.user).access_token}'
        )

    def test_totp_enable_get_returns_qr(self):
        response = self.client.get('/api/mfa/totp/enable/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('secret', response.data)
        self.assertIn('qr_code', response.data)

    def test_totp_enable_post_valid_code(self):
        secret = pyotp.random_base32()
        code = pyotp.TOTP(secret).now()
        response = self.client.post('/api/mfa/totp/enable/', {'secret': secret, 'code': code})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.mfa_enabled)

    def test_totp_enable_post_invalid_code(self):
        secret = pyotp.random_base32()
        response = self.client.post('/api/mfa/totp/enable/', {'secret': secret, 'code': '000000'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


# ---------------------------------------------------------------------------
# MFA verify — TOTP path
# ---------------------------------------------------------------------------

@override_settings(**TEST_SETTINGS)
class MFAVerifyTOTPTests(APITestCase):
    def setUp(self):
        self.user = make_user()
        self.user.mfa_enabled = True
        self.user.save()
        self.secret = pyotp.random_base32()
        MFAMethod.objects.create(user=self.user, method_type='totp',
                                 secret=self.secret, is_active=True)

    def _mfa_token(self):
        resp = self.client.post('/api/login/', {
            'identifier': 'user@example.com',
            'password': 'StrongPass123!',
        })
        return resp.data['mfa_token']

    def test_verify_totp_success(self):
        token = self._mfa_token()
        code = pyotp.TOTP(self.secret).now()
        response = self.client.post('/api/mfa/verify/', {
            'mfa_token': token, 'method': 'totp', 'code': code,
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)

    def test_verify_totp_wrong_code(self):
        token = self._mfa_token()
        response = self.client.post('/api/mfa/verify/', {
            'mfa_token': token, 'method': 'totp', 'code': '000000',
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_verify_invalid_token(self):
        response = self.client.post('/api/mfa/verify/', {
            'mfa_token': 'bad-token', 'method': 'totp', 'code': '123456',
        })
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


# ---------------------------------------------------------------------------
# Email OTP enable
# ---------------------------------------------------------------------------

@override_settings(**TEST_SETTINGS)
@patch('users.views.send_email_otp')
@patch('users.views.store_otp')
@patch('users.views.verify_otp')
class EmailOTPEnableTests(APITestCase):
    def setUp(self):
        self.user = make_user()
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(self.user).access_token}'
        )

    def test_get_sends_otp(self, mock_verify, mock_store, mock_send):
        response = self.client.get('/api/mfa/email/enable/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_store.assert_called_once()
        mock_send.assert_called_once()

    def test_post_valid_code_activates_method(self, mock_verify, mock_store, mock_send):
        mock_verify.return_value = True
        response = self.client.post('/api/mfa/email/enable/', {'code': '123456'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.mfa_enabled)
        self.assertTrue(MFAMethod.objects.filter(user=self.user, method_type='email').exists())

    def test_post_invalid_code_rejected(self, mock_verify, mock_store, mock_send):
        mock_verify.return_value = False
        response = self.client.post('/api/mfa/email/enable/', {'code': '000000'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


# ---------------------------------------------------------------------------
# MFA verify + SendOTP — email path
# ---------------------------------------------------------------------------

@override_settings(**TEST_SETTINGS)
@patch('users.views.send_email_otp')
@patch('users.views.store_otp')
@patch('users.views.verify_otp')
class MFAVerifyEmailTests(APITestCase):
    def setUp(self):
        self.user = make_user()
        self.user.mfa_enabled = True
        self.user.save()
        MFAMethod.objects.create(user=self.user, method_type='email',
                                 destination=self.user.email, is_active=True)

    def _mfa_token(self):
        resp = self.client.post('/api/login/', {
            'identifier': 'user@example.com',
            'password': 'StrongPass123!',
        })
        return resp.data['mfa_token']

    def test_send_otp_dispatches_email(self, mock_verify, mock_store, mock_send):
        token = self._mfa_token()
        response = self.client.post('/api/mfa/send-otp/', {
            'mfa_token': token, 'method': 'email',
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_store.assert_called_once()
        mock_send.assert_called_once()

    def test_verify_email_success(self, mock_verify, mock_store, mock_send):
        mock_verify.return_value = True
        token = self._mfa_token()
        response = self.client.post('/api/mfa/verify/', {
            'mfa_token': token, 'method': 'email', 'code': '123456',
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)

    def test_verify_email_wrong_code(self, mock_verify, mock_store, mock_send):
        mock_verify.return_value = False
        token = self._mfa_token()
        response = self.client.post('/api/mfa/verify/', {
            'mfa_token': token, 'method': 'email', 'code': '000000',
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


# ---------------------------------------------------------------------------
# UserMe
# ---------------------------------------------------------------------------

@override_settings(**TEST_SETTINGS)
class UserMeTests(APITestCase):
    def setUp(self):
        self.user = make_user()

    def test_me_authenticated(self):
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(self.user).access_token}'
        )
        response = self.client.get('/api/user/me/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['email'], self.user.email)

    def test_me_unauthenticated(self):
        response = self.client.get('/api/user/me/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
