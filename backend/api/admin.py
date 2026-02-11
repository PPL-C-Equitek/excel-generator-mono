from django.contrib import admin
from .models import GroupMember

@admin.register(GroupMember)
class GroupMemberAdmin(admin.ModelAdmin):
    list_display = ("npm", "name")
    search_fields = ("npm", "name")
