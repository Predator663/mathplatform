from rest_framework import serializers

from mathapi.apps.students.models import StudentProfile, Stream
from .models import Tournament, TournamentEntry, Challenge, EntryResult
from .services import get_entry_score


class EntrySlimSerializer(serializers.ModelSerializer):
    """Compact entrant identity used inside challenge/result payloads."""
    display_name = serializers.CharField(read_only=True)
    entrant_type = serializers.CharField(read_only=True)
    student_id = serializers.IntegerField(source='student.id', read_only=True, default=None)
    stream_id = serializers.IntegerField(source='stream.id', read_only=True, default=None)
    classroom_name = serializers.SerializerMethodField()
    live_score = serializers.SerializerMethodField()

    class Meta:
        model = TournamentEntry
        fields = ['id', 'display_name', 'entrant_type', 'student_id', 'stream_id',
                  'classroom_name', 'seed_average', 'withdrawn', 'live_score']

    def get_classroom_name(self, obj):
        if obj.student_id and obj.student.classroom_id:
            return obj.student.classroom.name
        if obj.stream_id:
            return str(obj.stream.classroom)
        return None

    def get_live_score(self, obj):
        return get_entry_score(obj)


class TournamentEntryCreateSerializer(serializers.Serializer):
    student_id = serializers.IntegerField(required=False)
    stream_id = serializers.IntegerField(required=False)

    def validate(self, attrs):
        if bool(attrs.get('student_id')) == bool(attrs.get('stream_id')):
            raise serializers.ValidationError('Provide exactly one of student_id or stream_id.')
        return attrs


class ChallengeSerializer(serializers.ModelSerializer):
    entries = EntrySlimSerializer(many=True, read_only=True)
    winner = EntrySlimSerializer(read_only=True)
    initiated_by_name = serializers.CharField(source='initiated_by.get_full_name', read_only=True, default=None)
    compatibility = serializers.SerializerMethodField()

    class Meta:
        model = Challenge
        fields = ['id', 'tournament', 'label', 'entries', 'status', 'winner', 'is_tie',
                  'initiated_by_name', 'created_at', 'resolved_at', 'compatibility']
        read_only_fields = ['status', 'winner', 'is_tie', 'created_at', 'resolved_at']

    def get_compatibility(self, obj):
        # Only worth computing (and worth the extra queries) for duels still
        # awaiting a result — once resolved, "was this a fair matchup" is a
        # historical curiosity rather than something to act on.
        if obj.status != Challenge.Status.PENDING:
            return None
        from . import services
        return services.check_challenge_compatibility(obj)


class ChallengeCreateSerializer(serializers.Serializer):
    label = serializers.CharField(required=False, allow_blank=True, max_length=120)
    entry_ids = serializers.ListField(child=serializers.IntegerField(), min_length=2)


class EntryResultSerializer(serializers.ModelSerializer):
    entry = EntrySlimSerializer(read_only=True)

    class Meta:
        model = EntryResult
        fields = ['id', 'entry', 'score_percentage', 'rank', 'prior_average', 'delta',
                  'is_rising_star', 'is_champion', 'is_absent', 'computed_at']


class TournamentSerializer(serializers.ModelSerializer):
    exam_title = serializers.CharField(source='exam.title', read_only=True)
    exam_date = serializers.DateField(source='exam.exam_date', read_only=True)
    exam_is_published = serializers.BooleanField(source='exam.is_published', read_only=True)
    classroom_name = serializers.CharField(source='classroom.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True, default=None)
    entry_count = serializers.SerializerMethodField()
    challenge_count = serializers.SerializerMethodField()

    class Meta:
        model = Tournament
        fields = [
            'id', 'title', 'codename', 'description', 'mode', 'exam', 'exam_title', 'exam_date',
            'exam_is_published', 'classroom', 'classroom_name', 'status', 'registration_opens_at',
            'registration_deadline', 'max_entrants', 'is_public', 'created_by_name', 'finalized_at',
            'entry_count', 'challenge_count', 'created_at', 'updated_at',
        ]
        read_only_fields = ['status', 'finalized_at', 'created_at', 'updated_at']

    def get_entry_count(self, obj):
        if hasattr(obj, 'annotated_entry_count'):
            return obj.annotated_entry_count
        return obj.entries.filter(withdrawn=False).count()

    def get_challenge_count(self, obj):
        if hasattr(obj, 'annotated_challenge_count'):
            return obj.annotated_challenge_count
        return obj.challenges.count()


class TournamentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tournament
        fields = [
            'id', 'title', 'codename', 'description', 'mode', 'exam', 'classroom',
            'registration_opens_at', 'registration_deadline', 'max_entrants', 'is_public',
        ]

    def validate(self, attrs):
        exam = attrs.get('exam') or getattr(self.instance, 'exam', None)
        classroom = attrs.get('classroom') or getattr(self.instance, 'classroom', None)
        if exam and classroom and not exam.classrooms.filter(id=classroom.id).exists():
            raise serializers.ValidationError('The chosen exam is not assigned to that classroom.')
        return attrs


class TournamentDetailSerializer(TournamentSerializer):
    entries = serializers.SerializerMethodField()
    challenges = ChallengeSerializer(many=True, read_only=True)
    leaderboard = serializers.SerializerMethodField()

    class Meta(TournamentSerializer.Meta):
        fields = TournamentSerializer.Meta.fields + ['entries', 'challenges', 'leaderboard']

    def get_entries(self, obj):
        qs = obj.entries.filter(withdrawn=False).select_related('student__user', 'stream__classroom')
        return EntrySlimSerializer(qs, many=True).data

    def get_leaderboard(self, obj):
        if obj.status != Tournament.Status.COMPLETED:
            return []
        results = obj.entries.filter(withdrawn=False).select_related('result', 'student__user', 'stream')
        rows = [e.result for e in results if hasattr(e, 'result')]
        rows.sort(key=lambda r: (r.rank is None, r.rank or 0))
        return EntryResultSerializer(rows, many=True).data
