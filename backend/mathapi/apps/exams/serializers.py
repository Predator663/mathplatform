from rest_framework import serializers
from django.db import transaction
from .models import MathTopic, Exam, ExamTopicWeight, ExamScore, TopicScore, ScoreEditLog


class MathTopicSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    subject_code = serializers.CharField(source='subject.code', read_only=True)
    subject_color = serializers.CharField(source='subject.color', read_only=True)

    class Meta:
        model = MathTopic
        fields = ['id', 'name', 'description', 'color', 'order', 'is_active',
                  'subject', 'subject_name', 'subject_code', 'subject_color']


class ExamTopicWeightSerializer(serializers.ModelSerializer):
    topic_name  = serializers.CharField(source='topic.name', read_only=True)
    topic_color = serializers.CharField(source='topic.color', read_only=True)

    class Meta:
        model = ExamTopicWeight
        fields = ['id', 'topic', 'topic_name', 'topic_color', 'max_marks', 'weight_percentage']


class ExamSerializer(serializers.ModelSerializer):
    topic_weights      = ExamTopicWeightSerializer(many=True, read_only=True)
    created_by_name    = serializers.CharField(source='created_by.get_full_name', read_only=True)
    passing_percentage = serializers.ReadOnlyField()
    score_count        = serializers.SerializerMethodField()
    average_score      = serializers.SerializerMethodField()
    pass_rate          = serializers.SerializerMethodField()
    subject_name       = serializers.CharField(source='subject.name', read_only=True)
    subject_code       = serializers.CharField(source='subject.code', read_only=True)
    subject_color      = serializers.CharField(source='subject.color', read_only=True)

    class Meta:
        model = Exam
        fields = [
            'id', 'title', 'exam_type', 'term', 'academic_year', 'exam_date',
            'max_score', 'passing_score', 'passing_percentage', 'classrooms',
            'topic_weights', 'created_by', 'created_by_name', 'description',
            'is_published', 'created_at', 'updated_at', 'score_count',
            'average_score', 'pass_rate',
            'subject', 'subject_name', 'subject_code', 'subject_color',
        ]
        read_only_fields = ['created_by', 'created_at', 'updated_at', 'is_deleted']

    def _present_scores(self, obj):
        """Return present (non-absent) scores, using the prefetch cache when available."""
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


