from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import PermissionDenied
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from .models import Tournament, TournamentEntry, Challenge, EntryResult
from .serializers import (
    TournamentSerializer, TournamentCreateSerializer, TournamentDetailSerializer,
    TournamentEntryCreateSerializer, EntrySlimSerializer,
    ChallengeSerializer, ChallengeCreateSerializer, ChallengeUpdateSerializer, EntryResultSerializer,
)
from . import services
from mathapi.apps.students.models import StudentProfile, Stream
from mathapi.apps.accounts.scoping import get_teacher_classrooms, assert_classroom_owned, scope_tournaments
from mathapi.apps.accounts.permissions import IsTeacherOrAdmin


def _my_student_profile(request):
    try:
        return request.user.student_profile
    except Exception:
        return None


class TournamentViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['classroom', 'mode', 'status', 'exam']
    search_fields = ['title', 'codename', 'description']
    ordering_fields = ['registration_deadline', 'created_at', 'title']
    ordering = ['-registration_deadline']

    def get_permissions(self):
        if self.action in ['create']:
            return [IsTeacherOrAdmin()]
        if self.action in ['update', 'partial_update', 'destroy', 'open_registration',
                            'close_registration', 'finalize', 'cancel', 'auto_match', 'register_class',
                            'delete_challenges']:
            return [IsTeacherOrAdmin()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        qs = scope_tournaments(self.request.user).select_related(
            'exam', 'classroom', 'created_by',
        ).annotate(
            annotated_entry_count=Count('entries', filter=Q(entries__withdrawn=False), distinct=True),
            annotated_challenge_count=Count('challenges', distinct=True),
        )
        return qs

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return TournamentCreateSerializer
        if self.action == 'retrieve':
            return TournamentDetailSerializer
        return TournamentSerializer

    def perform_create(self, serializer):
        classroom = serializer.validated_data.get('classroom')
        if self.request.user.role == 'teacher' and classroom is not None:
            assert_classroom_owned(self.request.user, classroom.id)
        serializer.save(created_by=self.request.user, status=Tournament.Status.DRAFT)

    def perform_update(self, serializer):
        tournament = self.get_object()
        if self.request.user.role != 'super_admin' and tournament.created_by_id != self.request.user.id:
            raise PermissionDenied('You can only edit tournaments you created.')
        serializer.save()

    def destroy(self, request, *args, **kwargs):
        tournament = self.get_object()
        if request.user.role != 'super_admin' and tournament.created_by_id != request.user.id:
            return Response({'detail': 'You can only delete tournaments you created.'}, status=status.HTTP_403_FORBIDDEN)
        if tournament.status not in (Tournament.Status.CANCELLED, Tournament.Status.DRAFT):
            return Response(
                {'detail': 'Only cancelled or draft tournaments can be deleted. Cancel this tournament first.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().destroy(request, *args, **kwargs)

    # ── Bulk registration ───────────────────────────────────────────────────
    @action(detail=True, methods=['post'], url_path='register-class')
    def register_class(self, request, pk=None):
        """
        POST /api/tournaments/tournaments/<id>/register-class/ — registers
        every active, not-yet-entered student in the tournament's own
        classroom in one shot. Individual-mode, registration-open only.
        """
        tournament = self.get_object()
        if tournament.mode != Tournament.Mode.INDIVIDUAL:
            return Response({'detail': 'Register Entire Class only applies to student-vs-student tournaments.'},
                             status=status.HTTP_400_BAD_REQUEST)
        if tournament.status != Tournament.Status.REGISTRATION_OPEN:
            return Response({'detail': 'Registration is not open for this tournament.'}, status=status.HTTP_400_BAD_REQUEST)

        result = services.register_entire_class(tournament, registered_by=request.user)
        return Response({
            'created': EntrySlimSerializer(result['created'], many=True).data,
            'created_count': result['created_count'],
            'already_registered_count': result['already_registered_count'],
            'skipped_due_to_cap': len(result['skipped_due_to_cap']),
        }, status=status.HTTP_201_CREATED)

    # ── Lifecycle ────────────────────────────────────────────────────────
    @action(detail=True, methods=['post'], url_path='open-registration')
    def open_registration(self, request, pk=None):
        tournament = self.get_object()
        tournament.status = Tournament.Status.REGISTRATION_OPEN
        tournament.save(update_fields=['status'])
        return Response(TournamentSerializer(tournament).data)

    @action(detail=True, methods=['post'], url_path='close-registration')
    def close_registration(self, request, pk=None):
        tournament = self.get_object()
        tournament.status = Tournament.Status.REGISTRATION_CLOSED
        tournament.save(update_fields=['status'])
        return Response(TournamentSerializer(tournament).data)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        tournament = self.get_object()
        tournament.status = Tournament.Status.CANCELLED
        tournament.save(update_fields=['status'])
        return Response(TournamentSerializer(tournament).data)

    @action(detail=True, methods=['post'])
    def finalize(self, request, pk=None):
        tournament = self.get_object()
        if not tournament.exam.is_published:
            return Response({'detail': 'The linked exam must be published (scored) before finalizing.'},
                             status=status.HTTP_400_BAD_REQUEST)
        dossier = services.finalize_tournament(tournament)
        tournament.refresh_from_db()

        # Email notifications are best-effort — a bad SMTP config or a
        # transient failure should never prevent the tournament from
        # finalizing (mirrors exams' publish-notification handling).
        try:
            from mathapi.apps.notifications.services import notify_tournament_finalized
            notify_tournament_finalized(tournament, dossier)
        except Exception:
            pass

        return Response(TournamentDetailSerializer(tournament).data)

    # ── Registration ─────────────────────────────────────────────────────
    @action(detail=True, methods=['post'])
    def register(self, request, pk=None):
        tournament = self.get_object()
        serializer = TournamentEntryCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        user = request.user

        if tournament.status != Tournament.Status.REGISTRATION_OPEN:
            return Response({'detail': 'Registration is not open for this tournament.'}, status=status.HTTP_400_BAD_REQUEST)

        if data.get('student_id'):
            if tournament.mode != Tournament.Mode.INDIVIDUAL:
                return Response({'detail': 'This is a stream-vs-stream tournament.'}, status=status.HTTP_400_BAD_REQUEST)
            if user.role == 'student':
                my_profile = _my_student_profile(request)
                if not my_profile or my_profile.id != data['student_id']:
                    return Response({'detail': 'Students may only register themselves.'}, status=status.HTTP_403_FORBIDDEN)
            elif user.role not in ('teacher', 'super_admin'):
                return Response({'detail': 'Not permitted.'}, status=status.HTTP_403_FORBIDDEN)
            try:
                student = StudentProfile.objects.get(id=data['student_id'], classroom=tournament.classroom, is_active=True)
            except StudentProfile.DoesNotExist:
                return Response({'detail': 'Student not found in this tournament\'s classroom.'}, status=status.HTTP_404_NOT_FOUND)
            if tournament.max_entrants and tournament.entries.filter(withdrawn=False).count() >= tournament.max_entrants:
                return Response({'detail': 'This tournament is full.'}, status=status.HTTP_400_BAD_REQUEST)
            if TournamentEntry.objects.filter(tournament=tournament, student=student, withdrawn=False).exists():
                return Response({'detail': 'Already registered.'}, status=status.HTTP_400_BAD_REQUEST)
            entry = services.register_entry(tournament, student=student, registered_by=user)
        else:
            if tournament.mode != Tournament.Mode.STREAM:
                return Response({'detail': 'This is a student-vs-student tournament.'}, status=status.HTTP_400_BAD_REQUEST)
            if not IsTeacherOrAdmin().has_permission(request, self):
                return Response({'detail': 'Only teachers/admins can register a stream.'}, status=status.HTTP_403_FORBIDDEN)
            try:
                stream = Stream.objects.get(id=data['stream_id'], classroom=tournament.classroom)
            except Stream.DoesNotExist:
                return Response({'detail': 'Stream not found in this tournament\'s classroom.'}, status=status.HTTP_404_NOT_FOUND)
            if TournamentEntry.objects.filter(tournament=tournament, stream=stream, withdrawn=False).exists():
                return Response({'detail': 'Stream already registered.'}, status=status.HTTP_400_BAD_REQUEST)
            entry = services.register_entry(tournament, stream=stream, registered_by=user)

        return Response(EntrySlimSerializer(entry).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='withdraw')
    def withdraw(self, request, pk=None):
        tournament = self.get_object()
        entry_id = request.data.get('entry_id')
        try:
            entry = tournament.entries.get(id=entry_id)
        except TournamentEntry.DoesNotExist:
            return Response({'detail': 'Entry not found.'}, status=status.HTTP_404_NOT_FOUND)

        user = request.user
        is_owner = entry.student_id and _my_student_profile(request) and entry.student_id == _my_student_profile(request).id
        if not (is_owner or IsTeacherOrAdmin().has_permission(request, self)):
            return Response({'detail': 'Not permitted.'}, status=status.HTTP_403_FORBIDDEN)

        entry.withdrawn = True
        entry.save(update_fields=['withdrawn'])
        return Response(status=status.HTTP_204_NO_CONTENT)

    # ── Challenges ───────────────────────────────────────────────────────
    @action(detail=True, methods=['get', 'post'])
    def challenges(self, request, pk=None):
        tournament = self.get_object()
        if request.method == 'GET':
            qs = tournament.challenges.prefetch_related('entries__student__user', 'entries__stream').all()
            return Response(ChallengeSerializer(qs, many=True).data)

        serializer = ChallengeCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        user = request.user
        entries = list(tournament.entries.filter(id__in=data['entry_ids'], withdrawn=False))
        if len(entries) != len(set(data['entry_ids'])):
            return Response({'detail': 'One or more entries were not found in this tournament.'}, status=status.HTTP_400_BAD_REQUEST)

        if user.role == 'student':
            my_profile = _my_student_profile(request)
            mine = [e for e in entries if e.student_id and my_profile and e.student_id == my_profile.id]
            if not mine:
                return Response({'detail': 'You must include yourself in a challenge you create.'}, status=status.HTTP_403_FORBIDDEN)
        elif user.role not in ('teacher', 'super_admin'):
            return Response({'detail': 'Not permitted.'}, status=status.HTTP_403_FORBIDDEN)

        with transaction.atomic():
            challenge = Challenge.objects.create(
                tournament=tournament, label=data.get('label', ''), initiated_by=user,
            )
            challenge.entries.set(entries)

        # compatibility is computed automatically by ChallengeSerializer for
        # any still-pending challenge — no need to duplicate that here.
        return Response(ChallengeSerializer(challenge).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['patch'], url_path=r'challenges/(?P<challenge_id>\d+)')
    def update_challenge(self, request, pk=None, challenge_id=None):
        """
        PATCH /api/tournaments/tournaments/<id>/challenges/<challenge_id>/
        Body: {"label"?: str, "entry_ids"?: [id, ...]} — edits an
        already-declared duel in place (relabel and/or swap combatants,
        including growing or shrinking the combatant count) instead of
        deleting and redeclaring it. Only while the tournament's
        registration is still open and the duel itself hasn't been
        resolved or voided yet. Same authorship rule as declaring one: a
        student may edit a challenge only if she's (and remains, if
        entry_ids is being changed) one of its combatants; a teacher/
        admin may edit any.
        """
        tournament = self.get_object()
        try:
            challenge = tournament.challenges.get(id=challenge_id)
        except Challenge.DoesNotExist:
            return Response({'detail': 'Challenge not found in this tournament.'}, status=status.HTTP_404_NOT_FOUND)

        if tournament.status != Tournament.Status.REGISTRATION_OPEN:
            return Response({'detail': 'Challenges can only be edited while registration is open.'},
                             status=status.HTTP_400_BAD_REQUEST)
        if challenge.status != Challenge.Status.PENDING:
            return Response({'detail': 'This challenge has already been resolved and can no longer be edited.'},
                             status=status.HTTP_400_BAD_REQUEST)

        serializer = ChallengeUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        user = request.user
        entry_ids = data.get('entry_ids')

        if user.role == 'student':
            my_profile = _my_student_profile(request)
            current_student_ids = set(challenge.entries.values_list('student_id', flat=True))
            if not my_profile or my_profile.id not in current_student_ids:
                return Response({'detail': 'You can only edit a challenge you are part of.'}, status=status.HTTP_403_FORBIDDEN)
        elif user.role not in ('teacher', 'super_admin'):
            return Response({'detail': 'Not permitted.'}, status=status.HTTP_403_FORBIDDEN)

        if entry_ids is not None:
            entries = list(tournament.entries.filter(id__in=entry_ids, withdrawn=False))
            if len(entries) != len(set(entry_ids)):
                return Response({'detail': 'One or more entries were not found in this tournament.'}, status=status.HTTP_400_BAD_REQUEST)
            if user.role == 'student':
                my_profile = _my_student_profile(request)
                mine = [e for e in entries if e.student_id and my_profile and e.student_id == my_profile.id]
                if not mine:
                    return Response({'detail': 'You must remain a combatant in a challenge you edit.'}, status=status.HTTP_403_FORBIDDEN)

        services.update_challenge(challenge, label=data.get('label'), entry_ids=entry_ids)
        return Response(ChallengeSerializer(challenge).data)

    @action(detail=True, methods=['post'], url_path='challenges/delete')
    def delete_challenges(self, request, pk=None):
        """
        POST /api/tournaments/tournaments/<id>/challenges/delete/
        Body: {"challenge_ids": [1, 2, 3]} — removes one, several, or (by
        passing every id currently declared) all duels at once. Teacher/
        admin only. Blocked once the tournament is finalized: a resolved
        challenge already fed into the leaderboard, badge awards, and win
        streaks, so un-declaring it after the fact would silently corrupt
        results that were already handed out. Cancel/reopen the tournament
        first if a finalized duel genuinely needs to be undone.
        """
        tournament = self.get_object()
        if tournament.status == Tournament.Status.COMPLETED:
            return Response(
                {'detail': 'This tournament is finalized — duels can no longer be removed.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        challenge_ids = request.data.get('challenge_ids') or []
        if not isinstance(challenge_ids, list) or not challenge_ids:
            return Response({'detail': 'challenge_ids is required.'}, status=status.HTTP_400_BAD_REQUEST)

        qs = tournament.challenges.filter(id__in=challenge_ids)
        found_ids = set(qs.values_list('id', flat=True))
        missing = set(challenge_ids) - found_ids
        if missing:
            return Response(
                {'detail': f'{len(missing)} challenge(s) were not found in this tournament.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        deleted_count, _ = qs.delete()
        return Response({'deleted_count': len(found_ids)}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='compatibility')
    def compatibility(self, request, pk=None):
        """
        GET /api/tournaments/<id>/compatibility/?entry_a=<id>&entry_b=<id>
        Checks whether two specific registered entrants are at the same
        skill level, using their historical average across every previous
        exam. Read-only — available to anyone who can see the tournament,
        including a student sizing up a potential opponent.
        """
        tournament = self.get_object()
        entry_a_id = request.query_params.get('entry_a')
        entry_b_id = request.query_params.get('entry_b')
        if not entry_a_id or not entry_b_id:
            return Response({'detail': 'entry_a and entry_b are required.'}, status=status.HTTP_400_BAD_REQUEST)
        if entry_a_id == entry_b_id:
            return Response({'detail': 'Choose two different entries.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            entry_a = tournament.entries.get(id=entry_a_id, withdrawn=False)
            entry_b = tournament.entries.get(id=entry_b_id, withdrawn=False)
        except TournamentEntry.DoesNotExist:
            return Response({'detail': 'One or both entries were not found in this tournament.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(services.check_entry_compatibility(entry_a, entry_b))

    @action(detail=True, methods=['get'], url_path='suggested-pairs')
    def suggested_pairs(self, request, pk=None):
        """
        GET /api/tournaments/<id>/suggested-pairs/?group_size=&use_ai= —
        a preview of the same-level groupings auto-match would create,
        without writing anything. Every unmatched individual entrant,
        clustered by historical average into same-level groups (not
        necessarily pairs — see services.suggest_level_groups).
        group_size (default 2) biases the target group headcount;
        use_ai=true asks Claude to take a refinement pass over the
        grouping first (falls back silently if unavailable).
        """
        tournament = self.get_object()
        try:
            group_size = int(request.query_params.get('group_size') or services.DEFAULT_GROUP_SIZE)
        except (TypeError, ValueError):
            group_size = services.DEFAULT_GROUP_SIZE
        use_ai = str(request.query_params.get('use_ai', '')).lower() in ('1', 'true', 'yes')
        return Response(services.suggest_level_groups(tournament, group_size=group_size, use_ai=use_ai))

    @action(detail=True, methods=['post'], url_path='auto-match')
    def auto_match(self, request, pk=None):
        """
        POST /api/tournaments/<id>/auto-match/ — materializes
        suggested-pairs into real Challenge rows, each a group of 2 or
        more combatants (not necessarily a pair). Body: {"only_compatible":
        true} (default) skips any group that's still a skill mismatch
        after best-effort clustering, leaving it for manual review; pass
        false to create every group regardless of gap. "group_size"
        (default 2) biases the target headcount per group. "use_ai": true
        asks Claude to refine the grouping before it's created — falls
        back to the deterministic clustering if the AI call fails or
        ANTHROPIC_API_KEY isn't configured. Teacher/admin only — this is
        a bulk action over the whole roster, not a single self-registration.
        """
        tournament = self.get_object()
        only_compatible = request.data.get('only_compatible', True)
        try:
            group_size = int(request.data.get('group_size') or services.DEFAULT_GROUP_SIZE)
        except (TypeError, ValueError):
            group_size = services.DEFAULT_GROUP_SIZE
        use_ai = bool(request.data.get('use_ai', False))
        result = services.auto_create_level_challenges(
            tournament, created_by=request.user, only_compatible=bool(only_compatible),
            group_size=group_size, use_ai=use_ai,
        )
        return Response({
            'created': ChallengeSerializer(result['created'], many=True).data,
            'skipped_incompatible': result['skipped_incompatible'],
            'byes': result['byes'],
            'insufficient_history': result['insufficient_history'],
            'ai_used': result['ai_used'],
        }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'])
    def analytics(self, request, pk=None):
        """Score distribution, participation rate, pass rate vs. classroom,
        and headline callouts (closest duel, biggest upset, top riser)."""
        tournament = self.get_object()
        return Response(services.get_tournament_analytics(tournament))

    @action(detail=True, methods=['get'])
    def dossier(self, request, pk=None):
        """The full 'never miss a bit of info' payload for the tournament's
        dedicated intel view: leaderboard, challenge log, champion + rising
        stars, and stream-vs-stream aggregate if applicable."""
        tournament = self.get_object()
        payload = services.get_tournament_dossier(tournament)
        results_data = EntryResultSerializer(payload['results'], many=True).data
        challenges_data = ChallengeSerializer(
            tournament.challenges.prefetch_related('entries__student__user', 'entries__stream').all(), many=True,
        ).data
        return Response({
            'tournament': TournamentSerializer(tournament).data,
            'leaderboard': results_data,
            'champion': EntryResultSerializer(payload['champion']).data if payload['champion'] else None,
            'rising_stars': EntryResultSerializer(payload['rising_stars'], many=True).data,
            'challenges': challenges_data,
        })


class MyTournamentEntriesView(APIView):
    """GET /api/tournaments/my-entries/ — a student's own tournament
    history: every entry they've registered, live/finalized score, and
    challenge record, newest tournament first."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        profile = _my_student_profile(request)
        if not profile:
            return Response({'detail': 'Only students have a tournament history.'}, status=status.HTTP_400_BAD_REQUEST)

        entries = (
            TournamentEntry.objects.filter(student=profile, withdrawn=False)
            .select_related('tournament', 'tournament__exam', 'tournament__classroom')
            .order_by('-tournament__registration_deadline')
        )
        rows = []
        for entry in entries:
            result = getattr(entry, 'result', None)
            rows.append({
                'tournament': TournamentSerializer(entry.tournament).data,
                'entry_id': entry.id,
                'seed_average': entry.seed_average,
                'live_score': services.get_entry_score(entry),
                'result': EntryResultSerializer(result).data if result else None,
            })
        return Response(rows)


class HeadToHeadView(APIView):
    """GET /api/tournaments/head-to-head/?student_a=<id>&student_b=<id>
    Lifetime rivalry record between two students across every tournament
    they've both entered."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        a = request.query_params.get('student_a')
        b = request.query_params.get('student_b')
        if not a or not b:
            return Response({'detail': 'student_a and student_b are required.'}, status=status.HTTP_400_BAD_REQUEST)
        if a == b:
            return Response({'detail': 'Choose two different students.'}, status=status.HTTP_400_BAD_REQUEST)
        data = services.get_head_to_head(int(a), int(b))
        if 'error' in data:
            return Response(data, status=status.HTTP_404_NOT_FOUND)
        return Response(data)


class TournamentIntelView(APIView):
    """GET /api/tournaments/intel/?classroom_id=
    Platform-wide (or classroom-scoped) hall-of-fame: most-decorated
    students, best win rate, biggest upsets, stream head-to-head record —
    the dashboard-level rollup that sits above any single tournament."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        classroom_id = request.query_params.get('classroom_id')
        tournaments = scope_tournaments(request.user).filter(status=Tournament.Status.COMPLETED)
        if classroom_id:
            tournaments = tournaments.filter(classroom_id=classroom_id)

        results = EntryResult.objects.filter(entry__tournament__in=tournaments).select_related(
            'entry', 'entry__student__user', 'entry__stream__classroom', 'entry__tournament',
        )

        titles_by_student = {}
        for r in results.filter(is_champion=True):
            if r.entry.student_id:
                titles_by_student.setdefault(r.entry.student_id, {'name': r.entry.display_name, 'count': 0})
                titles_by_student[r.entry.student_id]['count'] += 1

        rising_stars = [
            {'name': r.entry.display_name, 'tournament': r.entry.tournament.title, 'delta': r.delta}
            for r in results.filter(is_rising_star=True).order_by('-delta')[:10]
        ]

        challenges = Challenge.objects.filter(tournament__in=tournaments, status=Challenge.Status.RESOLVED)
        win_counts = {}
        for c in challenges.select_related('winner__student__user'):
            if c.winner and c.winner.student_id:
                key = c.winner.student_id
                win_counts.setdefault(key, {'name': c.winner.display_name, 'wins': 0})
                win_counts[key]['wins'] += 1

        # Stream-vs-stream aggregate win record
        stream_records = {}
        for r in results.filter(entry__stream__isnull=False):
            key = r.entry.stream_id
            stream_records.setdefault(key, {'name': str(r.entry.stream), 'titles': 0, 'entries': 0, 'avg_score': []})
            stream_records[key]['entries'] += 1
            if r.is_champion:
                stream_records[key]['titles'] += 1
            if r.score_percentage is not None:
                stream_records[key]['avg_score'].append(r.score_percentage)
        stream_leaderboard = []
        for rec in stream_records.values():
            scores = rec.pop('avg_score')
            rec['average_score'] = round(sum(scores) / len(scores), 2) if scores else None
            stream_leaderboard.append(rec)
        stream_leaderboard.sort(key=lambda r: (r['titles'], r['average_score'] or 0), reverse=True)

        return Response({
            'tournaments_completed': tournaments.count(),
            'total_entrants': TournamentEntry.objects.filter(tournament__in=tournaments, withdrawn=False).count(),
            'total_challenges_fought': challenges.count(),
            'most_decorated': sorted(titles_by_student.values(), key=lambda r: -r['count'])[:10],
            'most_duel_wins': sorted(win_counts.values(), key=lambda r: -r['wins'])[:10],
            'rising_stars': rising_stars,
            'stream_leaderboard': stream_leaderboard,
        })
