from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import GradeLevel, Classroom, StudentProfile, ParentStudentLink

User = get_user_model()


class GradeLevelSerializer(serializers.ModelSerializer):
    education_level_display = serializers.CharField(
        source='get_education_level_display', read_only=True)
    class Meta:
        model  = GradeLevel
        fields = ['id', 'name', 'short_name', 'education_level',
                  'education_level_display', 'order', 'necta_exam', 'math_subject']


class ClassroomSerializer(serializers.ModelSerializer):
    grade_level_name       = serializers.CharField(source='grade_level.name', read_only=True)
    grade_level_short      = serializers.CharField(source='grade_level.short_name', read_only=True)
    education_level        = serializers.CharField(source='grade_level.education_level', read_only=True)
    education_level_display = serializers.CharField(
        source='grade_level.get_education_level_display', read_only=True)
    stream_display         = serializers.CharField(source='get_stream_display', read_only=True)
    student_count          = serializers.ReadOnlyField()
    teacher_names          = serializers.SerializerMethodField()
    teacher_assignments    = serializers.SerializerMethodField()
    necta_exam             = serializers.CharField(source='grade_level.necta_exam', read_only=True)
    math_subject           = serializers.CharField(source='grade_level.math_subject', read_only=True)

    class Meta:
        model  = Classroom
        fields = [
            'id', 'name', 'grade_level', 'grade_level_name', 'grade_level_short',
            'education_level', 'education_level_display', 'stream', 'stream_display',
            'academic_year', 'teacher_names', 'teacher_assignments', 'is_active',
            'student_count', 'necta_exam', 'math_subject', 'created_at',
        ]

    def get_teacher_names(self, obj):
        seen = set()
        names = []
        for ta in obj.teacher_assignments.select_related('teacher').all():
            if ta.teacher_id not in seen:
                seen.add(ta.teacher_id)
                names.append(ta.teacher.get_full_name())
        return names

    def get_teacher_assignments(self, obj):
        return [
            {
                'teacher_id': ta.teacher_id,
                'teacher_name': ta.teacher.get_full_name(),
                'subject_id': ta.subject_id,
                'subject_name': ta.subject.name,
                'subject_code': ta.subject.code,
            }
            for ta in obj.teacher_assignments.select_related('teacher', 'subject').all()
        ]


class StudentProfileSerializer(serializers.ModelSerializer):
    full_name      = serializers.ReadOnlyField()
    email          = serializers.ReadOnlyField()
    classroom_name = serializers.CharField(source='classroom.__str__', read_only=True)
    # NOTE: these were previously read_only=True. That meant editing a
    # student's name in the UI would PATCH successfully (200 OK, "Student
    # updated" toast) but silently drop first_name/last_name from
    # validated_data — DRF excludes read_only fields from input entirely —
    # so the name itself never actually changed. See update() below, which
    # pushes the nested `user.first_name` / `user.last_name` values onto
    # the related User row (ModelSerializer's default update() can't do
    # this on its own since these live on a different model).
    first_name     = serializers.CharField(source='user.first_name')
    last_name      = serializers.CharField(source='user.last_name')
    grade_level    = serializers.SerializerMethodField()
    education_level = serializers.SerializerMethodField()

    class Meta:
        model  = StudentProfile
        fields = [
            'id', 'student_id', 'full_name', 'first_name', 'last_name', 'email',
            'classroom', 'classroom_name', 'grade_level', 'education_level',
            'date_of_birth', 'enrollment_date', 'is_active', 'notes',
            'index_number', 'parent_name', 'parent_phone', 'district', 'region',
        ]

    def get_grade_level(self, obj):
        if obj.classroom and obj.classroom.grade_level:
            return obj.classroom.grade_level.name
        return None

    def get_education_level(self, obj):
        if obj.classroom and obj.classroom.grade_level:
            return obj.classroom.grade_level.education_level
        return None

    def update(self, instance, validated_data):
        # `first_name`/`last_name` use a dotted source (user.first_name),
        # so DRF nests them under a 'user' key in validated_data rather
        # than setting them directly on the StudentProfile instance.
        user_data = validated_data.pop('user', None)
        instance = super().update(instance, validated_data)
        if user_data:
            user = instance.user
            for attr, value in user_data.items():
                setattr(user, attr, value)
            user.save(update_fields=list(user_data.keys()))
        return instance


class StudentCreateSerializer(serializers.Serializer):
    email         = serializers.EmailField()
    first_name    = serializers.CharField(max_length=100)
    last_name     = serializers.CharField(max_length=100)
    student_id    = serializers.CharField(max_length=20)
    classroom     = serializers.PrimaryKeyRelatedField(
        queryset=Classroom.objects.all(), required=False, allow_null=True)
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    notes         = serializers.CharField(required=False, allow_blank=True)
    index_number  = serializers.CharField(required=False, allow_blank=True)
    parent_name   = serializers.CharField(required=False, allow_blank=True)
    parent_phone  = serializers.CharField(required=False, allow_blank=True)
    district      = serializers.CharField(required=False, allow_blank=True)
    region        = serializers.CharField(required=False, allow_blank=True)

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError('A user with this email already exists.')
        return value

    def validate_student_id(self, value):
        if StudentProfile.objects.filter(student_id=value).exists():
            raise serializers.ValidationError('This student ID is already in use.')
        return value

    def validate_classroom(self, value):
        # Mirrors the allowed_classrooms restriction in
        # StudentProfileViewSet.bulk_import — without this, a teacher could
        # place a single new student into any classroom in the school via
        # this non-bulk endpoint, even one they don't teach.
        request = self.context.get('request')
        if value is not None and request and request.user.role == 'teacher':
            from mathapi.apps.accounts.scoping import get_teacher_classrooms
            if not get_teacher_classrooms(request.user).filter(id=value.id).exists():
                raise serializers.ValidationError(
                    'You do not have access to this classroom.'
                )
        return value

    def create(self, validated_data):
        import secrets
        user_data = {
            'email':      validated_data.pop('email'),
            'first_name': validated_data.pop('first_name'),
            'last_name':  validated_data.pop('last_name'),
            'role':       'student',
        }
        password = secrets.token_urlsafe(12)
        user = User.objects.create_user(password=password, **user_data)
        profile = StudentProfile.objects.create(user=user, **validated_data)
        profile._generated_password = password
        return profile


class ParentStudentLinkSerializer(serializers.ModelSerializer):
    parent_name  = serializers.CharField(source='parent.get_full_name', read_only=True)
    student_name = serializers.CharField(source='student.full_name', read_only=True)

    class Meta:
        model  = ParentStudentLink
        fields = '__all__'
