from rest_framework import serializers
from .models import Client, ClientUser, ClientApplication, Plan
from oauth2_provider.models import Application

# --- PlanSerializer first (used by ClientDetailSerializer) ---
class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = '__all__'

# --- ClientSerializer (basic) ---
class ClientSerializer(serializers.ModelSerializer):
    # plan is optional from the API caller's perspective. If the new client
    # owner doesn't pick one, perform_create() falls back to the cheapest
    # active Plan. The model itself still requires a plan FK at the DB level,
    # which is fine because the view always provides one before .save().
    class Meta:
        model = Client
        fields = ['id', 'name', 'slug', 'plan', 'logo', 'primary_color', 'is_active']
        read_only_fields = ['slug', 'is_active']
        extra_kwargs = {
            'plan': {'required': False, 'allow_null': True},
        }

# --- ClientDetailSerializer (uses PlanSerializer) ---
class ClientDetailSerializer(serializers.ModelSerializer):
    plan = PlanSerializer(read_only=True)
    owner_email = serializers.EmailField(source='owner.email', read_only=True)

    class Meta:
        model = Client
        fields = '__all__'

# --- ClientApplicationSerializer ---
class ClientApplicationSerializer(serializers.ModelSerializer):
    client_id = serializers.CharField(source='application.client_id', read_only=True)
    client_secret = serializers.SerializerMethodField()
    name = serializers.CharField(source='application.name', read_only=True)
    redirect_uris = serializers.CharField(source='application.redirect_uris', read_only=True)
    client_type = serializers.CharField(source='application.client_type', read_only=True)
    authorization_grant_type = serializers.CharField(source='application.authorization_grant_type', read_only=True)

    class Meta:
        model = ClientApplication
        fields = ['id', 'client_id', 'client_secret', 'name', 'redirect_uris',
                  'client_type', 'authorization_grant_type', 'is_active']
        read_only_fields = ['id', 'client_id', 'client_secret', 'name', 'redirect_uris',
                            'client_type', 'authorization_grant_type']

    def get_client_secret(self, obj):
        # Only return plain secret for newly created objects (POST)
        request = self.context.get('request')
        if request and request.method == 'POST':
            # Check if the application has a temporary _plain_secret attribute
            return getattr(obj.application, '_plain_secret', None)
        return None

# --- ClientUserSerializer ---
class ClientUserSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = ClientUser
        fields = ['id', 'user', 'user_email', 'role', 'joined_at']
        read_only_fields = ['joined_at']