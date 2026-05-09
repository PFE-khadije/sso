from django.contrib import admin
from .models import User, Role, Permission, MFAMethod, BiometricProfile, TrustedDevice, UserRole

class UserRoleInline(admin.TabularInline):
    model = UserRole
    extra = 1
    autocomplete_fields = ['role']

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('email', 'phone', 'is_active', 'is_staff', 'mfa_enabled', 'biometric_enabled')
    fieldsets = (
        (None, {'fields': ('email', 'phone', 'password')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'user_permissions')}),
    )
    readonly_fields = ('last_login', 'date_joined')  
    inlines = [UserRoleInline]
    search_fields = ('email', 'phone')

@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    filter_horizontal = ('permissions',)
    search_fields = ('name',)

@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ('code', 'description')
    search_fields = ('code',)

@admin.register(MFAMethod)
class MFAMethodAdmin(admin.ModelAdmin):
    list_display = ('user', 'method_type', 'is_active', 'created_at')
    list_filter = ('method_type', 'is_active')
    search_fields = ('user__email',)

@admin.register(BiometricProfile)
class BiometricProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'created_at', 'updated_at')
    search_fields = ('user__email',)

@admin.register(TrustedDevice)
class TrustedDeviceAdmin(admin.ModelAdmin):
    list_display = ('user', 'device_name', 'last_used', 'expires_at')
    search_fields = ('user__email', 'device_name')