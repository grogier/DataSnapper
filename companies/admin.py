from django.contrib import admin

from companies.models import Contact, DataInventory, Organization


class ContactInline(admin.TabularInline):
    model = Contact
    extra = 0


class DataInventoryInline(admin.TabularInline):
    model = DataInventory
    extra = 0


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "country", "status", "created_at")
    list_filter = ("category", "status", "country")
    search_fields = ("name", "legal_name", "trading_name", "privacy_email", "dpo_email")
    inlines = [ContactInline, DataInventoryInline]
