from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser

from mathapi.apps.accounts.permissions import IsTeacherOrAdmin
from mathapi.apps.accounts.scoping import assert_classroom_owned, get_teacher_classrooms
from mathapi.apps.students.models import Classroom, StudentProfile
from .models import StudentGroup, GroupMembership, GroupTransferLog, PerformanceTier, DEFAULT_BADGE_COLORS, PeerConstraint
from .serializers import StudentGroupSerializer, GroupTransferLogSerializer, PeerConstraintSerializer
from . import services


def _owned_classroom_or_404(user, classroom_id):
    classroom = get_object_or_404(Classroom, id=classroom_id)
    if user.role == 'teacher':
        assert_classroom_owned(user, classroom_id)  # raises PermissionDenied
    return classroom


class PeerConstraintViewSet(viewsets.ModelViewSet):
    """
    CRUD for standing 'keep apart' / 'keep together' rules between two
    students in a classroom. auto-generate reads these and tries to
    honour them (hard for 'avoid', best-effort for 'prefer').
    """
    serializer_class = PeerConstraintSerializer
    permission_classes = [permissions.IsAuthenticated, IsTeacherOrAdmin]

    def get_queryset(self):
        qs = PeerConstraint.objects.select_related('classroom', 'student_a__user', 'student_b__user')
        user = self.request.user
        if user.role != 'super_admin':
            qs = qs.filter(classroom__in=get_teacher_classrooms(user))
        classroom_id = self.request.query_params.get('classroom')
        if classroom_id:
            qs = qs.filter(classroom_id=classroom_id)
        return qs

    def perform_create(self, serializer):
        classroom = serializer.validated_data.get('classroom')
        _owned_classroom_or_404(self.request.user, classroom.id)
        serializer.save(created_by=self.request.user)

    def perform_destroy(self, instance):
        _owned_classroom_or_404(self.request.user, instance.classroom_id)
        instance.delete()


