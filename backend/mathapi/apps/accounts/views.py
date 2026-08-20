from rest_framework import generics, status, viewsets, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework.decorators import action
import csv
import io

from .models import Subject, TeacherAssignment, AuditLog, SiteSettings
from .serializers import (
    UserSerializer, MeSerializer, RegisterSerializer, ChangePasswordSerializer,
    SubjectSerializer, TeacherAssignmentSerializer,
    AuditLogSerializer, SiteSettingsSerializer,
)
from .permissions import IsAdminRole
from . import audit_export

User = get_user_model()


# ── Auth views ────────────────────────────────────────────────────────────────

class LoginView(TokenObtainPairView):
    # A stricter, dedicated throttle scope — login is the single highest-
    # value target for credential brute-forcing, so it gets its own much
    # tighter rate limit (see DEFAULT_THROTTLE_RATES['login']) independent
    # of the general anon-request allowance.
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'login'

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            try:
                from rest_framework_simplejwt.tokens import AccessToken
                token = AccessToken(response.data['access'])
                user = User.objects.get(id=token['user_id'])
                response.data['user'] = UserSerializer(user).data
                AuditLog.objects.create(
                    user=user,
                    action=AuditLog.Action.LOGIN,
                    model_name='User',
                    object_id=str(user.id),
                    description=f'Login from {_get_client_ip(request)}',
                    ip_address=_get_client_ip(request),
                )
            except Exception:
                pass
        return response


class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get('refresh')
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()
            AuditLog.objects.create(
                user=request.user,
                action=AuditLog.Action.LOGOUT,
                model_name='User',
                object_id=str(request.user.id),
                description='Logout',
                ip_address=_get_client_ip(request),
            )
        except Exception:
            pass
        return Response({'detail': 'Logged out successfully.'})


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [IsAdminRole]


class MeView(generics.RetrieveUpdateAPIView):
    serializer_class = MeSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class ChangePasswordView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data['new_password'])
        request.user.save()
        return Response({'detail': 'Password changed successfully.'})


# ── Users ─────────────────────────────────────────────────────────────────────

