from django.contrib import admin
from .models import (
    StudentGroup, GroupMembership, GroupTransferLog,
    GroupAssignment, GroupAssignmentScore, GroupAssignmentMemberMark,
)


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


class GroupAssignmentMemberMarkInline(admin.TabularInline):
    model = GroupAssignmentMemberMark
    extra = 0
    autocomplete_fields = ['student']


@admin.register(GroupAssignment)
class GroupAssignmentAdmin(admin.ModelAdmin):
    list_display = ['title', 'classroom', 'stream', 'subject', 'assignment_type', 'academic_year', 'date_given']
    list_filter = ['academic_year', 'assignment_type', 'classroom', 'stream']
    search_fields = ['title', 'classroom__name']


@admin.register(GroupAssignmentScore)
class GroupAssignmentScoreAdmin(admin.ModelAdmin):
    list_display = ['assignment', 'group', 'score', 'is_absent', 'entered_by', 'entered_at']
    list_filter = ['is_absent']
    search_fields = ['assignment__title', 'group__name']
    inlines = [GroupAssignmentMemberMarkInline]
