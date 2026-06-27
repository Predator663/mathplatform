from django.contrib import admin
from .models import MathTopic, Exam, ExamTopicWeight, ExamScore, TopicScore, ScoreEditLog


@admin.register(MathTopic)
class MathTopicAdmin(admin.ModelAdmin):
    list_display  = ['name', 'subject', 'color', 'order', 'is_active', 'description']
    list_editable = ['color', 'order', 'is_active']
    list_filter   = ['subject', 'is_active']
    search_fields = ['name', 'description']
    ordering      = ['subject__name', 'order', 'name']


class ExamTopicWeightInline(admin.TabularInline):
    model  = ExamTopicWeight
    extra  = 0
    fields = ['topic', 'max_marks', 'weight_percentage']


@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    list_display      = ['title', 'subject', 'exam_type', 'term', 'academic_year', 'exam_date', 'max_score', 'passing_score', 'is_published']
    list_editable     = ['is_published']
    list_filter       = ['subject', 'exam_type', 'term', 'academic_year', 'is_published']
    search_fields     = ['title', 'description']
    filter_horizontal = ['classrooms']
    inlines           = [ExamTopicWeightInline]
    date_hierarchy    = 'exam_date'
    fieldsets = (
        (None, {
            'fields': ('title', 'subject', 'exam_type', 'term', 'academic_year', 'exam_date', 'is_published'),
        }),
        ('Scoring', {
            'fields': ('max_score', 'passing_score'),
        }),
        ('Classrooms', {
            'fields': ('classrooms',),
        }),
        ('Details', {
            'fields': ('description', 'created_by'),
            'classes': ('collapse',),
        }),
    )
    readonly_fields = ['created_by']

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


class TopicScoreInline(admin.TabularInline):
    model          = TopicScore
    extra          = 0
    fields         = ['topic', 'score', 'max_marks']
    readonly_fields = ['max_marks']


@admin.register(ExamScore)
class ExamScoreAdmin(admin.ModelAdmin):
    list_display  = ['student', 'exam', 'score', 'percentage', 'is_absent', 'entered_by', 'entered_at']
    list_editable = ['score', 'is_absent']
    list_filter   = ['exam__term', 'exam__academic_year', 'is_absent', 'exam']
    search_fields = ['student__user__first_name', 'student__user__last_name', 'student__student_id']
    raw_id_fields  = ['student', 'entered_by']
    inlines       = [TopicScoreInline]
    readonly_fields = ['entered_by', 'entered_at', 'updated_at']
    fieldsets = (
        (None, {
            'fields': ('exam', 'student', 'score', 'is_absent', 'remarks'),
        }),
        ('Meta', {
            'fields': ('entered_by', 'entered_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def percentage(self, obj):
        if obj.exam.max_score:
            pct = round(float(obj.score) / float(obj.exam.max_score) * 100, 1)
            color = '#10b981' if pct >= 50 else '#ef4444'
            return f'<span style="color:{color};font-weight:600">{pct}%</span>'
        return '—'
    percentage.short_description = '%'
    percentage.allow_tags = True


@admin.register(ScoreEditLog)
class ScoreEditLogAdmin(admin.ModelAdmin):
    list_display    = ['exam_score', 'changed_by', 'old_score', 'new_score', 'reason', 'changed_at']
    list_filter     = ['changed_at']
    search_fields   = ['exam_score__student__user__last_name', 'changed_by__email', 'reason']
    readonly_fields = ['exam_score', 'changed_by', 'old_score', 'new_score', 'reason', 'changed_at']
    date_hierarchy  = 'changed_at'