class UserViewSet(viewsets.ModelViewSet):
    """Full CRUD for users. List/retrieve: admin + scoped teachers. Write: admin only."""
    serializer_class = UserSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['role', 'is_active']
    search_fields = ['email', 'first_name', 'last_name']
    ordering_fields = ['email', 'date_joined', 'first_name']
    ordering = ['first_name']

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminRole()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        if user.role == 'super_admin':
            return User.objects.all()
        if user.role == 'teacher':
            from .scoping import get_teacher_classrooms
            from mathapi.apps.students.models import StudentProfile
            classrooms = get_teacher_classrooms(user)
            student_ids = StudentProfile.objects.filter(
                classroom__in=classrooms
            ).values_list('user_id', flat=True)
            return User.objects.filter(id__in=student_ids, role='student')
        return User.objects.filter(id=user.id)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance == request.user:
            return Response(
                {'detail': 'You cannot delete your own account.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().destroy(request, *args, **kwargs)

    @action(detail=False, methods=['get'], url_path='assignable-teachers')
    def assignable_teachers(self, request):
        """Return all users who can be assigned as a teacher (teacher or super_admin role).
        Students and parents are excluded. This endpoint is admin-only.
        """
        if request.user.role != 'super_admin':
            return Response({'detail': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)
        qs = User.objects.filter(
            role__in=['teacher', 'super_admin'], is_active=True
        ).order_by('first_name', 'last_name')
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)


# ── Subjects ──────────────────────────────────────────────────────────────────

class SubjectViewSet(viewsets.ModelViewSet):
    serializer_class = SubjectSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['is_active']
    search_fields = ['name', 'code']

    def get_queryset(self):
        user = self.request.user
        if user.role == 'super_admin':
            return Subject.objects.all()
        # Teachers see only their assigned subjects
        from .scoping import get_teacher_subjects
        return get_teacher_subjects(user)

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            action_map = {'create': 'add', 'update': 'edit', 'partial_update': 'edit', 'destroy': 'delete'}
            from .permissions import TeacherFeatureEnabled
            # Admins always pass (TeacherFeatureEnabled short-circuits True
            # for super_admin); teachers only pass if an admin has switched
            # this on in Settings. Off by default, so behaviour is
            # unchanged (admin-only) unless an admin opts in.
            return [permissions.IsAuthenticated(),
                    TeacherFeatureEnabled('subjects', action_map[self.action])]
        return [permissions.IsAuthenticated()]


# ── TeacherAssignments ────────────────────────────────────────────────────────

class TeacherAssignmentViewSet(viewsets.ModelViewSet):
    serializer_class = TeacherAssignmentSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['teacher', 'classroom', 'subject']

    def get_queryset(self):
        user = self.request.user
        if user.role == 'super_admin':
            return TeacherAssignment.objects.select_related(
                'teacher', 'classroom', 'subject'
            ).all()
        return TeacherAssignment.objects.select_related(
            'teacher', 'classroom', 'subject'
        ).filter(teacher=user)

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminRole()]
        return [permissions.IsAuthenticated()]


# ── AuditLog ──────────────────────────────────────────────────────────────────
# Every view in this section is restricted to IsAdminRole, which checks
# request.user.role == 'super_admin' exactly — see permissions.py. There is
# no separate "admin" tier in this platform's role model, so "super admins
# only" and "IsAdminRole" are the same restriction throughout.

def _filter_audit_logs(request, qs=None):
    """Shared filtering used by the list view, stats, facets, and every
    export — so 'export what I'm looking at' always matches the table."""
    qs = (qs if qs is not None else AuditLog.objects.select_related('user')).all()
    params = request.query_params

    action_param = params.get('action')
    if action_param:
        qs = qs.filter(action=action_param)
    model_name = params.get('model_name')
    if model_name:
        qs = qs.filter(model_name=model_name)
    user_id = params.get('user')
    if user_id:
        qs = qs.filter(user_id=user_id)
    object_id = params.get('object_id')
    if object_id:
        qs = qs.filter(object_id=object_id)
    ip_address = params.get('ip_address')
    if ip_address:
        qs = qs.filter(ip_address=ip_address)
    search = params.get('search')
    if search:
        qs = qs.filter(
            Q(description__icontains=search) | Q(user__email__icontains=search)
            | Q(model_name__icontains=search) | Q(object_id__icontains=search)
        )
    date_from = params.get('date_from')
    if date_from:
        qs = qs.filter(timestamp__date__gte=date_from)
    date_to = params.get('date_to')
    if date_to:
        qs = qs.filter(timestamp__date__lte=date_to)
    return qs


class AuditLogListView(generics.ListAPIView):
    serializer_class = AuditLogSerializer
    permission_classes = [IsAdminRole]
    filter_backends = [OrderingFilter]
    ordering_fields = ['timestamp']
    ordering = ['-timestamp']

    def get_queryset(self):
        return _filter_audit_logs(self.request)


class AuditLogFacetsView(APIView):
    """
    GET /api/auth/audit-log/facets/
    Distinct actions, models, and users actually present in the audit
    log — populates the advanced-filter dropdowns without shipping every
    row, and without hardcoding a model/user list that drifts from
    what's actually been logged.
    """
    permission_classes = [IsAdminRole]

    def get(self, request):
        models = list(
            AuditLog.objects.exclude(model_name='').values_list('model_name', flat=True)
            .distinct().order_by('model_name')
        )
        users = list(
            AuditLog.objects.filter(user__isnull=False).values('user_id', 'user__email', 'user__first_name', 'user__last_name')
            .distinct().order_by('user__first_name')
        )
        return Response({
            'actions': [{'value': v, 'label': l} for v, l in AuditLog.Action.choices],
            'models': models,
            'users': [
                {'id': u['user_id'], 'email': u['user__email'],
                 'name': f"{u['user__first_name']} {u['user__last_name']}".strip() or u['user__email']}
                for u in users
            ],
        })


class AuditLogStatsView(APIView):
    """
    GET /api/auth/audit-log/stats/  (same filters as the list endpoint)
    Headline counters for the currently filtered view: totals by action,
    the busiest models, and the busiest users — the numbers behind the
    stat cards on the advanced audit log page.
    """
    permission_classes = [IsAdminRole]

    def get(self, request):
        qs = _filter_audit_logs(request)
        total = qs.count()
        by_action = dict(qs.values_list('action').annotate(n=Count('id')).values_list('action', 'n'))
        top_models = list(
            qs.exclude(model_name='').values('model_name').annotate(n=Count('id')).order_by('-n')[:6]
        )
        top_users = list(
            qs.filter(user__isnull=False).values('user_id', 'user__email', 'user__first_name', 'user__last_name')
            .annotate(n=Count('id')).order_by('-n')[:6]
        )
        return Response({
            'total': total,
            'by_action': {choice: by_action.get(choice, 0) for choice, _ in AuditLog.Action.choices},
            'top_models': [{'model_name': m['model_name'], 'count': m['n']} for m in top_models],
            'top_users': [
                {
                    'id': u['user_id'], 'email': u['user__email'],
                    'name': f"{u['user__first_name']} {u['user__last_name']}".strip() or u['user__email'],
                    'count': u['n'],
                }
                for u in top_users
            ],
        })


def _resolve_school_name(request) -> str:
    override = request.query_params.get('school_name')
    return override or SiteSettings.get().platform_name


class AuditLogCardPDFView(APIView):
    """GET /api/auth/audit-log/<id>/card/pdf/ — a single, detailed
    audit-entry PDF card, including the full field-level diff."""
    permission_classes = [IsAdminRole]

    def get(self, request, pk):
        log = get_object_or_404(AuditLog.objects.select_related('user'), pk=pk)
        pdf_bytes = audit_export.generate_single_card_pdf(log, {
            'school_name': _resolve_school_name(request),
            'generated_by': request.user.get_full_name() or request.user.email,
        })
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="audit_log_card_{log.id}.pdf"'
        return response


BATCH_CARD_EXPORT_LIMIT = 150


class AuditLogExportCardsPDFView(APIView):
    """
    GET /api/auth/audit-log/export/cards/pdf/  (same filters as the list
    endpoint) — one card per matching entry, several per page. Capped so
    a too-broad filter doesn't generate a multi-thousand-page PDF; narrow
    the filters (or export CSV instead) for a bigger result set.
    """
    permission_classes = [IsAdminRole]

    def get(self, request):
        qs = _filter_audit_logs(request).order_by('-timestamp')
        total = qs.count()
        if total == 0:
            return Response({'detail': 'No audit log entries match this filter.'}, status=404)
        if total > BATCH_CARD_EXPORT_LIMIT:
            return Response({
                'detail': f'{total} entries match — narrow your filters to {BATCH_CARD_EXPORT_LIMIT} or '
                          f'fewer for a card export, or use the CSV export for larger result sets.',
            }, status=400)
        logs = list(qs[:BATCH_CARD_EXPORT_LIMIT])
        pdf_bytes = audit_export.generate_batch_cards_pdf(logs, {
            'school_name': _resolve_school_name(request),
            'generated_by': request.user.get_full_name() or request.user.email,
        })
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="audit_log_cards.pdf"'
        return response


class AuditLogExportCSVView(APIView):
    """GET /api/auth/audit-log/export/csv/ (same filters as the list
    endpoint) — raw, one-row-per-entry export for spreadsheet analysis,
    unbounded (unlike the card export, since CSV rows are cheap)."""
    permission_classes = [IsAdminRole]

    def get(self, request):
        qs = _filter_audit_logs(request).order_by('-timestamp')
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            'ID', 'Timestamp', 'User Name', 'User Email', 'Action', 'Model',
            'Object ID', 'Description', 'IP Address', 'Changed Fields', 'Changes (JSON)',
        ])
        for log in qs.iterator():
            changed_fields = ', '.join((log.changes or {}).keys())
            writer.writerow([
                log.id, log.timestamp.isoformat(),
                log.user.get_full_name() if log.user else '', log.user.email if log.user else '',
                log.get_action_display(), log.model_name, log.object_id, log.description,
                log.ip_address or '', changed_fields, log.changes or '',
            ])
        response = HttpResponse(output.getvalue(), content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="audit_log_export.csv"'
        return response


# ── SiteSettings ──────────────────────────────────────────────────────────────

class SiteSettingsView(APIView):
    def get_permissions(self):
        if self.request.method == 'GET':
            return [permissions.AllowAny()]
        return [IsAdminRole()]

    def get(self, request):
        settings = SiteSettings.get()
        return Response(SiteSettingsSerializer(settings).data)

    def patch(self, request):
        settings = SiteSettings.get()
        serializer = SiteSettingsSerializer(settings, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        instance.updated_by_id = request.user.id
        instance.save(update_fields=['updated_by_id'])
        return Response(SiteSettingsSerializer(instance).data)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_client_ip(request):
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded:
        return x_forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')
