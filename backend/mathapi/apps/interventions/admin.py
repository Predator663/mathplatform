from django.contrib import admin
from .models import InterventionProgram, InterventionStage


class InterventionStageInline(admin.TabularInline):
    model = InterventionStage
    extra = 0


@admin.register(InterventionProgram)
class InterventionProgramAdmin(admin.ModelAdmin):
    list_display = ['student', 'classroom', 'status', 'baseline_average', 'latest_average', 'started_at']
    list_filter = ['status', 'classroom']
    search_fields = ['student__user__first_name', 'student__user__last_name']
    inlines = [InterventionStageInline]


@admin.register(InterventionStage)
class InterventionStageAdmin(admin.ModelAdmin):
    list_display = ['program', 'order', 'title', 'status']
    list_filter = ['status']
