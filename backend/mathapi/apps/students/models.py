from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class EducationLevel(models.TextChoices):
    PRE_PRIMARY  = 'pre_primary',  'Pre-Primary (Awali)'
    PRIMARY      = 'primary',      'Primary (Msingi)'
    O_LEVEL      = 'o_level',      'O-Level (Form 1–4)'
    A_LEVEL      = 'a_level',      'A-Level (Form 5–6)'
    TECHNICAL    = 'technical',    'Technical / VETA'


class GradeLevel(models.Model):
    """
    Tanzania curriculum grade levels.
    Primary: Standard 1–7
    O-Level: Form 1–4
    A-Level: Form 5–6
    """
    name            = models.CharField(max_length=50, unique=True)
    short_name      = models.CharField(max_length=20, blank=True)   # e.g. "Std 7", "Form 4"
    education_level = models.CharField(max_length=20, choices=EducationLevel.choices,
                                        default=EducationLevel.O_LEVEL)
    order           = models.PositiveIntegerField(default=0)
    necta_exam      = models.CharField(max_length=50, blank=True)   # e.g. "PSLE", "CSEE", "ACSEE"
    math_subject    = models.CharField(max_length=100, blank=True,
                                        default='Mathematics')       # e.g. "Hisabati", "Advanced Mathematics"

    class Meta:
        db_table = 'grade_levels'
        ordering = ['order']

    def __str__(self):
        return self.name


class Classroom(models.Model):
    """
    A class in a Tanzania school.
    Name examples: "Form 2A", "Standard 5 Blue", "Form 4 Science"
    Stream: Science / Arts / Commerce / General (A-Level streams)
    """
    class Stream(models.TextChoices):
        GENERAL    = 'general',    'General'
        SCIENCE    = 'science',    'Science'
        ARTS       = 'arts',       'Arts'
        COMMERCE   = 'commerce',   'Commerce'
        TECHNICAL  = 'technical',  'Technical'

    name          = models.CharField(max_length=100)
    grade_level   = models.ForeignKey(GradeLevel, on_delete=models.CASCADE,
                                       related_name='classrooms')
    stream        = models.CharField(max_length=20, choices=Stream.choices,
                                      default=Stream.GENERAL, blank=True)
    academic_year = models.CharField(max_length=9)   # e.g. "2024"
    teachers      = models.ManyToManyField(User, related_name='classrooms', blank=True,
                                            limit_choices_to={'role': 'teacher'})
    is_active     = models.BooleanField(default=True)
    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'classrooms'
        unique_together = ['name', 'grade_level', 'academic_year']
        ordering = ['grade_level__order', 'name']

    def __str__(self):
        stream = f' ({self.get_stream_display()})' if self.stream != 'general' else ''
        return f'{self.name}{stream} — {self.academic_year}'

    @property
    def student_count(self):
        # Use the annotated value when the queryset provided one (see
        # ClassroomViewSet.get_queryset's .annotate(active_student_count=...))
        # to avoid one extra COUNT query per classroom on list endpoints.
        if hasattr(self, 'active_student_count'):
            return self.active_student_count
        return self.student_profiles.filter(is_active=True).count()

    @property
    def education_level(self):
        return self.grade_level.education_level


class StudentProfile(models.Model):
    user            = models.OneToOneField(User, on_delete=models.CASCADE,
                                            related_name='student_profile')
    student_id      = models.CharField(max_length=20, unique=True)
    classroom       = models.ForeignKey(Classroom, on_delete=models.SET_NULL, null=True,
                                         related_name='student_profiles')
    date_of_birth   = models.DateField(null=True, blank=True)
    enrollment_date = models.DateField(auto_now_add=True)
    is_active       = models.BooleanField(default=True)
    notes           = models.TextField(blank=True)

    # Tanzania-specific
    index_number    = models.CharField(max_length=30, blank=True,
                                        help_text='NECTA examination index number')
    parent_name     = models.CharField(max_length=200, blank=True)
    parent_phone    = models.CharField(max_length=20, blank=True)
    district        = models.CharField(max_length=100, blank=True)
    region          = models.CharField(max_length=100, blank=True)

    class Meta:
        db_table = 'student_profiles'
        ordering = ['user__last_name', 'user__first_name']

    def __str__(self):
        return f'{self.user.get_full_name()} ({self.student_id})'

    @property
    def full_name(self):
        return self.user.get_full_name()

    @property
    def email(self):
        return self.user.email


class ParentStudentLink(models.Model):
    parent       = models.ForeignKey(User, on_delete=models.CASCADE,
                                      related_name='linked_students',
                                      limit_choices_to={'role': 'parent'})
    student      = models.ForeignKey(StudentProfile, on_delete=models.CASCADE,
                                      related_name='parent_links')
    relationship = models.CharField(max_length=50, default='Parent')
    is_primary   = models.BooleanField(default=False)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'parent_student_links'
        unique_together = ['parent', 'student']

    def __str__(self):
        return f'{self.parent.get_full_name()} → {self.student.full_name}'
