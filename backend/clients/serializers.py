from rest_framework import serializers
from .models import Plan, Client, ClientUser, ClientApplication
from oauth2_provider.models import Application

class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = '__all__'

class ClientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Client
        fields = ['id', 'name', 'slug', 'plan', 'logo', 'primary_color', 'is_active']
        read_only_fields = ['slug', 'is_active']

class ClientDetailSerializer(serializers.ModelSerializer):
    plan = PlanSerializer(read_only=True)
    owner_email = serializers.EmailField(source='owner.email', read_only=True)

    class Meta:
        model = Client
        fields = '__all__'

class ClientApplicationSerializer(serializers.ModelSerializer):
    application_id = serializers.IntegerField(source='application.id', read_only=True)
    client_id = serializers.CharField(source='application.client_id', read_only=True)
    client_secret = serializers.SerializerMethodField()  # ← champ calculé
    name = serializers.CharField(source='application.name')
    redirect_uris = serializers.CharField(source='application.redirect_uris')
    client_type = serializers.CharField(source='application.client_type')
    authorization_grant_type = serializers.CharField(source='application.authorization_grant_type')

    class Meta:
        model = ClientApplication
        fields = [
            'id', 'application_id', 'client_id', 'client_secret',
            'name', 'redirect_uris', 'client_type',
            'authorization_grant_type', 'is_active'
        ]

    def get_client_secret(self, obj):
        return obj.application.client_secret

class ClientUserSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = ClientUser
        fields = ['id', 'user', 'user_email', 'role', 'joined_at']
        read_only_fields = ['joined_at']