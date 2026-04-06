from django.contrib import admin

from .models import CustomSchema


@admin.register(CustomSchema)
class CustomSchemaAdmin(admin.ModelAdmin):
    list_display = ("id", "owner_id", "name", "version", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("name", "description", "owner_id")
    readonly_fields = ("version", "created_at", "updated_at")
