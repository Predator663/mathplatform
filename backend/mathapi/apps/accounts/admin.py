from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Subject, TeacherAssignment, AuditLog, SiteSettings


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['email', 'first_name', 'last_name', 'role', 'is_active', 'date_joined']
    list_filter = ['role', 'is_active', 'is_staff']
    search_fields = ['email', 'first_name', 'last_name']
    ordering = ['email']
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'phone', 'avatar')}),
        ('Permissions', {'fields': ('role', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Dates', {'fields': ('date_joined', 'last_login')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'first_name', 'last_name', 'role', 'password1', 'password2'),
        }),
    )


class TeacherUser(User):
    class Meta:
        proxy = True
        verbose_name = 'Teacher'
        verbose_name_plural = 'Teachers'


class StudentUser(User):
    class Meta:
        proxy = True
        verbose_name = 'Student'
        verbose_name_plural = 'Students'


class TeacherAssignmentInline(admin.TabularInline):
    model = TeacherAssignment
    extra = 1
    autocomplete_fields = ['classroom', 'subject']
    fields = ['classroom', 'subject', 'created_at']
    readonly_fields = ['created_at']


@admin.register(TeacherUser)
class TeacherAdmin(BaseUserAdmin):
    inlines = [TeacherAssignmentInline]
    list_display = ['email', 'first_name', 'last_name', 'is_active']
    search_fields = ['email', 'first_name', 'last_name']
    ordering = ['email']
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'phone')}),
        ('Status', {'fields': ('is_active',)}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'first_name', 'last_name', 'password1', 'password2'),
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).filter(role='teacher')

    def save_model(self, request, obj, form, change):
        obj.role = 'teacher'
        super().save_model(request, obj, form, change)


@admin.register(StudentUser)
class StudentAdmin(BaseUserAdmin):
    list_display = ['email', 'first_name', 'last_name', 'is_active']
    search_fields = ['email', 'first_name', 'last_name']
    ordering = ['email']
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'phone')}),
        ('Status', {'fields': ('is_active',)}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'first_name', 'last_name', 'password1', 'password2'),
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).filter(role='student')

    def save_model(self, request, obj, form, change):
        obj.role = 'student'
        super().save_model(request, obj, form, change)


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'color', 'is_active']
    list_editable = ['is_active']
    search_fields = ['name', 'code']
    ordering = ['name']


@admin.register(TeacherAssignment)
class TeacherAssignmentAdmin(admin.ModelAdmin):
    list_display = ['teacher', 'classroom', 'subject', 'created_at']
    list_filter = ['subject', 'classroom__academic_year']
    search_fields = ['teacher__email', 'teacher__first_name', 'classroom__name']
    autocomplete_fields = ['teacher', 'subject']
    ordering = ['teacher__last_name', 'subject__name']


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['timestamp', 'user', 'action', 'model_name', 'object_id', 'ip_address']
    list_filter = ['action', 'model_name', 'timestamp']
    search_fields = ['user__email', 'description', 'model_name']
    readonly_fields = ['user', 'action', 'model_name', 'object_id', 'description', 'ip_address', 'timestamp']
    ordering = ['-timestamp']
    date_hierarchy = 'timestamp'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    list_display = ['platform_name', 'platform_subtitle', 'updated_at']
    readonly_fields = ['updated_at', 'updated_by']
