from rest_framework import serializers
from django.contrib.auth import authenticate
import pyotp
from .models import User, Role, Permission, MFAMethod, BiometricProfile, TrustedDevice, UserActivity, IdentityDocument

# --- User Serializer (with phone conversion) ---
class UserSerializer(serializers.ModelSerializer):
    phone = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'email', 'phone', 'first_name', 'last_name', 'is_active', 'date_joined', 'mfa_enabled', 'biometric_enabled', 'roles']
        read_only_fields = ['date_joined']

    def get_phone(self, obj):
        return str(obj.phone) if obj.phone else None

# --- Role, Permission, MFA, Biometric, TrustedDevice, Activity serializers ---
class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = '__all__'

class PermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permission
        fields = '__all__'

class MFAMethodSerializer(serializers.ModelSerializer):
    class Meta:
        model = MFAMethod
        fields = '__all__'
        read_only_fields = ('user',)

class BiometricProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = BiometricProfile
        fields = '__all__'

class TrustedDeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrustedDevice
        fields = '__all__'

class UserActivitySerializer(serializers.ModelSerializer):
    class Meta:
        model = UserActivity
        fields = ['id', 'event_type', 'description', 'ip_address', 'user_agent', 'created_at']
        read_only_fields = fields

# --- Signup Serializer ---
class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})
    password2 = serializers.CharField(write_only=True, required=True, label='Confirmer le mot de passe', style={'input_type': 'password'})

    class Meta:
        model = User
        fields = ['email', 'phone', 'first_name', 'last_name', 'password', 'password2']
        extra_kwargs = {
            'phone': {'required': False, 'allow_blank': True},
            'first_name': {'required': False, 'allow_blank': True},
            'last_name': {'required': False, 'allow_blank': True},
        }

    def validate(self, attrs):
        if attrs.get('password') != attrs.get('password2'):
            raise serializers.ValidationError({'password2': 'Les mots de passe ne correspondent pas.'})
        return attrs

    def create(self, validated_data):
        validated_data.pop('password2')
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user

# --- Login Serializer ---
class LoginSerializer(serializers.Serializer):
    identifier = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    phone = serializers.CharField(required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})

    def validate(self, attrs):
        # Prendre le premier identifiant non vide parmi identifier, email, phone
        identifier = attrs.get('identifier') or attrs.get('email') or attrs.get('phone')
        password = attrs.get('password')

        if not identifier or not password:
            raise serializers.ValidationError('Identifiant et mot de passe requis.')

        # Chercher l'utilisateur par email ou téléphone
        try:
            if '@' in identifier:
                user = User.objects.get(email=identifier)
            else:
                user = User.objects.get(phone=identifier)
        except User.DoesNotExist:
            raise serializers.ValidationError('Identifiants incorrects.')

        # Authentifier avec l'email (username field) et le mot de passe
        user = authenticate(username=user.email, password=password)
        if not user:
            raise serializers.ValidationError('Identifiants incorrects.')

        attrs['user'] = user
        return attrs

# --- TOTP Serializers ---
class TOTPVerifySerializer(serializers.Serializer):
    code = serializers.CharField(max_length=6, min_length=6)
    secret = serializers.CharField(write_only=True)

    def validate(self, data):
        secret = data.get('secret')
        code = data.get('code')
        totp = pyotp.TOTP(secret)
        if not totp.verify(code, valid_window=1):
            raise serializers.ValidationError("Code invalide ou expiré.")
        return data

class TOTPDisableSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})

    def validate_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Mot de passe incorrect.")
        return value


class IdentityDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = IdentityDocument
        fields = [
            'id', 'document_type', 'front_image', 'back_image',
            'selfie_image', 'status', 'rejection_reason',
            'expiry_date', 'submitted_at', 'reviewed_at',
        ]
        read_only_fields = ['status', 'rejection_reason', 'expiry_date', 'submitted_at', 'reviewed_at']