class StudentGroupViewSet(viewsets.ModelViewSet):
    """
    CRUD for peer-learning groups, plus the auto-generation and
    membership-transfer actions. Every classroom-touching action is
    scoped so a teacher can only ever see/edit groups in classrooms
    they're actually assigned to — admins see everything.
    """
    serializer_class = StudentGroupSerializer
    permission_classes = [permissions.IsAuthenticated, IsTeacherOrAdmin]

    def get_queryset(self):
        qs = StudentGroup.objects.select_related('classroom', 'subject').prefetch_related(
            'memberships__student__user'
        )
        user = self.request.user
        if user.role != 'super_admin':
            qs = qs.filter(classroom__in=get_teacher_classrooms(user))
        classroom_id = self.request.query_params.get('classroom')
        if classroom_id:
            qs = qs.filter(classroom_id=classroom_id)
        academic_year = self.request.query_params.get('academic_year')
        if academic_year:
            qs = qs.filter(academic_year=academic_year)
        return qs

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['request'] = self.request
        return ctx

    def perform_create(self, serializer):
        classroom = serializer.validated_data.get('classroom')
        _owned_classroom_or_404(self.request.user, classroom.id)
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        classroom = serializer.instance.classroom
        _owned_classroom_or_404(self.request.user, classroom.id)
        new_classroom = serializer.validated_data.get('classroom')
        if new_classroom and new_classroom.id != classroom.id:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({'classroom': 'A group cannot be moved to a different classroom.'})
        serializer.save()

    def perform_destroy(self, instance):
        _owned_classroom_or_404(self.request.user, instance.classroom_id)
        instance.delete()

    # ── Badge upload ─────────────────────────────────────────────────────
    @action(detail=True, methods=['post'], url_path='upload-badge', parser_classes=[MultiPartParser, FormParser])
    def upload_badge(self, request, pk=None):
        group = self.get_object()
        _owned_classroom_or_404(request.user, group.classroom_id)
        image = request.FILES.get('badge_image')
        if not image:
            return Response({'detail': 'badge_image file is required.'}, status=status.HTTP_400_BAD_REQUEST)
        if image.size > 3 * 1024 * 1024:
            return Response({'detail': 'Badge image must be under 3MB.'}, status=status.HTTP_400_BAD_REQUEST)
        if not (image.content_type or '').startswith('image/'):
            return Response({'detail': 'File must be an image.'}, status=status.HTTP_400_BAD_REQUEST)
        group.badge_image = image
        group.save(update_fields=['badge_image', 'updated_at'])
        return Response(StudentGroupSerializer(group, context={'request': request}).data)

    # ── Manual membership editing ───────────────────────────────────────
    @action(detail=True, methods=['post'], url_path='add-member')
    def add_member(self, request, pk=None):
        group = self.get_object()
        _owned_classroom_or_404(request.user, group.classroom_id)
        student_id = request.data.get('student_id')
        student = get_object_or_404(StudentProfile, id=student_id, classroom_id=group.classroom_id)

        # Moving into this group means leaving whatever group they were in
        # within the same classroom — a student only ever belongs to one
        # group per classroom at a time.
        old_membership = GroupMembership.objects.filter(
            student=student, group__classroom_id=group.classroom_id
        ).exclude(group=group).first()
        from_group = old_membership.group if old_membership else None
        if old_membership:
            old_membership.delete()

        perf = [r for r in services.get_classroom_student_performance(group.classroom_id)
                if r['student_id'] == student.id]
        avg = perf[0]['average'] if perf else None
        tier = perf[0]['tier'] if perf else PerformanceTier.UNRATED

        membership, created = GroupMembership.objects.get_or_create(
            group=group, student=student,
            defaults={'tier': tier, 'average_at_placement': avg, 'is_anchor': tier in services.ANCHOR_TIERS},
        )
        GroupTransferLog.objects.create(
            student=student, from_group=from_group, to_group=group,
            reason=request.data.get('reason', ''), transferred_by=request.user,
        )
        return Response(StudentGroupSerializer(group, context={'request': request}).data)

    @action(detail=True, methods=['post'], url_path='remove-member')
    def remove_member(self, request, pk=None):
        group = self.get_object()
        _owned_classroom_or_404(request.user, group.classroom_id)
        student_id = request.data.get('student_id')
        membership = get_object_or_404(GroupMembership, group=group, student_id=student_id)
        membership.delete()
        GroupTransferLog.objects.create(
            student_id=student_id, from_group=group, to_group=None,
            reason=request.data.get('reason', 'Removed from group'), transferred_by=request.user,
        )
        return Response(StudentGroupSerializer(group, context={'request': request}).data)

    # ── Transfer between two existing groups ────────────────────────────
    @action(detail=False, methods=['post'], url_path='transfer-member')
    def transfer_member(self, request):
        student_id = request.data.get('student_id')
        to_group_id = request.data.get('to_group_id')
        reason = request.data.get('reason', '')
        if not student_id or not to_group_id:
            return Response({'detail': 'student_id and to_group_id are required.'}, status=400)

        to_group = get_object_or_404(StudentGroup, id=to_group_id)
        _owned_classroom_or_404(request.user, to_group.classroom_id)
        student = get_object_or_404(StudentProfile, id=student_id, classroom_id=to_group.classroom_id)

        with transaction.atomic():
            existing = GroupMembership.objects.filter(
                student=student, group__classroom_id=to_group.classroom_id
            ).select_related('group').first()

            if existing and existing.group_id == to_group.id:
                return Response({'detail': 'Student is already in that group.'}, status=400)

            source_group = existing.group if existing else None
            warnings = []
            if existing:
                source_members = list(existing.group.memberships.all())
                dest_members = list(to_group.memberships.all())
                classroom_group_count = StudentGroup.objects.filter(classroom_id=to_group.classroom_id).count()
                classroom_student_count = StudentProfile.objects.filter(
                    classroom_id=to_group.classroom_id, is_active=True
                ).count()
                avg_size = (classroom_student_count / classroom_group_count) if classroom_group_count else None
                warnings = services.check_transfer_warnings(
                    source_members, dest_members, student.id, average_group_size=avg_size
                )
                existing.delete()

            perf = [r for r in services.get_classroom_student_performance(to_group.classroom_id)
                    if r['student_id'] == student.id]
            avg = perf[0]['average'] if perf else None
            tier = perf[0]['tier'] if perf else PerformanceTier.UNRATED

            GroupMembership.objects.create(
                group=to_group, student=student, tier=tier,
                average_at_placement=avg, is_anchor=tier in services.ANCHOR_TIERS,
            )
            log = GroupTransferLog.objects.create(
                student=student, from_group=source_group, to_group=to_group,
                reason=reason, warnings='; '.join(warnings), transferred_by=request.user,
            )

        return Response({
            'detail': f'{student.full_name} moved to {to_group.name}.',
            'warnings': warnings,
            'transfer': GroupTransferLogSerializer(log).data,
        })

    # ── Auto-generation ──────────────────────────────────────────────────
    @action(detail=False, methods=['post'], url_path='auto-generate')
    def auto_generate(self, request):
        classroom_id = request.data.get('classroom_id')
        if not classroom_id:
            return Response({'detail': 'classroom_id is required.'}, status=400)
        classroom = _owned_classroom_or_404(request.user, classroom_id)

        academic_year = request.data.get('academic_year') or classroom.academic_year
        subject_id = request.data.get('subject_id') or None
        term = request.data.get('term') or ''
        name_prefix = (request.data.get('name_prefix') or 'Group').strip()
        replace_existing = bool(request.data.get('replace_existing', False))
        group_count = request.data.get('group_count')
        group_size = request.data.get('group_size')
        try:
            group_count = int(group_count) if group_count not in (None, '') else None
            group_size = int(group_size) if group_size not in (None, '') else None
        except (TypeError, ValueError):
            return Response({'detail': 'group_count and group_size must be numbers.'}, status=400)

        created_by_id = request.user.id if request.user.role == 'teacher' else None
        performance = services.get_classroom_student_performance(
            classroom_id, subject_id=subject_id, term=term or None,
            academic_year=academic_year, created_by_id=created_by_id,
        )
        if not performance:
            return Response({'detail': 'No active students in this classroom.'}, status=400)

        plan = services.plan_balanced_groups(performance, group_count=group_count, group_size=group_size)

        constraints = PeerConstraint.objects.filter(classroom_id=classroom_id).select_related('student_a__user', 'student_b__user')
        performance_ids = {p['student_id'] for p in performance}
        avoid_pairs, prefer_pairs, name_by_id = set(), set(), {}
        for c in constraints:
            if c.student_a_id not in performance_ids or c.student_b_id not in performance_ids:
                continue  # constraint involves a student not in this grouping round
            pair = services._pair_key(c.student_a_id, c.student_b_id)
            (avoid_pairs if c.constraint_type == PeerConstraint.ConstraintType.AVOID else prefer_pairs).add(pair)
            name_by_id[c.student_a_id] = c.student_a.full_name
            name_by_id[c.student_b_id] = c.student_b.full_name

        if avoid_pairs or prefer_pairs:
            constraint_warnings = services.apply_peer_constraints(
                plan['groups'], avoid_pairs, prefer_pairs, name_by_id=name_by_id,
            )
            plan['warnings'].extend(constraint_warnings)

        with transaction.atomic():
            if replace_existing:
                StudentGroup.objects.filter(classroom_id=classroom_id, academic_year=academic_year).delete()

            existing_names = set(
                StudentGroup.objects.filter(classroom_id=classroom_id, academic_year=academic_year)
                .values_list('name', flat=True)
            )

            created_groups = []
            for i, members in enumerate(plan['groups']):
                # Skip auto-naming collisions with groups a teacher already
                # made by hand (e.g. re-running auto-generate to fill in
                # remaining students without clobbering custom names).
                name = f'{name_prefix} {chr(65 + i)}' if i < 26 else f'{name_prefix} {i + 1}'
                n = name
                suffix = 1
                while n in existing_names:
                    suffix += 1
                    n = f'{name} ({suffix})'
                existing_names.add(n)

                group = StudentGroup.objects.create(
                    classroom_id=classroom_id, name=n, academic_year=academic_year,
                    subject_id=subject_id, term=term, created_by=request.user,
                    badge_color=DEFAULT_BADGE_COLORS[i % len(DEFAULT_BADGE_COLORS)],
                )
                for m in members:
                    GroupMembership.objects.create(
                        group=group, student_id=m['student_id'], tier=m['tier'],
                        average_at_placement=m['average'], is_anchor=m['tier'] in services.ANCHOR_TIERS,
                    )
                    GroupTransferLog.objects.create(
                        student_id=m['student_id'], from_group=None, to_group=group,
                        reason='Auto-generated', transferred_by=request.user,
                    )
                created_groups.append(group)

        serialized = StudentGroupSerializer(created_groups, many=True, context={'request': request}).data
        return Response({'groups': serialized, 'warnings': plan['warnings']}, status=201)


