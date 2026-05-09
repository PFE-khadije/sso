from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.core import mail
from unittest.mock import patch
from rest_framework import status
from rest_framework.test import APITestCase, APIClient

from .models import Role, Permission, MFAMethod, TrustedDevice
from .utils import encrypt_secret, decrypt_secret

User = get_user_model()


# ── Existing RBAC tests ───────────────────────────────────────────────────────

class PermissionTests(APITestCase):
    def setUp(self):
        self.view_user_perm = Permission.objects.create(code='users.view_user', description='')
        self.add_user_perm = Permission.objects.create(code='users.add_user', description='')
        self.admin_role = Role.objects.create(name='admin')
        self.admin_role.permissions.add(self.view_user_perm, self.add_user_perm)
        self.admin_user = User.objects.create_user(
            email='admin@example.com', phone='123456789', password='adminpass'
        )
        self.admin_user.roles.add(self.admin_role)
        self.normal_user = User.objects.create_user(
            email='user@example.com', phone='987654321', password='userpass'
        )
        self.client = APIClient()

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
            'phone': '111222333',
            'password': 'testpass123',
            'password2': 'testpass123',
        }
        response = self.client.post(reverse('user-list'), data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_normal_user_cannot_create_user(self):
        self.client.force_authenticate(user=self.normal_user)
        data = {
            'email': 'new@example.com',
            'phone': '111222333',
            'password': 'testpass123',
            'password2': 'testpass123',
        }
        response = self.client.post(reverse('user-list'), data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


# ── Encryption helpers ────────────────────────────────────────────────────────

class EncryptionTests(TestCase):
    def test_round_trip(self):
        secret = "JBSWY3DPEHPK3PXP"
        self.assertEqual(decrypt_secret(encrypt_secret(secret)), secret)

    def test_plaintext_fallback(self):
        """decrypt_secret must tolerate pre-encryption plaintext values."""
        plain = "JBSWY3DPEHPK3PXP"
        self.assertEqual(decrypt_secret(plain), plain)


# ── Signup / Login ────────────────────────────────────────────────────────────

class AuthFlowTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_signup_creates_user_and_returns_tokens(self):
        res = self.client.post(reverse('signup'), {
            'email': 'test@example.com',
            'password': 'StrongPass123!',
            'password2': 'StrongPass123!',
        })
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertIn('access', res.data)
        self.assertIn('refresh', res.data)
        self.assertTrue(User.objects.filter(email='test@example.com').exists())

    def test_signup_rejects_mismatched_passwords(self):
        res = self.client.post(reverse('signup'), {
            'email': 'test2@example.com',
            'password': 'StrongPass123!',
            'password2': 'Different123!',
        })
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_returns_tokens(self):
        User.objects.create_user(email='login@example.com', password='StrongPass123!')
        res = self.client.post(reverse('login'), {
            'email': 'login@example.com',
            'password': 'StrongPass123!',
        })
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn('access', res.data)

    def test_login_wrong_password(self):
        User.objects.create_user(email='bad@example.com', password='correct')
        res = self.client.post(reverse('login'), {
            'email': 'bad@example.com',
            'password': 'wrong',
        })
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)


# ── User enumeration ──────────────────────────────────────────────────────────

class UserEnumerationTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_auth_methods_same_response_for_unknown_user(self):
        url = reverse('auth-methods') + '?identifier=ghost@example.com'
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertFalse(res.data.get('has_mfa'))
        self.assertFalse(res.data.get('has_biometric'))
        self.assertNotIn('exists', res.data)

    def test_totp_verify_returns_same_error_for_unknown_user(self):
        res = self.client.post(reverse('totp_verify'), {
            'identifier': 'ghost@example.com',
            'code': '000000',
        })
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(res.data['detail'], 'Code invalide.')


# ── TOTP enrollment (server-side secret) ─────────────────────────────────────

class TOTPEnrollmentTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(email='totp@example.com', password='Pass123!')
        self.client.force_authenticate(self.user)

    def test_get_returns_enrollment_token_not_secret(self):
        res = self.client.get(reverse('totp_enable'))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn('enrollment_token', res.data)
        self.assertIn('qr_code', res.data)
        self.assertNotIn('secret', res.data)

    @patch('users.views.cache')
    def test_post_with_bad_enrollment_token_fails(self, mock_cache):
        mock_cache.get.return_value = None
        res = self.client.post(reverse('totp_enable'), {
            'enrollment_token': 'invalid-token',
            'code': '123456',
        })
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)


# ── TrustedDevice fingerprint scoping ────────────────────────────────────────

class TrustedDeviceScopeTests(TestCase):
    def test_same_fingerprint_allowed_for_different_users(self):
        from django.utils import timezone
        from datetime import timedelta
        u1 = User.objects.create_user(email='u1@example.com', password='x')
        u2 = User.objects.create_user(email='u2@example.com', password='x')
        exp = timezone.now() + timedelta(days=30)
        TrustedDevice.objects.create(user=u1, device_name='phone', device_fingerprint='fp-abc', expires_at=exp)
        TrustedDevice.objects.create(user=u2, device_name='phone', device_fingerprint='fp-abc', expires_at=exp)
        self.assertEqual(TrustedDevice.objects.filter(device_fingerprint='fp-abc').count(), 2)


# ── Password reset ────────────────────────────────────────────────────────────

class PasswordResetTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(email='reset@example.com', password='OldPass123!')

    def test_request_always_returns_200(self):
        res = self.client.post(reverse('password-reset-request'), {'email': 'ghost@example.com'})
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    @patch('users.utils.verify_otp', return_value=True)
    def test_confirm_sets_new_password(self, _mock):
        res = self.client.post(reverse('password-reset-confirm'), {
            'email': 'reset@example.com',
            'code': '123456',
            'new_password': 'NewStrongPass123!',
        })
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('NewStrongPass123!'))

    @patch('users.utils.verify_otp', return_value=False)
    def test_confirm_rejects_wrong_code(self, _mock):
        res = self.client.post(reverse('password-reset-confirm'), {
            'email': 'reset@example.com',
            'code': '000000',
            'new_password': 'NewStrongPass123!',
        })
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)


# ── Email verification ────────────────────────────────────────────────────────

class EmailVerificationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(email='verify@example.com', password='Pass123!')
        self.client.force_authenticate(self.user)

    def test_request_sends_email(self):
        res = self.client.post(reverse('email-verify-request'))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('verify@example.com', mail.outbox[0].to)

    def test_confirm_with_valid_token(self):
        self.client.post(reverse('email-verify-request'))
        self.user.refresh_from_db()
        token = self.user.email_verification_token
        self.assertIsNotNone(token)
        unauth_client = APIClient()
        res = unauth_client.get(reverse('email-verify-confirm') + f'?token={token}')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.email_verified)

    def test_confirm_with_invalid_token(self):
        unauth_client = APIClient()
        res = unauth_client.get(reverse('email-verify-confirm') + '?token=bad-token')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_already_verified_returns_400(self):
        self.user.email_verified = True
        self.user.save()
        res = self.client.post(reverse('email-verify-request'))
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
