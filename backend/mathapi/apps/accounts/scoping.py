"""
Queryset scoping helpers — the single source of truth for data isolation.
Import these into every app that needs teacher-scoped querysets.
"""
from .models import TeacherAssignment, Subject


def get_teacher_subjects(user):
    """Return Subject queryset for the given teacher."""
    if user.role == 'super_admin':
        return Subject.objects.filter(is_active=True)
    return Subject.objects.filter(
        assignments__teacher=user,
        is_active=True,
    ).distinct()


def get_teacher_classrooms(user, subject=None, base_qs=None):
    """Return Classroom queryset for the given teacher, optionally filtered by subject.

    `base_qs` lets callers pass in a queryset with their own select_related/
    prefetch_related already applied (e.g. ClassroomViewSet.get_queryset()) so
    that filtering by teacher assignment doesn't throw away those optimizations.
    """
    from mathapi.apps.students.models import Classroom
    base = base_qs if base_qs is not None else Classroom.objects.all()
    if user.role == 'super_admin':
        return base
    qs = TeacherAssignment.objects.filter(teacher=user)
    if subject:
        qs = qs.filter(subject=subject)
    return base.filter(teacher_assignments__in=qs).distinct()


def assert_classroom_owned(user, classroom_id):
    """Raise PermissionError if the teacher does not own this classroom."""
    if user.role == 'super_admin':
        return
    owned = get_teacher_classrooms(user).filter(id=classroom_id).exists()
    if not owned:
        from rest_framework.exceptions import PermissionDenied
        raise PermissionDenied('You do not have access to this classroom.')


def scope_exams(user, base_qs=None):
    """Return a scoped Exam queryset for the given user.

    Teacher isolation rules:
    - A teacher sees ONLY exams they personally created (created_by=user),
      AND those exams must be in a subject+classroom they are assigned to.
      Filtering on both ensures a reassigned or deleted assignment
      immediately hides that exam from the teacher too.
    - Published exams from other teachers in the same classroom are NOT
      visible to teachers — teachers work in their own isolated workspace.
    - Admin (super_admin) sees every non-deleted exam unconditionally.
    - Students and parents see only published exams in their classroom(s).
    """
    from mathapi.apps.exams.models import Exam
    qs = base_qs if base_qs is not None else Exam.objects.all()
    qs = qs.filter(is_deleted=False)
    if user.role == 'super_admin':
        return qs
    if user.role == 'teacher':
        subjects = get_teacher_subjects(user)
        classrooms = get_teacher_classrooms(user)
        # Only the teacher's OWN exams, scoped to their assigned classrooms
        # and subjects — prevents cross-teacher exam leakage in shared classes.
        return qs.filter(
            created_by=user,
            subject__in=subjects,
            classrooms__in=classrooms,
        ).distinct()
    if user.role == 'student':
        try:
            profile = user.student_profile
            return qs.filter(classrooms=profile.classroom, is_published=True)
        except Exception:
            return qs.none()
    if user.role == 'parent':
        try:
            student_classrooms = user.linked_students.values_list('student__classroom', flat=True)
            return qs.filter(classrooms__in=student_classrooms, is_published=True)
        except Exception:
            return qs.none()
    return qs.none()


def scope_quizzes(user, base_qs=None):
    """Return a scoped DailyQuiz queryset for the given user.

    Mirrors scope_exams()'s isolation rules exactly (own-created-only for
    teachers, full access for admin, own-classroom-only for
    student/parent) — daily quizzes have no draft/published gate the way
    Exam does, so a student/parent sees every quiz recorded for their
    classroom as soon as it exists.
    """
    from mathapi.apps.quizzes.models import DailyQuiz
    qs = base_qs if base_qs is not None else DailyQuiz.objects.all()
    qs = qs.filter(is_deleted=False)
    if user.role == 'super_admin':
        return qs
    if user.role == 'teacher':
        subjects = get_teacher_subjects(user)
        classrooms = get_teacher_classrooms(user)
        return qs.filter(created_by=user, subject__in=subjects, classroom__in=classrooms)
    if user.role == 'student':
        try:
            profile = user.student_profile
            return qs.filter(classroom=profile.classroom)
        except Exception:
            return qs.none()
    if user.role == 'parent':
        try:
            student_classrooms = user.linked_students.values_list('student__classroom', flat=True)
            return qs.filter(classroom__in=student_classrooms)
        except Exception:
            return qs.none()
    return qs.none()


def scope_tournaments(user, base_qs=None):
    """Return a scoped Tournament queryset for the given user.

    Mirrors scope_quizzes()'s isolation rules: teachers see tournaments they
    created within their assigned classrooms, students/parents see
    tournaments run in their own classroom (draft ones stay hidden from
    them — nothing to see until a teacher opens registration).
    """
    from mathapi.apps.tournaments.models import Tournament
    qs = base_qs if base_qs is not None else Tournament.objects.all()
    if user.role == 'super_admin':
        return qs
    if user.role == 'teacher':
        classrooms = get_teacher_classrooms(user)
        return qs.filter(created_by=user, classroom__in=classrooms)
    if user.role == 'student':
        try:
            profile = user.student_profile
            return qs.filter(classroom=profile.classroom).exclude(status=Tournament.Status.DRAFT)
        except Exception:
            return qs.none()
    if user.role == 'parent':
        try:
            student_classrooms = user.linked_students.values_list('student__classroom', flat=True)
            return qs.filter(classroom__in=student_classrooms).exclude(status=Tournament.Status.DRAFT)
        except Exception:
            return qs.none()
    return qs.none()
