from rest_framework import serializers

from .models import InterventionProgram, InterventionStage, DEFAULT_STAGE_TEMPLATE


class InterventionStageSerializer(serializers.ModelSerializer):
    improvement = serializers.FloatField(read_only=True)
    is_locked = serializers.BooleanField(read_only=True)

    class Meta:
        model = InterventionStage
        fields = [
            'id', 'program', 'order', 'title', 'description', 'status',
            'measured_before', 'measured_after', 'improvement', 'is_locked',
            'notes', 'started_at', 'completed_at',
        ]
        read_only_fields = ['status', 'measured_before', 'measured_after', 'started_at', 'completed_at']


class StageDefInputSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=150)
    description = serializers.CharField(required=False, allow_blank=True)


class InterventionProgramSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.full_name', read_only=True)
    student_code = serializers.CharField(source='student.student_id', read_only=True)
    classroom_name = serializers.CharField(source='classroom.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True, default=None)
    improvement = serializers.FloatField(read_only=True)
    stage_count = serializers.IntegerField(read_only=True)
    completed_stage_count = serializers.IntegerField(read_only=True)
    current_stage_title = serializers.SerializerMethodField()

    class Meta:
        model = InterventionProgram
        fields = [
            'id', 'student', 'student_name', 'student_code', 'classroom', 'classroom_name', 'subject',
            'status', 'trigger_reason', 'baseline_average', 'latest_average', 'improvement',
            'stage_count', 'completed_stage_count', 'current_stage_title',
            'created_by_name', 'started_at', 'completed_at', 'updated_at',
        ]
        read_only_fields = ['status', 'baseline_average', 'latest_average', 'started_at', 'completed_at', 'updated_at']

    def get_current_stage_title(self, obj):
        stage = obj.current_stage
        return stage.title if stage else None


class InterventionProgramDetailSerializer(InterventionProgramSerializer):
    stages = InterventionStageSerializer(many=True, read_only=True)

    class Meta(InterventionProgramSerializer.Meta):
        fields = InterventionProgramSerializer.Meta.fields + ['stages']


class CreateProgramSerializer(serializers.Serializer):
    student_id = serializers.IntegerField()
    subject_id = serializers.IntegerField(required=False, allow_null=True)
    trigger_reason = serializers.CharField(required=False, allow_blank=True, max_length=255)
    stages = StageDefInputSerializer(many=True, required=False)


class CompleteStageSerializer(serializers.Serializer):
    notes = serializers.CharField(required=False, allow_blank=True)


class SlowLearnerCandidateSerializer(serializers.Serializer):
    student_id = serializers.IntegerField(source='student.id')
    student_name = serializers.CharField(source='student.full_name')
    student_code = serializers.CharField(source='student.student_id')
    exam_count = serializers.IntegerField()
    slope = serializers.FloatField()
    early_average = serializers.FloatField()
    recent_average = serializers.FloatField()
    overall_average = serializers.FloatField()
    trend = serializers.CharField()
