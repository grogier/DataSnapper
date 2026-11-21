from django.contrib import admin

from correspondence.models import Attachment, Message, Template


@admin.register(Template)
class TemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "right", "locale", "version", "is_active", "updated_at")
    list_filter = ("right", "locale", "is_active", "jurisdiction")
    search_fields = ("name", "slug", "subject", "body")


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("subject", "case", "direction", "channel", "status", "created_at")
    list_filter = ("direction", "channel", "status")
    search_fields = ("subject", "body", "case__reference", "to_address", "from_address")
    raw_id_fields = ("case", "template")


@admin.register(Attachment)
class AttachmentAdmin(admin.ModelAdmin):
    list_display = ("original_name", "kind", "case", "organization", "size", "created_at")
    list_filter = ("kind",)
    search_fields = ("original_name", "notes", "sha256", "case__reference")
    raw_id_fields = ("case", "message", "organization")
