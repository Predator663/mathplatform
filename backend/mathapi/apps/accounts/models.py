from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Email is required')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', User.Role.SUPER_ADMIN)
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    class Role(models.TextChoices):
        SUPER_ADMIN = 'super_admin', 'Super Admin'
        TEACHER = 'teacher', 'Teacher'
        STUDENT = 'student', 'Student'
        PARENT = 'parent', 'Parent/Guardian'

    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.STUDENT)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)
    last_login = models.DateTimeField(null=True, blank=True)
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    phone = models.CharField(max_length=20, blank=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    objects = UserManager()

    class Meta:
        db_table = 'users'
        verbose_name = 'User'
        verbose_name_plural = 'Users'

    def __str__(self):
        return f'{self.get_full_name()} ({self.email})'

    def get_full_name(self):
        return f'{self.first_name} {self.last_name}'.strip()

    @property
    def is_teacher(self):
        return self.role == self.Role.TEACHER

    @property
    def is_student_role(self):
        return self.role == self.Role.STUDENT

    @property
    def is_admin(self):
        return self.role == self.Role.SUPER_ADMIN


class Subject(models.Model):
    """A school subject — Mathematics, Physics, Geography, etc."""
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=10, unique=True)
    color = models.CharField(max_length=7, default='#6366f1')
    icon = models.CharField(max_length=50, blank=True, help_text='Lucide icon name, e.g. calculator')
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'subjects'
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.code})'


class TeacherAssignment(models.Model):
    """Links a teacher (or admin acting as teacher) to a classroom for a specific subject."""
    teacher = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='assignments',
    )
    classroom = models.ForeignKey(
        'students.Classroom', on_delete=models.CASCADE,
        related_name='teacher_assignments',
    )
    subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE, related_name='assignments',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'teacher_assignments'
        unique_together = [('teacher', 'classroom', 'subject')]

    def __str__(self):
        return f'{self.teacher.get_full_name()} | {self.classroom} | {self.subject.code}'


class AuditLog(models.Model):
    class Action(models.TextChoices):
        CREATE = 'create', 'Create'
        UPDATE = 'update', 'Update'
        DELETE = 'delete', 'Delete'
        LOGIN = 'login', 'Login'
        LOGOUT = 'logout', 'Logout'

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='audit_logs')
    action = models.CharField(max_length=20, choices=Action.choices)
    model_name = models.CharField(max_length=100)
    object_id = models.CharField(max_length=50, blank=True)
    description = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'audit_logs'
        ordering = ['-timestamp']

    def __str__(self):
        return f'{self.user} - {self.action} - {self.model_name} at {self.timestamp}'


class SiteSettings(models.Model):
    """Singleton model for platform-wide configuration."""
    platform_name = models.CharField(max_length=100, default='MathPlatform')
    platform_subtitle = models.CharField(max_length=100, default='Tanzania', blank=True)
    logo_url = models.URLField(blank=True, help_text='URL to platform logo image')
    logo_letter = models.CharField(max_length=3, default='Σ', help_text='Fallback letter(s) for logo icon')
    favicon_url = models.URLField(blank=True, help_text='URL to favicon (.ico, .png, or .svg)')
    footer_text = models.TextField(
        default='© 2025 MathPlatform · Built for Tanzanian Secondary Schools',
        blank=True,
    )
    login_tagline = models.CharField(
        max_length=200, default='Student Performance Analytics', blank=True,
        help_text='Tagline shown under the platform name on the login page',
    )
    login_welcome = models.CharField(
        max_length=200, default='Sign in to your account', blank=True,
        help_text='Heading shown above the login form',
    )
    login_bg_gradient = models.BooleanField(
        default=True, help_text='Show ambient glow gradient on login page background',
    )
    page_settings = models.JSONField(default=dict, blank=True)

    privacy_policy = models.TextField(
        default='', blank=True,
        help_text='Privacy Policy page content (plain text / markdown-ish, line breaks preserved)',
    )
    terms_of_use = models.TextField(
        default='', blank=True,
        help_text='Terms of Use page content (plain text / markdown-ish, line breaks preserved)',
    )
    about_me = models.TextField(
        default='', blank=True,
        help_text='About page content (plain text / markdown-ish, line breaks preserved)',
    )

    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+'
    )

    class Meta:
        db_table = 'site_settings'
        verbose_name = 'Site Settings'
        verbose_name_plural = 'Site Settings'

    def __str__(self):
        return self.platform_name

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def get_page(self, page_key: str) -> dict:
        defaults = {'enabled': True, 'page_size': 20}
        return {**defaults, **self.page_settings.get(page_key, {})}
