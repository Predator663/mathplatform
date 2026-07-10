from rest_framework import generics, status, viewsets, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.contrib.auth import get_user_model
from rest_framework.decorators import action

from .models import Subject, TeacherAssignment, AuditLog, SiteSettings
from .serializers import (
    UserSerializer, MeSerializer, RegisterSerializer, ChangePasswordSerializer,
    SubjectSerializer, TeacherAssignmentSerializer,
    AuditLogSerializer, SiteSettingsSerializer,
)
from .permissions import IsAdminRole

User = get_user_model()


# ── Auth views ────────────────────────────────────────────────────────────────

class LoginView(TokenObtainPairView):
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

class AuditLogListView(generics.ListAPIView):
    serializer_class = AuditLogSerializer
    permission_classes = [IsAdminRole]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['action', 'model_name', 'user']
    search_fields = ['description', 'user__email', 'model_name']
    ordering_fields = ['timestamp']
    ordering = ['-timestamp']

    def get_queryset(self):
        qs = AuditLog.objects.select_related('user').all()
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')
        if date_from:
            qs = qs.filter(timestamp__date__gte=date_from)
        if date_to:
            qs = qs.filter(timestamp__date__lte=date_to)
        return qs


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
