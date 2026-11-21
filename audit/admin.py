from django.contrib import admin

from audit.models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "action", "entity_type", "entity_id", "summary", "actor")
    list_filter = ("action", "entity_type")
    search_fields = ("summary", "entity_id", "actor__username")
    readonly_fields = [field.name for field in AuditLog._meta.fields]
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
