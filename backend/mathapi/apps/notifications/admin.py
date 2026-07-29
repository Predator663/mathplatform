from django.contrib import admin

from .models import NotificationPreference, NotificationLog


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ['user', 'category', 'frequency', 'updated_at']
    list_filter = ['category', 'frequency']
    search_fields = ['user__email', 'user__first_name', 'user__last_name']
    autocomplete_fields = ['user']


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = ['recipient', 'category', 'subject', 'status', 'sent_at']
    list_filter = ['category', 'status', 'sent_at']
    search_fields = ['recipient__email', 'subject', 'summary']
    readonly_fields = [f.name for f in NotificationLog._meta.fields]
    date_hierarchy = 'sent_at'

    def has_add_permission(self, request):
        return False  # audit log — only ever created by the notification engine
