from rest_framework import serializers
from .models import DailyQuiz, DailyQuizScore


class DailyQuizSerializer(serializers.ModelSerializer):
    display_title      = serializers.ReadOnlyField()
    passing_percentage = serializers.ReadOnlyField()
    created_by_name     = serializers.CharField(source='created_by.get_full_name', read_only=True)
    classroom_name       = serializers.CharField(source='classroom.name', read_only=True)
    subject_name        = serializers.CharField(source='subject.name', read_only=True)
    subject_color        = serializers.CharField(source='subject.color', read_only=True)
    topic_name           = serializers.CharField(source='topic.name', read_only=True, default=None)
    score_count          = serializers.SerializerMethodField()
    average_score        = serializers.SerializerMethodField()
    pass_rate            = serializers.SerializerMethodField()

    class Meta:
        model = DailyQuiz
        fields = [
            'id', 'date', 'classroom', 'classroom_name', 'subject', 'subject_name',
            'subject_color', 'topic', 'topic_name', 'title', 'display_title',
            'term', 'academic_year', 'max_score', 'passing_score', 'passing_percentage',
            'notes', 'created_by', 'created_by_name', 'created_at', 'updated_at',
            'score_count', 'average_score', 'pass_rate',
        ]
        read_only_fields = ['created_by', 'created_at', 'updated_at', 'is_deleted']

    def _present_scores(self, obj):
        if hasattr(obj, 'present_scores'):
            return obj.present_scores
        return list(obj.scores.filter(is_absent=False))

    def get_score_count(self, obj):
        return len(self._present_scores(obj))

    def get_average_score(self, obj):
        scores = self._present_scores(obj)
        if not scores:
            return None
        total = sum(float(s.score) for s in scores)
        return round((total / len(scores) / float(obj.max_score)) * 100, 1)

    def get_pass_rate(self, obj):
        scores = self._present_scores(obj)
        if not scores:
            return None
        passed = sum(1 for s in scores if float(s.score) >= float(obj.passing_score))
        return round((passed / len(scores)) * 100, 1)


class DailyQuizCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyQuiz
        fields = [
            'id', 'date', 'classroom', 'subject', 'topic', 'title',
            'term', 'academic_year', 'max_score', 'passing_score', 'notes',
        ]

    def validate(self, attrs):
        max_score = attrs.get('max_score', getattr(self.instance, 'max_score', None))
        passing_score = attrs.get('passing_score', getattr(self.instance, 'passing_score', None))
        if max_score is not None and passing_score is not None and passing_score > max_score:
            raise serializers.ValidationError({
                'passing_score': 'Passing score cannot exceed maximum score.'
            })
        topic = attrs.get('topic', getattr(self.instance, 'topic', None))
        subject = attrs.get('subject', getattr(self.instance, 'subject', None))
        if topic is not None and subject is not None and topic.subject_id != subject.id:
            raise serializers.ValidationError({
                'topic': 'That topic does not belong to the selected subject.'
            })
        return attrs


class DailyQuizScoreSerializer(serializers.ModelSerializer):
    student_name    = serializers.CharField(source='student.full_name', read_only=True)
    student_id_code = serializers.CharField(source='student.student_id', read_only=True)
    percentage      = serializers.ReadOnlyField()
    passed          = serializers.ReadOnlyField()
    letter_grade    = serializers.ReadOnlyField()
    quiz_title      = serializers.CharField(source='quiz.display_title', read_only=True)
    quiz_date       = serializers.DateField(source='quiz.date', read_only=True)
    max_score       = serializers.DecimalField(source='quiz.max_score', max_digits=6, decimal_places=2, read_only=True)

    class Meta:
        model = DailyQuizScore
        fields = [
            'id', 'quiz', 'quiz_title', 'quiz_date', 'max_score',
            'student', 'student_name', 'student_id_code',
            'score', 'percentage', 'passed', 'letter_grade',
            'is_absent', 'remarks', 'entered_by', 'entered_at', 'updated_at',
        ]
        read_only_fields = ['entered_by', 'entered_at', 'updated_at']


class BulkQuizScoreSerializer(serializers.Serializer):
    scores = serializers.ListField(child=serializers.DictField(), min_length=1)

    def validate_scores(self, value):
        required_keys = {'student_id', 'score'}
        for i, item in enumerate(value):
            missing = required_keys - set(item.keys())
            if missing:
                raise serializers.ValidationError(f'Item {i}: missing keys {missing}')
        return value
