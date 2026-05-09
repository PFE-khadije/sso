from django.contrib import admin
from django.utils import timezone
from .models import User, Role, Permission, MFAMethod, BiometricProfile, TrustedDevice, UserRole, IdentityDocument

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


@admin.action(description='✅ Approve selected documents')
def approve_documents(modeladmin, request, queryset):
    queryset.update(status='approved', reviewed_at=timezone.now(), rejection_reason='')


@admin.action(description='❌ Reject selected documents')
def reject_documents(modeladmin, request, queryset):
    queryset.update(status='rejected', reviewed_at=timezone.now(), rejection_reason='Documents did not meet requirements.')


@admin.register(IdentityDocument)
class IdentityDocumentAdmin(admin.ModelAdmin):
    list_display = ('user', 'document_type', 'status', 'submitted_at', 'reviewed_at')
    list_filter = ('status', 'document_type')
    search_fields = ('user__email',)
    readonly_fields = ('submitted_at', 'reviewed_at', 'front_image_preview', 'back_image_preview', 'selfie_image_preview')
    actions = [approve_documents, reject_documents]
    fieldsets = (
        ('User & Document', {
            'fields': ('user', 'document_type', 'status', 'rejection_reason'),
        }),
        ('Images', {
            'fields': ('front_image', 'front_image_preview', 'back_image', 'back_image_preview', 'selfie_image', 'selfie_image_preview'),
        }),
        ('Timestamps', {
            'fields': ('submitted_at', 'reviewed_at'),
        }),
    )

    def front_image_preview(self, obj):
        from django.utils.html import format_html
        if obj.front_image:
            return format_html('<img src="{}" style="max-height:200px;border-radius:8px;" />', obj.front_image.url)
        return '—'
    front_image_preview.short_description = 'Front Preview'

    def back_image_preview(self, obj):
        from django.utils.html import format_html
        if obj.back_image:
            return format_html('<img src="{}" style="max-height:200px;border-radius:8px;" />', obj.back_image.url)
        return '—'
    back_image_preview.short_description = 'Back Preview'

    def selfie_image_preview(self, obj):
        from django.utils.html import format_html
        if obj.selfie_image:
            return format_html('<img src="{}" style="max-height:200px;border-radius:8px;" />', obj.selfie_image.url)
        return '—'
    selfie_image_preview.short_description = 'Selfie Preview'