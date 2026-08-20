from rest_framework import serializers
from .models import (
    StudentGroup, GroupMembership, GroupTransferLog, PeerConstraint,
    GroupAssignment, GroupAssignmentScore, GroupAssignmentMemberMark,
)


class PeerConstraintSerializer(serializers.ModelSerializer):
    student_a_name = serializers.CharField(source='student_a.full_name', read_only=True)
    student_b_name = serializers.CharField(source='student_b.full_name', read_only=True)
    constraint_type_display = serializers.CharField(source='get_constraint_type_display', read_only=True)

    class Meta:
        model = PeerConstraint
        fields = [
            'id', 'classroom', 'student_a', 'student_a_name', 'student_b', 'student_b_name',
            'constraint_type', 'constraint_type_display', 'reason', 'created_by', 'created_at',
        ]
        read_only_fields = ['created_by', 'created_at']

    def validate(self, attrs):
        a = attrs.get('student_a') or getattr(self.instance, 'student_a', None)
        b = attrs.get('student_b') or getattr(self.instance, 'student_b', None)
        if a and b and a.id == b.id:
            raise serializers.ValidationError('A constraint needs two different students.')
        return attrs


class GroupMemberSerializer(serializers.ModelSerializer):
    student_id     = serializers.IntegerField(source='student.id', read_only=True)
    student_name   = serializers.CharField(source='student.full_name', read_only=True)
    student_code   = serializers.CharField(source='student.student_id', read_only=True)
    student_stream_id   = serializers.IntegerField(source='student.stream_id', read_only=True, default=None)
    student_stream_name = serializers.CharField(source='student.stream.name', read_only=True, default=None)
    tier_display   = serializers.CharField(source='get_tier_display', read_only=True)

    class Meta:
        model = GroupMembership
        fields = [
            'id', 'student_id', 'student_name', 'student_code',
            'student_stream_id', 'student_stream_name',
            'tier', 'tier_display', 'average_at_placement', 'is_anchor', 'joined_at',
        ]


class StudentGroupSerializer(serializers.ModelSerializer):
    members       = GroupMemberSerializer(source='memberships', many=True, read_only=True)
    member_count  = serializers.IntegerField(read_only=True)
    classroom_name = serializers.CharField(source='classroom.__str__', read_only=True)
    subject_name  = serializers.CharField(source='subject.name', read_only=True, default=None)
    stream_name   = serializers.CharField(source='stream.name', read_only=True, default=None)
    badge_image_url = serializers.SerializerMethodField()
    group_average = serializers.SerializerMethodField()

    class Meta:
        model = StudentGroup
        fields = [
            'id', 'classroom', 'classroom_name', 'name', 'academic_year', 'subject', 'subject_name',
            'stream', 'stream_name', 'term', 'description', 'badge_image', 'badge_image_url', 'badge_color',
            'created_by', 'created_at', 'updated_at', 'members', 'member_count', 'group_average',
        ]
        read_only_fields = ['created_by', 'created_at', 'updated_at']
        extra_kwargs = {'badge_image': {'write_only': True, 'required': False}}

    def get_badge_image_url(self, obj):
        if not obj.badge_image:
            return None
        request = self.context.get('request')
        url = obj.badge_image.url
        return request.build_absolute_uri(url) if request else url

    def get_group_average(self, obj):
        averages = [m.average_at_placement for m in obj.memberships.all() if m.average_at_placement is not None]
        return round(sum(averages) / len(averages), 1) if averages else None

    def validate_badge_color(self, value):
        if value and not (value.startswith('#') and len(value) in (4, 7)):
            raise serializers.ValidationError('badge_color must be a hex colour like #2563eb.')
        return value


class GroupAssignmentSerializer(serializers.ModelSerializer):
    classroom_name  = serializers.CharField(source='classroom.__str__', read_only=True)
    stream_name     = serializers.CharField(source='stream.name', read_only=True, default=None)
    subject_name    = serializers.CharField(source='subject.name', read_only=True, default=None)
    assignment_type_display = serializers.CharField(source='get_assignment_type_display', read_only=True)
    term_display    = serializers.CharField(source='get_term_display', read_only=True, default=None)
    groups_scored   = serializers.SerializerMethodField()
    groups_expected = serializers.SerializerMethodField()

    class Meta:
        model = GroupAssignment
        fields = [
            'id', 'classroom', 'classroom_name', 'stream', 'stream_name',
            'subject', 'subject_name', 'title', 'description', 'assignment_type',
            'assignment_type_display', 'term', 'term_display', 'academic_year',
            'date_given', 'due_date', 'max_score', 'created_by', 'created_at',
            'updated_at', 'groups_scored', 'groups_expected',
        ]
        read_only_fields = ['created_by', 'created_at', 'updated_at']

    def _expected_groups_qs(self, obj):
        qs = StudentGroup.objects.filter(classroom_id=obj.classroom_id, academic_year=obj.academic_year)
        if obj.stream_id:
            from django.db.models import Q
            qs = qs.filter(Q(stream_id=obj.stream_id) | Q(stream__isnull=True))
        return qs

    def get_groups_expected(self, obj):
        return self._expected_groups_qs(obj).count()

    def get_groups_scored(self, obj):
        return obj.group_scores.count()


class GroupAssignmentMemberMarkSerializer(serializers.ModelSerializer):
    student_id   = serializers.IntegerField(source='student.id', read_only=True)
    student_name = serializers.CharField(source='student.full_name', read_only=True)
    student_code = serializers.CharField(source='student.student_id', read_only=True)
    effective_score = serializers.FloatField(read_only=True)
    percentage      = serializers.FloatField(read_only=True)

    class Meta:
        model = GroupAssignmentMemberMark
        fields = [
            'id', 'student_id', 'student_name', 'student_code',
            'adjustment', 'is_excused', 'note', 'effective_score', 'percentage', 'updated_at',
        ]


class GroupAssignmentScoreSerializer(serializers.ModelSerializer):
    group_name  = serializers.CharField(source='group.name', read_only=True)
    stream_id   = serializers.IntegerField(source='group.stream_id', read_only=True, default=None)
    stream_name = serializers.CharField(source='group.stream.name', read_only=True, default=None)
    percentage  = serializers.FloatField(read_only=True)
    member_marks = GroupAssignmentMemberMarkSerializer(many=True, read_only=True)
    entered_by_name = serializers.CharField(source='entered_by.get_full_name', read_only=True, default=None)

    class Meta:
        model = GroupAssignmentScore
        fields = [
            'id', 'assignment', 'group', 'group_name', 'stream_id', 'stream_name',
            'score', 'percentage', 'is_absent', 'remarks', 'member_marks',
            'entered_by', 'entered_by_name', 'entered_at', 'updated_at',
        ]
        read_only_fields = ['entered_by', 'entered_at', 'updated_at']


class GroupTransferLogSerializer(serializers.ModelSerializer):
    student_name    = serializers.CharField(source='student.full_name', read_only=True)
    from_group_name = serializers.CharField(source='from_group.name', read_only=True, default=None)
    to_group_name   = serializers.CharField(source='to_group.name', read_only=True, default=None)
    transferred_by_name = serializers.CharField(source='transferred_by.get_full_name', read_only=True, default=None)

    class Meta:
        model = GroupTransferLog
        fields = [
            'id', 'student', 'student_name', 'from_group', 'from_group_name',
            'to_group', 'to_group_name', 'reason', 'warnings',
            'transferred_by', 'transferred_by_name', 'transferred_at',
        ]
