from django.contrib import admin

from django.contrib import admin
from .models import Plan, Client, ClientUser, ClientApplication

@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'price_monthly', 'max_users', 'is_active')
    list_filter = ('is_active',)

@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'owner', 'plan', 'subscription_end', 'is_active')
    list_filter = ('is_active', 'plan')
    search_fields = ('name', 'owner__email')
    prepopulated_fields = {'slug': ('name',)}  

@admin.register(ClientUser)
class ClientUserAdmin(admin.ModelAdmin):
    list_display = ('client', 'user', 'role')
    list_filter = ('role',)

@admin.register(ClientApplication)
class ClientApplicationAdmin(admin.ModelAdmin):
    list_display = ('client', 'application', 'is_active')