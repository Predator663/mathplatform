import csv
import io
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from .models import GradeLevel, Classroom, StudentProfile, ParentStudentLink
from .serializers import (
    GradeLevelSerializer, ClassroomSerializer,
    StudentProfileSerializer, StudentCreateSerializer, ParentStudentLinkSerializer
)
from django.contrib.auth import get_user_model
import secrets

User = get_user_model()


class GradeLevelViewSet(viewsets.ModelViewSet):
    queryset = GradeLevel.objects.all()
    serializer_class = GradeLevelSerializer
    permission_classes = [permissions.IsAuthenticated]


class ClassroomViewSet(viewsets.ModelViewSet):
    serializer_class = ClassroomSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['academic_year', 'is_active', 'grade_level']
    search_fields = ['name']
    ordering_fields = ['name', 'academic_year']

    def get_queryset(self):
        user = self.request.user
        qs = Classroom.objects.select_related('grade_level').prefetch_related('teachers')
        if user.role == 'teacher':
            return qs.filter(teachers=user)
        return qs.all()

    @action(detail=True, methods=['get'])
    def students(self, request, pk=None):
        classroom = self.get_object()
        students = StudentProfile.objects.filter(
            classroom=classroom, is_active=True
        ).select_related('user')
        serializer = StudentProfileSerializer(students, many=True)
        return Response(serializer.data)


class StudentProfileViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['classroom', 'is_active', 'classroom__academic_year']
    search_fields = ['user__first_name', 'user__last_name', 'user__email', 'student_id']
    ordering_fields = ['user__last_name', 'student_id', 'enrollment_date']

    def get_queryset(self):
        user = self.request.user
        qs = StudentProfile.objects.select_related('user', 'classroom__grade_level')
        if user.role == 'student':
            return qs.filter(user=user)
        if user.role == 'parent':
            return qs.filter(parent_links__parent=user)
        if user.role == 'teacher':
            return qs.filter(classroom__teachers=user)
        return qs.all()

    def get_serializer_class(self):
        if self.action == 'create':
            return StudentCreateSerializer
        return StudentProfileSerializer

    def create(self, request, *args, **kwargs):
        serializer = StudentCreateSerializer(data=request.data)
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
        summary = get_student_summary(student.id)
        return Response(summary)

    @action(detail=False, methods=['post'], parser_classes=[MultiPartParser, FormParser])
    def bulk_import(self, request):
        """
        Bulk import students from CSV.
        Expected columns: first_name, last_name, email, student_id, classroom_id (optional),
                          date_of_birth (optional, YYYY-MM-DD)
        """
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
            return Response(
                {'detail': f'Missing columns: {", ".join(missing_cols)}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        created = []
        skipped = []
        errors = []

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
                password = secrets.token_urlsafe(10)
                user = User.objects.create_user(
                    email=email,
                    first_name=row.get('first_name', ''),
                    last_name=row.get('last_name', ''),
                    role='student',
                    password=password,
                )
                classroom = None
                classroom_id = row.get('classroom_id', '').strip()
                if classroom_id:
                    try:
                        classroom = Classroom.objects.get(id=int(classroom_id))
                    except (Classroom.DoesNotExist, ValueError):
                        pass

                dob = row.get('date_of_birth', '').strip() or None

                profile = StudentProfile.objects.create(
                    user=user,
                    student_id=student_id,
                    classroom=classroom,
                    date_of_birth=dob,
                    notes=row.get('notes', ''),
                )
                created.append({
                    'row': i,
                    'student_id': student_id,
                    'name': user.get_full_name(),
                    'email': email,
                    'generated_password': password,
                })
            except Exception as e:
                errors.append({'row': i, 'error': str(e)})

        return Response({
            'created': len(created),
            'skipped': len(skipped),
            'errors_count': len(errors),
            'students': created,
            'skipped_detail': skipped,
            'errors': errors,
        }, status=status.HTTP_207_MULTI_STATUS if (skipped or errors) else status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'])
    def import_template(self, request):
        """Download a CSV template for bulk student import."""
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['first_name', 'last_name', 'email', 'student_id', 'classroom_id', 'date_of_birth', 'notes'])
        writer.writerow(['Alice', 'Mensah', 'alice.mensah@school.edu', 'STU1001', '1', '2008-05-14', ''])
        writer.writerow(['Benjamin', 'Osei', 'ben.osei@school.edu', 'STU1002', '1', '2008-09-22', ''])
        from django.http import HttpResponse
        response = HttpResponse(output.getvalue(), content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="student_import_template.csv"'
        return response


class ParentStudentLinkViewSet(viewsets.ModelViewSet):
    queryset = ParentStudentLink.objects.select_related('parent', 'student__user')
    serializer_class = ParentStudentLinkSerializer
    permission_classes = [permissions.IsAuthenticated]
