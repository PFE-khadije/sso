from django.db import models

from django.db import models
from django.contrib.auth import get_user_model
from oauth2_provider.models import Application

User = get_user_model()

class Plan(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    price_monthly = models.DecimalField(max_digits=10, decimal_places=2)
    max_users = models.IntegerField(null=True, blank=True)
    features = models.JSONField(default=dict)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return self.name

class Client(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    owner = models.ForeignKey(User, on_delete=models.PROTECT, related_name='owned_clients')
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT)
    subscription_start = models.DateTimeField(auto_now_add=True)
    subscription_end = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    logo = models.ImageField(upload_to='client_logos/', blank=True, null=True)  # stockage local
    primary_color = models.CharField(max_length=7, default='#000000')

    def __str__(self):
        return self.name

class ClientUser(models.Model):
    ROLE_CHOICES = [
        ('admin', 'Administrateur'),
        ('member', 'Membre'),
    ]
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='members')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='client_memberships')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='member')
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('client', 'user')

class ClientApplication(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='applications')
    application = models.OneToOneField(Application, on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.client.name} - {self.application.name}"
