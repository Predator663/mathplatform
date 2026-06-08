from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import get_user_model

User = get_user_model()


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['email'] = user.email
        token['role'] = user.role
        token['full_name'] = user.get_full_name()
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data['user'] = UserSerializer(self.user).data
        return data


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'full_name',
                  'role', 'is_active', 'date_joined', 'phone', 'avatar']
        read_only_fields = ['id', 'email', 'role', 'date_joined']

    def get_full_name(self, obj):
        return obj.get_full_name()


class UserCreateSerializer(serializers.ModelSerializer):
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
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['confirm_password']:
            raise serializers.ValidationError({'confirm_password': 'Passwords do not match.'})
        return attrs


def _get_db_columns(table='site_settings'):
    """Return set of column names that currently exist in the DB table."""
    try:
        from django.db import connection
        with connection.cursor() as cursor:
            cols = connection.introspection.get_table_description(cursor, table)
        return {c.name for c in cols}
    except Exception:
        return set()


class SiteSettingsSerializer(serializers.ModelSerializer):
    # Login page fields — declared explicitly so they're optional (required=False)
    # and don't blow up if the DB column doesn't exist yet.
    login_tagline = serializers.CharField(max_length=200, required=False, allow_blank=True, default='Student Performance Analytics')
    login_welcome = serializers.CharField(max_length=200, required=False, allow_blank=True, default='Sign in to your account')
    login_bg_gradient = serializers.BooleanField(required=False, default=True)

    class Meta:
        from .models import SiteSettings
        model = SiteSettings
        fields = [
            'platform_name', 'platform_subtitle', 'logo_url',
            'logo_letter', 'favicon_url', 'footer_text',
            'login_tagline', 'login_welcome', 'login_bg_gradient',
            'page_settings', 'updated_at',
        ]
        read_only_fields = ['updated_at']

    def to_representation(self, instance):
        """Safe read — inject defaults for any column that doesn't exist in the DB yet."""
        existing = _get_db_columns()
        all_defaults = {
            'platform_name': 'MathPlatform',
            'platform_subtitle': 'Tanzania',
            'logo_url': '',
            'logo_letter': 'Σ',
            'favicon_url': '',
            'footer_text': '© 2025 MathPlatform · Built for Tanzanian Secondary Schools',
            'login_tagline': 'Student Performance Analytics',
            'login_welcome': 'Sign in to your account',
            'login_bg_gradient': True,
            'page_settings': {},
        }
        patched = []
        for field, default in all_defaults.items():
            if field not in existing and not hasattr(instance, '_patched_' + field):
                setattr(instance, field, default)
                patched.append(field)
        result = super().to_representation(instance)
        for field in patched:
            try:
                delattr(instance, field)
            except AttributeError:
                pass
        return result

    def save(self, **kwargs):
        """Strip any field whose DB column doesn't exist yet."""
        existing = _get_db_columns()
        # Keep only fields that exist as DB columns (page_settings is a JSONField — always safe)
        for field in list(self.validated_data.keys()):
            if field not in existing:
                self.validated_data.pop(field, None)
        return super().save(**kwargs)
