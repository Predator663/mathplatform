from django.contrib import admin
from django.utils.html import format_html
from .models import GradeLevel, Classroom, StudentProfile, ParentStudentLink
from mathapi.apps.accounts.models import TeacherAssignment


@admin.register(GradeLevel)
class GradeLevelAdmin(admin.ModelAdmin):
    list_display  = ['name', 'short_name', 'education_level', 'necta_exam', 'math_subject', 'order']
    list_editable = ['short_name', 'education_level', 'necta_exam', 'math_subject', 'order']
    list_filter   = ['education_level']
    search_fields = ['name', 'short_name']
    ordering      = ['order']
    fieldsets = (
        (None, {'fields': ('name', 'short_name', 'education_level', 'order')}),
        ('Tanzania Curriculum', {'fields': ('necta_exam', 'math_subject')}),
    )


class TeacherAssignmentInline(admin.TabularInline):
    """
    The actual mechanism for granting a teacher access to a classroom in v2 —
    Classroom.teachers (M2M, below) is legacy-only and is not read anywhere in
    the app's scoping logic (see accounts.scoping.get_teacher_classrooms).
    Assign teacher + subject pairs here instead.
    """
    model  = TeacherAssignment
    extra  = 0
    fields = ['teacher', 'subject']


@admin.register(Classroom)
class ClassroomAdmin(admin.ModelAdmin):
    list_display  = ['name', 'grade_level', 'stream_badge', 'academic_year', 'is_active', 'student_count']
    list_editable = ['academic_year', 'is_active']
    list_filter   = ['academic_year', 'is_active', 'grade_level', 'stream']
    search_fields = ['name']
    inlines = [TeacherAssignmentInline]
    ordering = ['grade_level__order', 'name']
    fieldsets = (
        (None, {
            'fields': ('name', 'grade_level', 'stream', 'academic_year', 'is_active'),
        }),
        ('Teachers (legacy — has no effect on access; use the assignments below)', {
            'fields': ('teachers',),
            'classes': ('collapse',),
        }),
    )

    def stream_badge(self, obj):
        colors = {
            'general':   '#6b7280',
            'science':   '#3b82f6',
            'arts':      '#a855f7',
            'commerce':  '#f59e0b',
            'technical': '#10b981',
        }
        color = colors.get(obj.stream, '#6b7280')
        label = obj.get_stream_display()
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:4px;font-size:11px">{}</span>',
            color, label,
        )
    stream_badge.short_description = 'Stream'

    def student_count(self, obj):
        return obj.student_count
    student_count.short_description = 'Students'


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display  = ['student_id', 'full_name', 'classroom', 'index_number', 'region', 'district', 'enrollment_date', 'is_active']
    list_editable = ['is_active']
    list_filter   = ['is_active', 'classroom__academic_year', 'classroom__grade_level', 'region']
    search_fields = ['student_id', 'user__first_name', 'user__last_name', 'user__email', 'index_number']
    raw_id_fields = ['user', 'classroom']
    ordering      = ['user__last_name', 'user__first_name']
    fieldsets = (
        ('Identity', {
            'fields': ('user', 'student_id', 'classroom', 'is_active'),
        }),
        ('Dates', {
            'fields': ('date_of_birth', 'enrollment_date'),
        }),
        ('Tanzania Details', {
            'fields': ('index_number', 'region', 'district'),
        }),
        ('Parent / Guardian', {
            'fields': ('parent_name', 'parent_phone'),
        }),
        ('Notes', {
            'fields': ('notes',),
            'classes': ('collapse',),
        }),
    )
    readonly_fields = ['enrollment_date']

    def full_name(self, obj):
        return obj.full_name
    full_name.short_description = 'Name'
    full_name.admin_order_field = 'user__last_name'


@admin.register(ParentStudentLink)
class ParentStudentLinkAdmin(admin.ModelAdmin):
    list_display  = ['parent', 'student', 'relationship', 'is_primary']
    list_editable = ['relationship', 'is_primary']
    list_filter   = ['relationship', 'is_primary']
    raw_id_fields = ['parent', 'student']
    search_fields = ['parent__email', 'student__student_id', 'student__user__last_name']
