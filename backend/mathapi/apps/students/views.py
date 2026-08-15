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
from .models import GradeLevel, Classroom, Stream, StudentProfile, ParentStudentLink
from .serializers import (
    GradeLevelSerializer, ClassroomSerializer, StreamSerializer,
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
            'teacher_assignments__teacher', 'teacher_assignments__subject', 'streams'
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


class StreamViewSet(viewsets.ModelViewSet):
    """
    CRUD for streams (sections like "A", "B") within a classroom.
    Scoped identically to ClassroomViewSet: admins see/manage everything,
    teachers see/manage only streams of classrooms they're assigned to.
    Reuses the 'classrooms' TeacherFeatureEnabled toggle rather than adding
    a new admin-settings resource key, since a stream is a sub-resource of
    its classroom.
    """
    serializer_class = StreamSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['classroom', 'is_active']
    search_fields = ['name']
    ordering_fields = ['name', 'created_at']

    def get_permissions(self):
        from mathapi.apps.accounts.permissions import TeacherFeatureEnabled
        if self.action == 'create':
            return [permissions.IsAuthenticated(), TeacherFeatureEnabled('classrooms', 'add')]
        if self.action in ['update', 'partial_update']:
            return [permissions.IsAuthenticated(), TeacherFeatureEnabled('classrooms', 'edit')]
        if self.action == 'destroy':
            return [permissions.IsAuthenticated(), TeacherFeatureEnabled('classrooms', 'delete')]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        from django.db.models import Count, Q
        user = self.request.user
        qs = Stream.objects.select_related('classroom').annotate(
            active_student_count=Count(
                'students', filter=Q(students__is_active=True), distinct=True,
            )
        ).order_by('classroom__name', 'name')
        if user.role == 'super_admin':
            return qs
        if user.role == 'teacher':
            from mathapi.apps.accounts.scoping import get_teacher_classrooms
            return qs.filter(classroom__in=get_teacher_classrooms(user))
        if user.role == 'student':
            try:
                return qs.filter(classroom_id=user.student_profile.classroom_id)
            except StudentProfile.DoesNotExist:
                return qs.none()
        if user.role == 'parent':
            classroom_ids = user.linked_students.values_list('student__classroom', flat=True)
            return qs.filter(classroom_id__in=classroom_ids)
        return qs.none()

    def perform_create(self, serializer):
        classroom = serializer.validated_data.get('classroom')
        if self.request.user.role == 'teacher' and classroom is not None:
            from mathapi.apps.accounts.scoping import get_teacher_classrooms
            if not get_teacher_classrooms(self.request.user).filter(id=classroom.id).exists():
                self.permission_denied(self.request, message='You are not assigned to this classroom.')
        serializer.save()

    def check_object_permissions(self, request, obj):
        # Delegate the classroom-ownership check to IsAdminOrAssignedTeacher
        # using obj.classroom instead of obj — a stream has no owning
        # teacher of its own, only via its parent classroom.
        if request.user.role == 'teacher' and self.action in ('update', 'partial_update', 'destroy'):
            from mathapi.apps.accounts.scoping import get_teacher_classrooms
            if not get_teacher_classrooms(request.user).filter(id=obj.classroom_id).exists():
                self.permission_denied(request, message='You are not assigned to this classroom.')
        super().check_object_permissions(request, obj)

    @action(detail=False, methods=['post'])
    def bulk_assign(self, request):
        """Assign a batch of students (by id) to a stream in one call."""
        from mathapi.apps.accounts.permissions import TeacherFeatureEnabled
        if not TeacherFeatureEnabled('students', 'edit').has_permission(request, self):
            return Response({'detail': 'You do not have permission to assign students to streams.'},
                             status=status.HTTP_403_FORBIDDEN)

        stream_id = request.data.get('stream_id')
        student_ids = request.data.get('student_ids') or []
        if not isinstance(student_ids, list) or not student_ids:
            return Response({'detail': 'student_ids must be a non-empty list.'}, status=status.HTTP_400_BAD_REQUEST)

        stream = None
        if stream_id:
            stream = self.get_queryset().filter(id=stream_id).first()
            if not stream:
                return Response({'detail': 'Stream not found or not accessible.'}, status=status.HTTP_404_NOT_FOUND)

        # Scope students the same way StudentProfileViewSet.get_queryset does,
        # so a teacher can't bulk-move students outside their own classrooms.
        students_qs = StudentProfile.objects.filter(id__in=student_ids)
        if request.user.role == 'teacher':
            from mathapi.apps.accounts.scoping import get_teacher_classrooms
            students_qs = students_qs.filter(classroom__in=get_teacher_classrooms(request.user))
        elif request.user.role != 'super_admin':
            return Response({'detail': 'Not permitted.'}, status=status.HTTP_403_FORBIDDEN)

        if stream:
            mismatched = students_qs.exclude(classroom_id=stream.classroom_id).count()
            if mismatched:
                return Response(
                    {'detail': f'{mismatched} of the selected students are not in this stream\'s classroom.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        updated = students_qs.update(stream=stream)
        return Response({'updated': updated, 'stream_id': stream.id if stream else None})


class StudentProfileViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['classroom', 'stream', 'is_active', 'classroom__academic_year',
                         'classroom__grade_level']
    search_fields = ['user__first_name', 'user__last_name', 'user__email', 'student_id']
    ordering_fields = ['user__last_name', 'user__first_name', 'student_id',
                        'enrollment_date', 'classroom__name', 'is_active']

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
        if self.action in ['destroy', 'bulk_delete']:
            return [IsTeacherOrAdmin(), TeacherFeatureEnabled('students', 'delete')]
        if self.action == 'duplicates':
            return [IsTeacherOrAdmin()]
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

    @action(detail=False, methods=['patch'], url_path='me/target',
            permission_classes=[permissions.IsAuthenticated])
    def set_my_target(self, request):
        """PATCH /students/profiles/me/target/ — a student sets their own
        dashboard goal. Deliberately separate from update/partial_update:
        those are teacher/admin-only (see get_permissions above, and the
        security-fix note on why student write-access there is locked
        down). This action only ever touches request.user's own profile
        and only the single target_percentage field, so it can't be used
        to edit classroom, is_active, or anyone else's record.
        """
        profile = getattr(request.user, 'student_profile', None)
        if request.user.role != 'student' or profile is None:
            return Response({'detail': 'Only students can set their own target.'}, status=status.HTTP_403_FORBIDDEN)
        value = request.data.get('target_percentage', None)
        if value is None:
            profile.target_percentage = None
        else:
            try:
                value = int(value)
            except (TypeError, ValueError):
                return Response({'target_percentage': 'Must be a whole number.'}, status=status.HTTP_400_BAD_REQUEST)
            if not (0 <= value <= 100):
                return Response({'target_percentage': 'Must be between 0 and 100.'}, status=status.HTTP_400_BAD_REQUEST)
            profile.target_percentage = value
        profile.save(update_fields=['target_percentage'])
        return Response({'target_percentage': profile.target_percentage}, status=status.HTTP_200_OK)

    # Fields a "possible duplicate" can be matched on. `name` is a virtual
    # key (first + last name combined) since full_name isn't a real DB
    # column; the rest are matched on the column directly. Kept as a class
    # attr (not a local dict in the action) so the frontend's choices and
    # the backend's validation can't drift apart from a single glance here.
    DUPLICATE_MATCH_FIELDS = {
        'name': ['user__first_name', 'user__last_name'],
        'email': ['user__email'],
        'index_number': ['index_number'],
        'parent_phone': ['parent_phone'],
        'date_of_birth': ['date_of_birth'],
    }

    @action(detail=False, methods=['get'])
    def duplicates(self, request):
        """
        Groups students that share the same value for `by` (default:
        name) and returns only the groups with more than one student —
        i.e. likely-duplicate records for a teacher/admin to review and
        merge/delete manually. Respects the same classroom/stream/
        active/grade-level query-param filters as the main list, and the
        same scoping as get_queryset (a teacher only ever sees duplicates
        within their own classrooms).
        """
        from django.db.models import Count, F
        from django.db.models.functions import Lower, Trim

        by = request.query_params.get('by', 'name')
        fields = self.DUPLICATE_MATCH_FIELDS.get(by)
        if not fields:
            return Response(
                {'detail': f'Unsupported "by" value. Choose one of: {", ".join(self.DUPLICATE_MATCH_FIELDS)}'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Reuse filter_queryset so classroom/stream/is_active/grade_level
        # (and search) filters already applied on the list page carry over
        # into the duplicate search, rather than always scanning everyone.
        qs = self.filter_queryset(self.get_queryset())

        # A shared blank value isn't a duplicate — exclude rows missing
        # any of the match fields before grouping. DateField has no notion
        # of an empty string (Django raises trying to parse '' as a date),
        # so the blank-string exclude only applies to the text fields.
        for f in fields:
            if f != 'date_of_birth':
                qs = qs.exclude(**{f: ''})
            qs = qs.exclude(**{f'{f}__isnull': True})

        annotations = {}
        group_keys = []
        for f in fields:
            key = f'dupe_{f}'
            # DateField has no .strip()/lower(), so only normalize text fields.
            annotations[key] = Lower(Trim(F(f))) if f != 'date_of_birth' else F(f)
            group_keys.append(key)

        qs = qs.annotate(**annotations)
        dupe_values = (
            qs.values(*group_keys)
              .annotate(count=Count('id'))
              .filter(count__gt=1)
              .order_by('-count')
        )

        groups = []
        for row in dupe_values:
            match = {k: row[k] for k in group_keys}
            students = (
                qs.filter(**match)
                  .select_related('user', 'classroom__grade_level')
                  .order_by('user__last_name', 'user__first_name')
            )
            students_data = StudentProfileSerializer(students, many=True).data
            label_field = {'name': 'full_name', 'email': 'email', 'index_number': 'index_number',
                            'parent_phone': 'parent_phone', 'date_of_birth': 'date_of_birth'}[by]
            label = students_data[0].get(label_field, '') if students_data else ''
            groups.append({
                'key': label,
                'count': row['count'],
                'students': students_data,
            })

        return Response({'by': by, 'groups': groups})

    def create(self, request, *args, **kwargs):
        serializer = StudentCreateSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        profile = serializer.save()
        out = StudentProfileSerializer(profile)
        response_data = out.data
        if hasattr(profile, '_generated_password'):
            response_data['generated_password'] = profile._generated_password
        return Response(response_data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'])
    def bulk_delete(self, request):
        """Delete a batch of students (by id) in one call, for the
        multi-select checkboxes in the student list. Reuses get_queryset()
        so a teacher can only ever delete students in classrooms they're
        assigned to — the same scoping the list view itself is subject to."""
        student_ids = request.data.get('student_ids') or []
        if not isinstance(student_ids, list) or not student_ids:
            return Response({'detail': 'student_ids must be a non-empty list.'}, status=status.HTTP_400_BAD_REQUEST)

        qs = self.get_queryset().filter(id__in=student_ids)
        deleted_count = qs.count()
        if not deleted_count:
            return Response({'detail': 'No matching students found.'}, status=status.HTTP_404_NOT_FOUND)
        qs.delete()
        return Response({'deleted': deleted_count})

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

        # Optional default classroom, chosen from a dropdown on the import
        # screen instead of requiring every CSV row to carry a classroom_id.
        # A per-row classroom_id (if present) still takes priority, so a
        # single file can still mix classrooms when needed.
        default_classroom = None
        default_classroom_id = str(request.data.get('classroom_id', '') or '').strip()
        if default_classroom_id:
            try:
                default_classroom = allowed_classrooms.get(id=int(default_classroom_id))
            except (Classroom.DoesNotExist, ValueError):
                return Response({'detail': 'Selected classroom was not found or is not available to you.'},
                                 status=status.HTTP_400_BAD_REQUEST)

        # Optional default stream — same idea as default_classroom above. A
        # per-row stream_id/stream_name still takes priority. The stream is
        # only applied if it belongs to whichever classroom the row ends up
        # in (default or per-row); mismatches are silently skipped rather
        # than failing the whole row, since the classroom assignment is the
        # more important part of the import.
        default_stream = None
        default_stream_id = str(request.data.get('stream_id', '') or '').strip()
        if default_stream_id:
            try:
                default_stream = Stream.objects.get(id=int(default_stream_id), classroom__in=allowed_classrooms)
            except (Stream.DoesNotExist, ValueError):
                return Response({'detail': 'Selected stream was not found or is not available to you.'},
                                 status=status.HTTP_400_BAD_REQUEST)

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
                    classroom = default_classroom
                    classroom_id = row.get('classroom_id', '').strip()
                    if classroom_id:
                        try:
                            classroom = allowed_classrooms.get(id=int(classroom_id))
                        except (Classroom.DoesNotExist, ValueError):
                            pass

                    stream = default_stream if (default_stream and default_stream.classroom_id == getattr(classroom, 'id', None)) else None
                    stream_id = row.get('stream_id', '').strip()
                    stream_name = row.get('stream_name', '').strip()
                    if classroom is not None:
                        if stream_id:
                            try:
                                stream = Stream.objects.get(id=int(stream_id), classroom=classroom)
                            except (Stream.DoesNotExist, ValueError):
                                pass
                        elif stream_name:
                            stream = Stream.objects.filter(classroom=classroom, name__iexact=stream_name).first()

                    profile = StudentProfile.objects.create(
                        user=user, student_id=student_id, classroom=classroom, stream=stream,
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
        writer.writerow(['first_name', 'last_name', 'email', 'student_id', 'classroom_id', 'stream_id', 'stream_name', 'date_of_birth', 'notes'])
        writer.writerow(['Alice', 'Mensah', 'alice.mensah@school.edu', 'STU1001', '', '', 'A', '2008-05-14', ''])
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