class ClassroomGroupsOverviewView(APIView):
    """
    GET /api/groups/classroom/<id>/overview/
    Single call that feeds the whole Groups page: every student's current
    performance tier, existing groups with members, and anyone not yet
    placed in a group.
    """
    permission_classes = [permissions.IsAuthenticated, IsTeacherOrAdmin]

    def get(self, request, classroom_id):
        classroom = _owned_classroom_or_404(request.user, classroom_id)
        subject_id = request.query_params.get('subject_id') or None
        term = request.query_params.get('term') or None
        academic_year = request.query_params.get('academic_year') or classroom.academic_year
        created_by_id = request.user.id if request.user.role == 'teacher' else None

        performance = services.get_classroom_student_performance(
            classroom_id, subject_id=subject_id, term=term,
            academic_year=academic_year, created_by_id=created_by_id,
        )
        groups = StudentGroup.objects.filter(
            classroom_id=classroom_id, academic_year=academic_year
        ).select_related('subject').prefetch_related('memberships__student__user').order_by('name')

        grouped_student_ids = set(
            GroupMembership.objects.filter(group__classroom_id=classroom_id, group__academic_year=academic_year)
            .values_list('student_id', flat=True)
        )
        ungrouped = [p for p in performance if p['student_id'] not in grouped_student_ids]

        tier_counts = {t: 0 for t in PerformanceTier.values}
        for p in performance:
            tier_counts[p['tier']] += 1

        return Response({
            'classroom_id': classroom.id,
            'classroom_name': str(classroom),
            'academic_year': academic_year,
            'performance': performance,
            'tier_counts': tier_counts,
            'groups': StudentGroupSerializer(groups, many=True, context={'request': request}).data,
            'ungrouped_students': ungrouped,
        })


