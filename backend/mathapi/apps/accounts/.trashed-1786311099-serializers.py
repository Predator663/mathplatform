from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Subject, TeacherAssignment, AuditLog, SiteSettings

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.ReadOnlyField(source='get_full_name')

    class Meta:
        model = User
        fields = [
            'id', 'email', 'first_name', 'last_name', 'full_name',
            'role', 'is_active', 'date_joined', 'phone', 'avatar',
        ]
        read_only_fields = ['date_joined']


class MeSerializer(UserSerializer):
    """Self-service profile editing, used only by MeView.

    Identical to UserSerializer except 'role' and 'is_active' are read-only.
    UserSerializer is also used by UserViewSet, where writing those fields is
    safe because create/update/partial_update/destroy are gated to
    IsAdminRole there. MeView has no such gate (any authenticated user can
    PATCH their own record), so without this, a regular user could promote
    themselves by sending {"role": "super_admin"} to /me.
    """
    class Meta(UserSerializer.Meta):
        read_only_fields = UserSerializer.Meta.read_only_fields + ['role', 'is_active']


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name', 'role', 'phone', 'password', 'confirm_password']

    def validate(self, attrs):
        if attrs['password'] != attrs.pop('confirm_password'):
            raise serializers.ValidationError({'confirm_password': 'Passwords do not match.'})
        return attrs

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField()
    new_password = serializers.CharField(min_length=8)

    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError('Current password is incorrect.')
        return value


# ── Subject ──────────────────────────────────────────────────────────────────

class SubjectSerializer(serializers.ModelSerializer):
    teacher_count = serializers.SerializerMethodField()
    exam_count = serializers.SerializerMethodField()

    class Meta:
        model = Subject
        fields = ['id', 'name', 'code', 'color', 'icon', 'is_active', 'teacher_count', 'exam_count']

    def get_teacher_count(self, obj):
        return obj.assignments.values('teacher').distinct().count()

    def get_exam_count(self, obj):
        return obj.exams.filter(is_deleted=False).count() if hasattr(obj, 'exams') else 0


class SubjectLightSerializer(serializers.ModelSerializer):
    """Minimal subject info for embedding in other serializers."""
    class Meta:
        model = Subject
        fields = ['id', 'name', 'code', 'color', 'icon']


# ── TeacherAssignment ─────────────────────────────────────────────────────────

class TeacherAssignmentSerializer(serializers.ModelSerializer):
    teacher_name = serializers.CharField(source='teacher.get_full_name', read_only=True)
    teacher_email = serializers.CharField(source='teacher.email', read_only=True)
    classroom_name = serializers.SerializerMethodField()
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    subject_code = serializers.CharField(source='subject.code', read_only=True)
    subject_color = serializers.CharField(source='subject.color', read_only=True)

    class Meta:
        model = TeacherAssignment
        fields = [
            'id', 'teacher', 'teacher_name', 'teacher_email',
            'classroom', 'classroom_name',
            'subject', 'subject_name', 'subject_code', 'subject_color',
            'created_at',
        ]
        read_only_fields = ['created_at']

    def get_classroom_name(self, obj):
        return str(obj.classroom)

    def validate(self, attrs):
        teacher = attrs.get('teacher')
        if teacher and teacher.role not in ('teacher', 'super_admin'):
            raise serializers.ValidationError(
                {'teacher': 'Only users with the Teacher or Admin role can be assigned as teachers. Students and parents cannot be assigned.'}
            )
        return attrs


# ── AuditLog ──────────────────────────────────────────────────────────────────

class AuditLogSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    action_display = serializers.CharField(source='get_action_display', read_only=True)

    class Meta:
        model = AuditLog
        fields = [
            'id', 'user', 'user_name', 'user_email',
            'action', 'action_display', 'model_name', 'object_id',
            'description', 'ip_address', 'timestamp',
        ]
        read_only_fields = fields


# ── SiteSettings ──────────────────────────────────────────────────────────────

class SiteSettingsSerializer(serializers.ModelSerializer):
    # Read-only convenience field: the fully-merged view (defaults +
    # overrides) so the admin Settings UI always has every resource/action
    # key to render toggles for, even before any override has been saved.
    teacher_permissions_resolved = serializers.SerializerMethodField()

    class Meta:
        model = SiteSettings
        fields = [
            'platform_name', 'platform_subtitle', 'logo_url',
            'logo_letter', 'favicon_url', 'pwa_icon_url', 'footer_text',
            'login_tagline', 'login_welcome', 'login_bg_gradient',
            'page_settings', 'privacy_policy', 'terms_of_use', 'about_me',
            'teacher_permissions', 'teacher_permissions_resolved',
            'updated_at',
        ]
        read_only_fields = ['updated_at']

    def get_teacher_permissions_resolved(self, obj):
        return obj.resolved_teacher_permissions()
