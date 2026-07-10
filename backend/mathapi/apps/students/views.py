import csv
import io
import secrets
from django.db import IntegrityError, transaction
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from .models import GradeLevel, Classroom, StudentProfile, ParentStudentLink
from .serializers import (
    GradeLevelSerializer, ClassroomSerializer,
    StudentProfileSerializer, StudentCreateSerializer, ParentStudentLinkSerializer,
)
from django.contrib.auth import get_user_model

User = get_user_model()


class IsTeacherOrAdmin(permissions.BasePermission):
    """Allows access only to teachers or super_admins (any other role, e.g.
    student/parent, is denied). Defined locally — if accounts/permissions.py
    already has an equivalent class, swap to that instead to avoid duplication."""

    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated
            and getattr(request.user, 'role', None) in ('teacher', 'super_admin')
        )


class IsAdminOrAssignedTeacher(permissions.BasePermission):
    """
    Classroom write permission.
    - create: any teacher or super_admin may create a classroom (there's no
      object yet to check ownership against).
    - update/partial_update/destroy: only super_admin, or the teacher
      currently assigned to *this specific* classroom via TeacherAssignment.
    Read actions (list/retrieve/students) are left to IsAuthenticated +
    get_queryset scoping and don't go through this class.
    """

    def has_permission(self, request, view):
        if view.action == 'create':
            return getattr(request.user, 'role', None) in ('teacher', 'super_admin')
        return True  # object-level check below decides update/destroy

    def has_object_permission(self, request, view, obj):
        if request.user.role == 'super_admin':
            return True
        if request.user.role == 'teacher':
            from mathapi.apps.accounts.scoping import get_teacher_classrooms
            return get_teacher_classrooms(request.user).filter(id=obj.id).exists()
        return False


class GradeLevelViewSet(viewsets.ModelViewSet):
    queryset = GradeLevel.objects.all()
    serializer_class = GradeLevelSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_permissions(self):
        # GradeLevel is shared reference data — any authenticated user (including
        # students/parents) may read it, but only an admin can create, edit, or
        # delete entries. Previously this was IsAuthenticated for every action,
        # so any logged-in student could create/update/delete grade levels.
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            from mathapi.apps.accounts.permissions import IsAdminRole
            return [IsAdminRole()]
        return [permissions.IsAuthenticated()]


class ClassroomViewSet(viewsets.ModelViewSet):
    serializer_class = ClassroomSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['academic_year', 'is_active', 'grade_level']
    search_fields = ['name']
    ordering_fields = ['name', 'academic_year']

    def get_permissions(self):
        # Write actions previously only required IsAuthenticated, with no
        # object-level check — combined with the (now-fixed) unscoped
        # get_queryset(), a student or parent could update or delete *any*
        # classroom by ID. create needs teacher/admin; update/partial_update/
        # destroy need admin or the assigned teacher (checked per-object below).
        # TeacherFeatureEnabled additionally lets an admin turn each of
        # add/edit/delete off for teachers from Settings — super admins are
        # never affected by that toggle.
        from mathapi.apps.accounts.permissions import TeacherFeatureEnabled
        if self.action == 'create':
            return [permissions.IsAuthenticated(), IsAdminOrAssignedTeacher(),
                    TeacherFeatureEnabled('classrooms', 'add')]
        if self.action in ['update', 'partial_update']:
            return [permissions.IsAuthenticated(), IsAdminOrAssignedTeacher(),
                    TeacherFeatureEnabled('classrooms', 'edit')]
        if self.action == 'destroy':
            return [permissions.IsAuthenticated(), IsAdminOrAssignedTeacher(),
                    TeacherFeatureEnabled('classrooms', 'delete')]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        from django.db.models import Count, Q
        user = self.request.user
        qs = Classroom.objects.select_related('grade_level').prefetch_related(
            'teacher_assignments__teacher', 'teacher_assignments__subject'
        ).annotate(
            active_student_count=Count(
                'student_profiles', filter=Q(student_profiles__is_active=True), distinct=True,
            )
        )
        if user.role == 'super_admin':
            qs = qs.all()
        elif user.role == 'teacher':
            from mathapi.apps.accounts.scoping import get_teacher_classrooms
            qs = get_teacher_classrooms(user, base_qs=qs)
        elif user.role == 'student':
            try:
                qs = qs.filter(id=user.student_profile.classroom_id)
            except StudentProfile.DoesNotExist:
                return qs.none()
        elif user.role == 'parent':
            classroom_ids = user.linked_students.values_list('student__classroom', flat=True)
            qs = qs.filter(id__in=classroom_ids)
        else:
            return qs.none()

        # Optional subject filter — narrows to classrooms where that subject is
        # taught. Used by AtRisk and ClassroomDetail to scope their dropdowns.
        subject_id = self.request.query_params.get('subject_id')
        if subject_id:
            try:
                qs = qs.filter(teacher_assignments__subject_id=int(subject_id)).distinct()
            except (ValueError, TypeError):
                pass

        return qs

    @action(detail=True, methods=['get'])
    def students(self, request, pk=None):
        classroom = self.get_object()
        students = StudentProfile.objects.filter(
            classroom=classroom, is_active=True
        ).select_related('user')
        return Response(StudentProfileSerializer(students, many=True).data)


class StudentProfileViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['classroom', 'is_active', 'classroom__academic_year']
    search_fields = ['user__first_name', 'user__last_name', 'user__email', 'student_id']
    ordering_fields = ['user__last_name', 'student_id', 'enrollment_date']

    def get_permissions(self):
        # create() and bulk_import previously bypassed get_queryset() scoping
        # entirely and only required IsAuthenticated, so any logged-in
        # student or parent could mint new student accounts (with generated
        # passwords) one at a time or in bulk. Now restricted to teacher/admin.
        #
        # SECURITY FIX: update/partial_update/destroy previously had NO role
        # restriction at all (fell through to the bare IsAuthenticated()
        # below). Since get_queryset() returns a student's own profile to
        # that same student, and a parent's linked children to that parent,
        # this meant a student could PATCH their own record (including
        # `classroom`, `is_active`, `enrollment_date`, etc.) or outright
        # DELETE it — and a parent could do the same to their child's
        # record. Now restricted to teacher/admin, with TeacherFeatureEnabled
        # additionally letting an admin toggle add/edit/delete off for
        # teachers from Settings.
        from mathapi.apps.accounts.permissions import TeacherFeatureEnabled
        if self.action in ['create', 'bulk_import']:
            return [IsTeacherOrAdmin(), TeacherFeatureEnabled('students', 'add')]
        if self.action in ['update', 'partial_update']:
            return [IsTeacherOrAdmin(), TeacherFeatureEnabled('students', 'edit')]
        if self.action == 'destroy':
            return [IsTeacherOrAdmin(), TeacherFeatureEnabled('students', 'delete')]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        qs = StudentProfile.objects.select_related('user', 'classroom__grade_level')
        if user.role == 'student':
            return qs.filter(user=user)
        if user.role == 'parent':
            return qs.filter(parent_links__parent=user)
        if user.role == 'teacher':
            from mathapi.apps.accounts.scoping import get_teacher_classrooms
            return qs.filter(classroom__in=get_teacher_classrooms(user))
        return qs.all()

    def get_serializer_class(self):
        if self.action == 'create':
            return StudentCreateSerializer
        return StudentProfileSerializer

    def create(self, request, *args, **kwargs):
        serializer = StudentCreateSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        profile = serializer.save()
        out = StudentProfileSerializer(profile)
        response_data = out.data
        if hasattr(profile, '_generated_password'):
            response_data['generated_password'] = profile._generated_password
        return Response(response_data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'])
    def performance_summary(self, request, pk=None):
        from mathapi.apps.analytics.services import get_student_summary
        student = self.get_object()
        created_by_id = request.user.id if request.user.role == 'teacher' else None
        return Response(get_student_summary(student.id, created_by_id=created_by_id))

    @action(detail=False, methods=['post'], parser_classes=[MultiPartParser, FormParser])
    def bulk_import(self, request):
        csv_file = request.FILES.get('file')
        if not csv_file:
            return Response({'detail': 'No file provided.'}, status=status.HTTP_400_BAD_REQUEST)
        if not csv_file.name.endswith('.csv'):
            return Response({'detail': 'File must be a CSV.'}, status=status.HTTP_400_BAD_REQUEST)

        decoded = csv_file.read().decode('utf-8-sig')
        reader = csv.DictReader(io.StringIO(decoded))

        required_cols = {'first_name', 'last_name', 'email', 'student_id'}
        if not reader.fieldnames:
            return Response({'detail': 'Empty CSV file.'}, status=status.HTTP_400_BAD_REQUEST)

        missing_cols = required_cols - {c.strip().lower() for c in reader.fieldnames}
        if missing_cols:
            return Response({'detail': f'Missing columns: {", ".join(missing_cols)}'}, status=status.HTTP_400_BAD_REQUEST)

        created, skipped, errors = [], [], []

        # Restrict which classroom_id values a row can resolve to. A teacher
        # could otherwise place imported students into a classroom they
        # don't actually teach by putting an arbitrary ID in the CSV — admin
        # keeps unrestricted access since they already have it everywhere
        # else in the app.
        if request.user.role == 'teacher':
            from mathapi.apps.accounts.scoping import get_teacher_classrooms
            allowed_classrooms = get_teacher_classrooms(request.user)
        else:
            allowed_classrooms = Classroom.objects.all()

        for i, row in enumerate(reader, start=2):
            row = {k.strip().lower(): v.strip() for k, v in row.items() if k}
            email = row.get('email', '')
            student_id = row.get('student_id', '')

            if not email or not student_id:
                errors.append({'row': i, 'error': 'email and student_id are required'})
                continue

            if User.objects.filter(email=email).exists():
                skipped.append({'row': i, 'email': email, 'reason': 'Email already exists'})
                continue
            if StudentProfile.objects.filter(student_id=student_id).exists():
                skipped.append({'row': i, 'student_id': student_id, 'reason': 'Student ID already exists'})
                continue

            try:
                with transaction.atomic():
                    password = secrets.token_urlsafe(10)
                    user = User.objects.create_user(
                        email=email, first_name=row.get('first_name', ''),
                        last_name=row.get('last_name', ''), role='student', password=password,
                    )
                    classroom = None
                    classroom_id = row.get('classroom_id', '').strip()
                    if classroom_id:
                        try:
                            classroom = allowed_classrooms.get(id=int(classroom_id))
                        except (Classroom.DoesNotExist, ValueError):
                            pass

                    profile = StudentProfile.objects.create(
                        user=user, student_id=student_id, classroom=classroom,
                        date_of_birth=row.get('date_of_birth', '').strip() or None,
                        notes=row.get('notes', ''),
                    )
                created.append({'row': i, 'student_id': student_id,
                                 'name': user.get_full_name(), 'email': email,
                                 'generated_password': password})
            except IntegrityError:
                errors.append({'row': i, 'error': 'Student ID or email already exists (race condition).'})
            except Exception as e:
                errors.append({'row': i, 'error': str(e)})

        return Response({
            'created': len(created), 'skipped': len(skipped), 'errors_count': len(errors),
            'students': created, 'skipped_detail': skipped, 'errors': errors,
        }, status=status.HTTP_207_MULTI_STATUS if (skipped or errors) else status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'])
    def import_template(self, request):
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['first_name', 'last_name', 'email', 'student_id', 'classroom_id', 'date_of_birth', 'notes'])
        writer.writerow(['Alice', 'Mensah', 'alice.mensah@school.edu', 'STU1001', '1', '2008-05-14', ''])
        from django.http import HttpResponse
        response = HttpResponse(output.getvalue(), content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="student_import_template.csv"'
        return response


class ParentStudentLinkViewSet(viewsets.ModelViewSet):
    serializer_class = ParentStudentLinkSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_permissions(self):
        # This table backs verify_student_access()'s parent-role check in
        # accounts/scoping.py — anyone who could write to it could grant
        # themselves access to an arbitrary student's grades and reports.
        # Restricted to admin only, per decision.
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            from mathapi.apps.accounts.permissions import IsAdminRole
            return [IsAdminRole()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        # Previously a flat, unfiltered queryset — any authenticated user
        # (student, parent, teacher) could list every parent-student link in
        # the school. Now scoped: parents/students see only their own links,
        # teachers see links for students in their classrooms, admin sees all.
        user = self.request.user
        qs = ParentStudentLink.objects.select_related('parent', 'student__user')
        if user.role == 'super_admin':
            return qs
        if user.role == 'parent':
            return qs.filter(parent=user)
        if user.role == 'student':
            return qs.filter(student__user=user)
        if user.role == 'teacher':
            from mathapi.apps.accounts.scoping import get_teacher_classrooms
            return qs.filter(student__classroom__in=get_teacher_classrooms(user))
        return qs.none()
