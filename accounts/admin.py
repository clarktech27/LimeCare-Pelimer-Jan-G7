from django.contrib import admin

from .models import Department, DoctorProfile, Profile


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name',)

    def has_delete_permission(self, request, obj=None):
        # BR-28: departments are deactivated, never deleted.
        return False


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'department', 'contact_number')
    list_filter = ('role', 'department')
    search_fields = ('user__username', 'user__first_name', 'user__last_name')


@admin.register(DoctorProfile)
class DoctorProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'specialization', 'license_number', 'department')
    search_fields = ('user__username', 'license_number', 'specialization')