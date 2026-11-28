from django.contrib import admin

from .models import Patient


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ('patient_number', 'last_name', 'first_name', 'birth_date', 'is_active')
    list_filter = ('is_active', 'sex')
    search_fields = ('patient_number', 'first_name', 'last_name')
    readonly_fields = ('patient_number',)

    def has_delete_permission(self, request, obj=None):
        # BR-13: patients are deactivated, never deleted.
        return False