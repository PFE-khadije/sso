import uuid
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone
from django.utils.functional import cached_property
from phonenumber_field.modelfields import PhoneNumberField
import pyotp
import json




class Permission(models.Model):
    code = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.code


class Role(models.Model):
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    permissions = models.ManyToManyField(Permission, blank=True)

    def __str__(self):
        return self.name


class UserManager(BaseUserManager):
    def create_user(self, email, phone=None, password=None, **extra_fields):
        if not email:
            raise ValueError('L’email est obligatoire')
        email = self.normalize_email(email)
        user = self.model(email=email, phone=phone, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email, password=password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    phone = PhoneNumberField(unique=True, blank=True, null=True, region=None)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)
    biometric_enabled = models.BooleanField(default=False)
    email_verified = models.BooleanField(default=False)
    roles = models.ManyToManyField(Role, through='UserRole', blank=True)
    mfa_enabled = models.BooleanField(default=False)
    

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['phone']

    def __str__(self):
        return self.email
    
    @cached_property
    def permission_codes(self):
        """Retourne l'ensemble des codes de permission accessibles via les rôles de l'utilisateur."""
        return set(self.roles.values_list('permissions__code', flat=True).distinct())

    def has_permission(self, permission_code):
        """Vérifie si l'utilisateur possède une permission donnée."""
        return permission_code in self.permission_codes

    def has_role(self, role_name):
        """Vérifie si l'utilisateur possède un rôle donné."""
        return self.roles.filter(name=role_name).exists()


class UserRole(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    role = models.ForeignKey(Role, on_delete=models.CASCADE)
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'role')


class MFAMethod(models.Model):
    METHOD_CHOICES = [
        ('totp', 'TOTP (Google Authenticator)'),
        ('email', 'Email OTP'),
        ('sms', 'SMS OTP'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='mfa_methods')
    method_type = models.CharField(max_length=10, choices=METHOD_CHOICES)
    secret = models.CharField(max_length=255, blank=True, null=True)
    destination = models.CharField(max_length=255, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'method_type')

    def __str__(self):
        return f"{self.user.email} - {self.method_type}"

class BiometricProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='biometric_profile')
    encrypted_embedding = models.TextField()  # stocké chiffré
    liveness_score_enrollment = models.FloatField(null=True, blank=True)  # optionnel
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Biometric profile for {self.user.email}"

class PasswordResetToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    token = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    used = models.BooleanField(default=False)

class TrustedDevice(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='trusted_devices')
    device_name = models.CharField(max_length=255)
    device_fingerprint = models.CharField(max_length=255, unique=True)
    last_used = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    def __str__(self):
        return f"{self.device_name} for {self.user.email}"
    
class UserActivity(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='activities')
    event_type = models.CharField(max_length=50)  # ex: 'login', 'mfa_success', 'app_authorized'
    description = models.TextField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class IdentityDocument(models.Model):
    DOCUMENT_TYPE_CHOICES = [
        ('id_card', 'National ID Card'),
        ('passport', 'Passport'),
        ('driver_license', "Driver's License"),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('under_review', 'Under Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='identity_document')
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPE_CHOICES)
    front_image = models.ImageField(upload_to='identity/front/')
    back_image = models.ImageField(upload_to='identity/back/', null=True, blank=True)
    selfie_image = models.ImageField(upload_to='identity/selfie/')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    rejection_reason = models.TextField(blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.user.email} – {self.document_type} ({self.status})"


class FCMToken(models.Model):
    PLATFORM_CHOICES = [('android', 'Android'), ('ios', 'iOS')]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='fcm_tokens')
    token = models.TextField(unique=True)
    platform = models.CharField(max_length=10, choices=PLATFORM_CHOICES, default='android')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.platform} token for {self.user.email}"


class QRLoginToken(models.Model):
    STATUS_CHOICES = [('pending', 'Pending'), ('confirmed', 'Confirmed'), ('expired', 'Expired')]
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='qr_tokens')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"QR {self.token} ({self.status})"


class LoginLockout(models.Model):
    identifier = models.CharField(max_length=255, unique=True)
    attempts = models.PositiveIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    last_attempt = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Lockout {self.identifier} ({self.attempts} attempts)"

    def is_locked(self):
        return bool(self.locked_until and self.locked_until > timezone.now())

    def remaining_seconds(self):
        if self.locked_until and self.locked_until > timezone.now():
            return int((self.locked_until - timezone.now()).total_seconds())
        return 0
