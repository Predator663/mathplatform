from django.contrib import admin
from .models import StudentGroup, GroupMembership, GroupTransferLog


class GroupMembershipInline(admin.TabularInline):
    model = GroupMembership
    extra = 0
    autocomplete_fields = ['student']


@admin.register(StudentGroup)
class StudentGroupAdmin(admin.ModelAdmin):
    list_display = ['name', 'classroom', 'stream', 'academic_year', 'subject', 'member_count', 'created_at']
    list_filter = ['academic_year', 'classroom', 'stream']
    search_fields = ['name', 'classroom__name']
    inlines = [GroupMembershipInline]


@admin.register(GroupTransferLog)
class GroupTransferLogAdmin(admin.ModelAdmin):
    list_display = ['student', 'from_group', 'to_group', 'transferred_by', 'transferred_at']
    list_filter = ['transferred_at']
    search_fields = ['student__user__first_name', 'student__user__last_name']