class ClassroomRebalanceSuggestionsView(APIView):
    """
    GET /api/groups/classroom/<id>/rebalance-suggestions/
    Live tier drift since placement, plus groups that currently have no
    anchor-tier student, with candidate students to move in. Advisory
    only — nothing here is applied without an explicit transfer call.
    """
    permission_classes = [permissions.IsAuthenticated, IsTeacherOrAdmin]

    def get(self, request, classroom_id):
        classroom = _owned_classroom_or_404(request.user, classroom_id)
        subject_id = request.query_params.get('subject_id') or None
        term = request.query_params.get('term') or None
        academic_year = request.query_params.get('academic_year') or classroom.academic_year
        created_by_id = request.user.id if request.user.role == 'teacher' else None

        data = services.get_rebalance_suggestions(
            classroom_id, academic_year=academic_year, subject_id=subject_id,
            term=term, created_by_id=created_by_id,
        )
        return Response({
            'classroom_id': classroom.id,
            'classroom_name': str(classroom),
            'academic_year': academic_year,
            **data,
        })


class ClassroomGroupEffectivenessView(APIView):
    """
    GET /api/groups/classroom/<id>/effectiveness/
    Whether the peer groups are actually helping: per-student and
    per-group score movement since each student joined their current
    group, plus a classroom-wide anchor-vs-non-anchor split.
    """
    permission_classes = [permissions.IsAuthenticated, IsTeacherOrAdmin]

    def get(self, request, classroom_id):
        classroom = _owned_classroom_or_404(request.user, classroom_id)
        subject_id = request.query_params.get('subject_id') or None
        term = request.query_params.get('term') or None
        academic_year = request.query_params.get('academic_year') or classroom.academic_year
        created_by_id = request.user.id if request.user.role == 'teacher' else None

        data = services.get_group_effectiveness(
            classroom_id, academic_year=academic_year, subject_id=subject_id,
            term=term, created_by_id=created_by_id,
        )
        return Response({
            'classroom_id': classroom.id,
            'classroom_name': str(classroom),
            'academic_year': academic_year,
            **data,
        })


class ClassroomGroupTransfersView(APIView):
    """GET /api/groups/classroom/<id>/transfers/ — audit trail of moves."""
    permission_classes = [permissions.IsAuthenticated, IsTeacherOrAdmin]

    def get(self, request, classroom_id):
        _owned_classroom_or_404(request.user, classroom_id)
        logs = GroupTransferLog.objects.filter(
            Q(from_group__classroom_id=classroom_id) | Q(to_group__classroom_id=classroom_id)
        ).select_related('student__user', 'from_group', 'to_group', 'transferred_by').distinct()[:200]
        return Response(GroupTransferLogSerializer(logs, many=True).data)
