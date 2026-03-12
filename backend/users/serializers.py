from rest_framework import serializers
from django.contrib.auth import authenticate
import pyotp
from .models import User, Role, Permission, MFAMethod, BiometricProfile, TrustedDevice , UserActivity

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'email', 'phone', 'is_active', 'date_joined', 'mfa_enabled', 'biometric_enabled', 'roles']
        read_only_fields = ['date_joined']

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

class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})
    password2 = serializers.CharField(write_only=True, required=True, label='Confirmer le mot de passe', style={'input_type': 'password'})

    class Meta:
        model = User
        fields = ['email', 'phone', 'password', 'password2']
        extra_kwargs = {
            'phone': {'required': False, 'allow_blank': True}
        }

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"password": "Les mots de passe ne correspondent pas."})
        if not attrs.get('email') and not attrs.get('phone'):
            raise serializers.ValidationError("Vous devez fournir un email ou un numéro de téléphone.")
        return attrs

    def create(self, validated_data):
        validated_data.pop('password2')
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user

class LoginSerializer(serializers.Serializer):
    identifier = serializers.CharField(help_text="Email ou numéro de téléphone")
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})

    def validate(self, attrs):
        identifier = attrs.get('identifier')
        password = attrs.get('password')
        if identifier and password:
            try:
                if '@' in identifier:
                    user = User.objects.get(email=identifier)
                else:
                    user = User.objects.get(phone=identifier)
            except User.DoesNotExist:
                raise serializers.ValidationError('Identifiants incorrects.')
            user = authenticate(username=user.email, password=password)
            if not user:
                raise serializers.ValidationError('Identifiants incorrects.')
            attrs['user'] = user
            return attrs
        raise serializers.ValidationError('Vous devez fournir un identifiant et un mot de passe.')

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