class ExamCreateSerializer(serializers.ModelSerializer):
    topic_weights = ExamTopicWeightSerializer(many=True, required=False)

    class Meta:
        model = Exam
        fields = [
            'id', 'title', 'exam_type', 'term', 'academic_year', 'exam_date',
            'max_score', 'passing_score', 'classrooms', 'description',
            'is_published', 'topic_weights', 'subject',
        ]

    def validate(self, attrs):
        if attrs.get('passing_score', 0) > attrs.get('max_score', 0):
            raise serializers.ValidationError({
                'passing_score': 'Passing score cannot exceed maximum score.'
            })

        # An exam with no classrooms becomes permanently invisible to the
        # teacher who created it (and to students) — scope_exams() filters
        # on classrooms__in=<teacher's classrooms>, which an empty M2M can
        # never match. Block it at the source instead of letting a "created"
        # exam silently turn into an unreachable ghost record.
        if 'classrooms' in attrs:
            if not attrs['classrooms']:
                raise serializers.ValidationError({
                    'classrooms': 'Select at least one classroom for this exam.'
                })
        elif self.instance is None:
            raise serializers.ValidationError({
                'classrooms': 'Select at least one classroom for this exam.'
            })

        topic_weights = attrs.get('topic_weights', [])
        if topic_weights:
            total = sum(float(tw['max_marks']) for tw in topic_weights)
            if round(total, 2) != round(float(attrs.get('max_score', 0)), 2):
                raise serializers.ValidationError({
                    'topic_weights': f'Topic marks total ({total}) must equal max score ({attrs.get("max_score")}).'
                })

        # A teacher may only create an exam for (subject, classroom) pairs
        # they're actually assigned to teach. scope_exams() checks subject
        # membership and classroom membership independently, so without this,
        # a teacher assigned to Subject A in Classroom 1 and Subject B in
        # Classroom 2 could create a Subject B exam in Classroom 1 — a
        # combination they were never assigned to teach.
        request = self.context.get('request')
        if request and getattr(request.user, 'role', None) == 'teacher':
            subject = attrs.get('subject') or getattr(self.instance, 'subject', None)
            classrooms = attrs.get('classrooms')
            if classrooms is None and self.instance is not None:
                classrooms = list(self.instance.classrooms.all())
            if subject and classrooms:
                from mathapi.apps.accounts.models import TeacherAssignment
                assigned_classroom_ids = set(
                    TeacherAssignment.objects.filter(
                        teacher=request.user, subject=subject,
                    ).values_list('classroom_id', flat=True)
                )
                unassigned = [c for c in classrooms if c.id not in assigned_classroom_ids]
                if unassigned:
                    names = ', '.join(str(c) for c in unassigned)
                    raise serializers.ValidationError({
                        'classrooms': f'You are not assigned to teach {subject.name} in: {names}.'
                    })

        # Duplicate exam guard — only for exam types that are intrinsically
        # singular within a (subject, term, year, classroom) combination.
        # Repeatable types (diagnostic, mock, …) are deliberately excluded so
        # teachers can create multiple diagnostics or mocks in the same term.
        SINGULAR_TYPES = {'mid_term', 'terminal', 'necta', 'psle', 'csee', 'acsee'}

        subject = attrs.get('subject')
        exam_type = attrs.get('exam_type')
        term = attrs.get('term')
        year = attrs.get('academic_year')
        classrooms = attrs.get('classrooms', [])

        if subject and exam_type and term and year and exam_type in SINGULAR_TYPES:
            for classroom in classrooms:
                qs = Exam.objects.filter(
                    subject=subject,
                    exam_type=exam_type,
                    term=term,
                    academic_year=year,
                    classrooms=classroom,
                    is_deleted=False,
                )
                if self.instance:
                    qs = qs.exclude(pk=self.instance.pk)
                if qs.exists():
                    raise serializers.ValidationError({
                        'exam_type': (
                            f'A {exam_type.replace("_", " ").title()} already exists for '
                            f'{subject.name} in {term.replace("_", " ").title()} {year} '
                            f'for {classroom}. Only one {exam_type.replace("_", " ").title()} '
                            f'is allowed per term per classroom.'
                        )
                    })
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        topic_weights_data = validated_data.pop('topic_weights', [])
        classrooms = validated_data.pop('classrooms', [])
        exam = Exam.objects.create(**validated_data)
        exam.classrooms.set(classrooms)
        for tw in topic_weights_data:
            ExamTopicWeight.objects.create(exam=exam, **tw)
        return exam

    @transaction.atomic
    def update(self, instance, validated_data):
        topic_weights_data = validated_data.pop('topic_weights', None)
        classrooms = validated_data.pop('classrooms', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if classrooms is not None:
            instance.classrooms.set(classrooms)
        if topic_weights_data is not None:
            instance.topic_weights.all().delete()
            for tw in topic_weights_data:
                ExamTopicWeight.objects.create(exam=instance, **tw)
        return instance


class TopicScoreSerializer(serializers.ModelSerializer):
    topic_name  = serializers.CharField(source='topic.name', read_only=True)
    topic_color = serializers.CharField(source='topic.color', read_only=True)
    percentage  = serializers.ReadOnlyField()

    class Meta:
        model = TopicScore
        fields = ['id', 'topic', 'topic_name', 'topic_color', 'score', 'max_marks', 'percentage']


class ExamScoreSerializer(serializers.ModelSerializer):
    student_name    = serializers.CharField(source='student.full_name', read_only=True)
    student_id_code = serializers.CharField(source='student.student_id', read_only=True)
    percentage      = serializers.ReadOnlyField()
    passed          = serializers.ReadOnlyField()
    letter_grade    = serializers.ReadOnlyField()
    topic_scores    = TopicScoreSerializer(many=True, read_only=True)
    exam_title      = serializers.CharField(source='exam.title', read_only=True)
    exam_date       = serializers.DateField(source='exam.exam_date', read_only=True)
    exam_type       = serializers.CharField(source='exam.exam_type', read_only=True)
    max_score       = serializers.DecimalField(source='exam.max_score', max_digits=6, decimal_places=2, read_only=True)

    class Meta:
        model = ExamScore
        fields = [
            'id', 'exam', 'exam_title', 'exam_date', 'exam_type', 'max_score',
            'student', 'student_name', 'student_id_code',
            'score', 'percentage', 'passed', 'letter_grade',
            'is_absent', 'remarks', 'topic_scores',
            'entered_by', 'entered_at', 'updated_at',
        ]
        read_only_fields = ['entered_by', 'entered_at', 'updated_at']


class ExamScoreCreateSerializer(serializers.ModelSerializer):
    topic_scores = TopicScoreSerializer(many=True, required=False)

    class Meta:
        model = ExamScore
        fields = ['exam', 'student', 'score', 'is_absent', 'remarks', 'topic_scores']

    def validate(self, attrs):
        exam = attrs.get('exam')
        score = attrs.get('score', 0)
        if not attrs.get('is_absent') and exam and score > exam.max_score:
            raise serializers.ValidationError({
                'score': f'Score ({score}) cannot exceed max score ({exam.max_score}).'
            })
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        topic_scores_data = validated_data.pop('topic_scores', [])
        exam_score = ExamScore.objects.create(**validated_data)
        for ts in topic_scores_data:
            TopicScore.objects.create(exam_score=exam_score, **ts)
        return exam_score

    @transaction.atomic
    def update(self, instance, validated_data):
        topic_scores_data = validated_data.pop('topic_scores', None)
        old_score = instance.score
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if instance.score != old_score:
            ScoreEditLog.objects.create(
                exam_score=instance,
                changed_by=self.context['request'].user,
                old_score=old_score,
                new_score=instance.score,
            )
        if topic_scores_data is not None:
            instance.topic_scores.all().delete()
            for ts in topic_scores_data:
                TopicScore.objects.create(exam_score=instance, **ts)
        return instance


class BulkScoreSerializer(serializers.Serializer):
    scores = serializers.ListField(child=serializers.DictField(), min_length=1)

    def validate_scores(self, value):
        required_keys = {'student_id', 'score'}
        for i, item in enumerate(value):
            missing = required_keys - set(item.keys())
            if missing:
                raise serializers.ValidationError(f'Item {i}: missing keys {missing}')
        return value


class ScoreEditLogSerializer(serializers.ModelSerializer):
    changed_by_name = serializers.CharField(source='changed_by.get_full_name', read_only=True)

    class Meta:
        model = ScoreEditLog
        fields = '__all__'
