from rest_framework import serializers
from .models import Badge, StudentBadge, StudentStreak, QuizStreak


class BadgeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Badge
        fields = ['id', 'code', 'name', 'description', 'icon', 'criteria_type', 'threshold']
        read_only_fields = fields


class StudentBadgeSerializer(serializers.ModelSerializer):
    badge = BadgeSerializer(read_only=True)
    exam_title = serializers.CharField(source='exam.title', read_only=True, default=None)
    quiz_title = serializers.CharField(source='quiz.display_title', read_only=True, default=None)

    class Meta:
        model = StudentBadge
        fields = ['id', 'badge', 'exam', 'exam_title', 'quiz', 'quiz_title', 'awarded_at']
        read_only_fields = fields


class StudentStreakSerializer(serializers.ModelSerializer):
    last_exam_title = serializers.CharField(source='last_exam.title', read_only=True, default=None)

    class Meta:
        model = StudentStreak
        fields = [
            'current_streak', 'longest_streak', 'last_exam', 'last_exam_title',
            'last_exam_date', 'last_result_passed', 'updated_at',
        ]
        read_only_fields = fields


class QuizStreakSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuizStreak
        fields = ['current_streak', 'longest_streak', 'last_quiz_date', 'updated_at']
        read_only_fields = fields
