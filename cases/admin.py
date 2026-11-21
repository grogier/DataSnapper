from django.contrib import admin

from cases.models import Case, CaseEvent, Task


class TaskInline(admin.TabularInline):
    model = Task
    extra = 0


@admin.register(Case)
class CaseAdmin(admin.ModelAdmin):
    list_display = ("reference", "organization", "right", "status", "sent_at", "due_at")
    list_filter = ("status", "right", "priority", "jurisdiction")
    search_fields = ("reference", "organization__name", "scope", "title")
    readonly_fields = ("reference", "created_at", "updated_at")
    inlines = [TaskInline]
    date_hierarchy = "opened_at"


@admin.register(CaseEvent)
class CaseEventAdmin(admin.ModelAdmin):
    list_display = ("created_at", "case", "event_type", "summary", "actor")
    list_filter = ("event_type",)
    search_fields = ("summary", "detail", "case__reference")
    readonly_fields = [field.name for field in CaseEvent._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
