from django.contrib import admin

from core.models import AppSettings, DataSubject


@admin.register(DataSubject)
class DataSubjectAdmin(admin.ModelAdmin):
    list_display = ("full_name", "email", "country", "is_primary")
    search_fields = ("full_name", "email")


@admin.register(AppSettings)
class AppSettingsAdmin(admin.ModelAdmin):
    list_display = (
        "case_prefix",
        "default_locale",
        "reminder_days",
        "retention_days",
        "llm_enabled",
        "llm_provider",
    )
