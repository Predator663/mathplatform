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
    necta_exam             = serializers.CharField(source='grade_level.necta_exam', read_only=True)
    math_subject           = serializers.CharField(source='grade_level.math_subject', read_only=True)

    class Meta:
        model  = Classroom
        fields = [
            'id', 'name', 'grade_level', 'grade_level_name', 'grade_level_short',
            'education_level', 'education_level_display', 'stream', 'stream_display',
            'academic_year', 'teachers', 'teacher_names', 'is_active',
            'student_count', 'necta_exam', 'math_subject', 'created_at',
        ]

    def get_teacher_names(self, obj):
        return [t.get_full_name() for t in obj.teachers.all()]


class StudentProfileSerializer(serializers.ModelSerializer):
    full_name      = serializers.ReadOnlyField()
    email          = serializers.ReadOnlyField()
    classroom_name = serializers.CharField(source='classroom.__str__', read_only=True)
    first_name     = serializers.CharField(source='user.first_name', read_only=True)
    last_name      = serializers.CharField(source='user.last_name', read_only=True)
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
