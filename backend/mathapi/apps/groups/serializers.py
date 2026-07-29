from rest_framework import serializers
from .models import StudentGroup, GroupMembership, GroupTransferLog, PeerConstraint


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
