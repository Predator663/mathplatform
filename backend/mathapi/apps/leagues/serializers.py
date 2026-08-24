from rest_framework import serializers

from .models import LeagueSeason, LeagueGroup, LeagueMembership, PromotionEvent


class LeagueGroupSerializer(serializers.ModelSerializer):
    member_count = serializers.SerializerMethodField()

    class Meta:
        model = LeagueGroup
        fields = ['id', 'season', 'name', 'min_mark', 'max_mark', 'order', 'color', 'icon',
                  'member_count', 'created_at']
        read_only_fields = ['created_at']

    def get_member_count(self, obj):
        if hasattr(obj, 'member_count'):
            return obj.member_count
        return obj.members.count()


class BandInputSerializer(serializers.Serializer):
    """One manual band definition supplied at season-creation time."""
    name = serializers.CharField(max_length=100)
    min_mark = serializers.FloatField(min_value=0, max_value=100)
    max_mark = serializers.FloatField(min_value=0, max_value=100)
    color = serializers.CharField(max_length=7, required=False, allow_blank=True)
    icon = serializers.CharField(max_length=50, required=False, allow_blank=True)


class LeagueMembershipSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.full_name', read_only=True)
    student_code = serializers.CharField(source='student.student_id', read_only=True)
    group_name = serializers.CharField(source='group.name', read_only=True)
    group_color = serializers.CharField(source='group.color', read_only=True)
    group_order = serializers.IntegerField(source='group.order', read_only=True)
    pending_target_group_name = serializers.CharField(source='pending_target_group.name', read_only=True, default=None)
    is_top_tier = serializers.BooleanField(read_only=True)

    class Meta:
        model = LeagueMembership
        fields = [
            'id', 'season', 'student', 'student_name', 'student_code', 'group', 'group_name',
            'group_color', 'group_order', 'placement_score', 'latest_score', 'latest_exam',
            'is_promotion_pending', 'pending_target_group', 'pending_target_group_name',
            'pending_trigger_score', 'is_top_tier', 'joined_at', 'updated_at',
        ]
        read_only_fields = fields


class PromotionEventSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.full_name', read_only=True)
    from_group_name = serializers.CharField(source='from_group.name', read_only=True)
    to_group_name = serializers.CharField(source='to_group.name', read_only=True)
    trigger_exam_title = serializers.CharField(source='trigger_exam.title', read_only=True)
    decided_by_name = serializers.CharField(source='decided_by.get_full_name', read_only=True, default=None)

    class Meta:
        model = PromotionEvent
        fields = [
            'id', 'membership', 'season', 'student', 'student_name', 'from_group', 'from_group_name',
            'to_group', 'to_group_name', 'trigger_exam', 'trigger_exam_title', 'trigger_score',
            'status', 'decided_by_name', 'decided_at', 'created_at',
        ]
        read_only_fields = fields


class LeagueSeasonSerializer(serializers.ModelSerializer):
    classroom_name = serializers.CharField(source='classroom.name', read_only=True)
    baseline_exam_title = serializers.CharField(source='baseline_exam.title', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True, default=None)
    group_count = serializers.SerializerMethodField()
    member_count = serializers.SerializerMethodField()
    pending_promotion_count = serializers.SerializerMethodField()

    class Meta:
        model = LeagueSeason
        fields = [
            'id', 'title', 'classroom', 'classroom_name', 'baseline_exam', 'baseline_exam_title',
            'interval_mode', 'band_width', 'promotion_mode', 'status', 'created_by_name',
            'group_count', 'member_count', 'pending_promotion_count',
            'created_at', 'updated_at', 'activated_at',
        ]
        read_only_fields = ['status', 'created_at', 'updated_at', 'activated_at']

    def get_group_count(self, obj):
        return obj.groups.count()

    def get_member_count(self, obj):
        return obj.memberships.count()

    def get_pending_promotion_count(self, obj):
        return obj.memberships.filter(is_promotion_pending=True).count()


class LeagueSeasonDetailSerializer(LeagueSeasonSerializer):
    groups = serializers.SerializerMethodField()
    memberships = serializers.SerializerMethodField()

    class Meta(LeagueSeasonSerializer.Meta):
        fields = LeagueSeasonSerializer.Meta.fields + ['groups', 'memberships']

    def get_groups(self, obj):
        qs = obj.groups.all().order_by('order')
        return LeagueGroupSerializer(qs, many=True).data

    def get_memberships(self, obj):
        qs = obj.memberships.select_related('student__user', 'group', 'pending_target_group').order_by(
            '-group__order', '-latest_score',
        )
        return LeagueMembershipSerializer(qs, many=True).data


class CreateSeasonSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=200)
    classroom_id = serializers.IntegerField()
    baseline_exam_id = serializers.IntegerField()
    interval_mode = serializers.ChoiceField(choices=LeagueSeason.IntervalMode.choices,
                                             default=LeagueSeason.IntervalMode.AUTO)
    band_width = serializers.IntegerField(required=False, min_value=1, max_value=50, default=10)
    promotion_mode = serializers.ChoiceField(choices=LeagueSeason.PromotionMode.choices,
                                              default=LeagueSeason.PromotionMode.MANUAL)
    manual_bands = BandInputSerializer(many=True, required=False)

    def validate(self, attrs):
        if attrs.get('interval_mode') == LeagueSeason.IntervalMode.MANUAL and not attrs.get('manual_bands'):
            raise serializers.ValidationError('manual_bands is required when interval_mode is "manual".')
        return attrs
