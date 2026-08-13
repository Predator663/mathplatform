"""
Tests for the student comparison feature (analytics.comparison_services +
the StudentComparisonView/StudentComparisonPDFView API views).
Run with: python manage.py test mathapi.apps.analytics.test_comparison -v 2
"""
import datetime
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model

from mathapi.apps.accounts.models import Subject, TeacherAssignment
from mathapi.apps.students.models import GradeLevel, Classroom, StudentProfile, ParentStudentLink
from mathapi.apps.exams.models import Exam, ExamScore, MathTopic, TopicScore
from . import comparison_services

User = get_user_model()


def make_exam(subject, classroom, date, **extra):
    defaults = dict(
        exam_type='monthly_test', term='term_1', academic_year='2026',
        max_score=100, passing_score=30, is_published=True,
    )
    defaults.update(extra)
    exam = Exam.objects.create(title=f'Exam {date}', exam_date=date, subject=subject, **defaults)
    exam.classrooms.add(classroom)
    return exam


class ComparisonServiceTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.subject = Subject.objects.create(name='Compare Maths', code='CMPM')
        cls.grade = GradeLevel.objects.create(name='Form 3', short_name='F3', education_level='secondary', order=3)
        cls.classroom = Classroom.objects.create(name='3C', grade_level=cls.grade, stream='general', academic_year='2026')

        cls.student_a = StudentProfile.objects.create(
            user=User.objects.create_user(email='cmp_a@test.tz', password='x', role='student'),
            student_id='CMPA', classroom=cls.classroom,
        )
        cls.student_b = StudentProfile.objects.create(
            user=User.objects.create_user(email='cmp_b@test.tz', password='x', role='student'),
            student_id='CMPB', classroom=cls.classroom,
        )

        # Student A: improving trajectory 40 -> 80
        for i, score in enumerate([40, 60, 80]):
            exam = make_exam(cls.subject, cls.classroom, datetime.date(2026, 1, i + 1))
            ExamScore.objects.create(exam=exam, student=cls.student_a, score=score)

        # Student B: flat at 50
        for i, score in enumerate([50, 50]):
            exam = make_exam(cls.subject, cls.classroom, datetime.date(2026, 2, i + 1))
            ExamScore.objects.create(exam=exam, student=cls.student_b, score=score)

    def test_growth_computed_from_first_to_last_exam(self):
        profile = comparison_services.get_student_comparison_profile(self.student_a.id)
        self.assertEqual(profile['growth']['first_pct'], 40.0)
        self.assertEqual(profile['growth']['last_pct'], 80.0)
        self.assertEqual(profile['growth']['delta'], 40.0)

    def test_growth_none_with_fewer_than_two_exams(self):
        lonely = StudentProfile.objects.create(
            user=User.objects.create_user(email='cmp_lonely@test.tz', password='x', role='student'),
            student_id='CMPL', classroom=self.classroom,
        )
        exam = make_exam(self.subject, self.classroom, datetime.date(2026, 3, 1))
        ExamScore.objects.create(exam=exam, student=lonely, score=70)
        profile = comparison_services.get_student_comparison_profile(lonely.id)
        self.assertIsNone(profile['growth']['delta'])

    def test_missing_student_returns_none_profile(self):
        profile = comparison_services.get_student_comparison_profile(999999)
        self.assertIsNone(profile)

    def test_get_students_comparison_preserves_order_and_flags_missing(self):
        result = comparison_services.get_students_comparison([self.student_b.id, self.student_a.id, 999999])
        self.assertEqual([p['student_id'] for p in result['students']], [self.student_b.id, self.student_a.id])
        self.assertEqual(result['missing_ids'], [999999])

    def test_comparison_includes_summary_and_topics(self):
        result = comparison_services.get_students_comparison([self.student_a.id, self.student_b.id])
        for profile in result['students']:
            self.assertIn('summary', profile)
            self.assertIn('timeline', profile)
            self.assertIn('topics', profile)


class ComparisonViewScopingTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.subject = Subject.objects.create(name='Scope Compare Maths', code='SCMP')
        cls.grade = GradeLevel.objects.create(name='Form 2', short_name='F2', education_level='secondary', order=2)
        cls.classroom_a = Classroom.objects.create(name='2G', grade_level=cls.grade, stream='general', academic_year='2026')
        cls.classroom_b = Classroom.objects.create(name='2H', grade_level=cls.grade, stream='general', academic_year='2026')

        cls.admin = User.objects.create_user(email='sc_admin@test.tz', password='x', role='super_admin')
        cls.teacher_a = User.objects.create_user(email='sc_teacher_a@test.tz', password='x', role='teacher')
        TeacherAssignment.objects.create(teacher=cls.teacher_a, subject=cls.subject, classroom=cls.classroom_a)

        cls.student_in_a = StudentProfile.objects.create(
            user=User.objects.create_user(email='sc_stu_a@test.tz', password='x', role='student'),
            student_id='SCA', classroom=cls.classroom_a,
        )
        cls.student_in_a2 = StudentProfile.objects.create(
            user=User.objects.create_user(email='sc_stu_a2@test.tz', password='x', role='student'),
            student_id='SCA2', classroom=cls.classroom_a,
        )
        cls.student_in_b = StudentProfile.objects.create(
            user=User.objects.create_user(email='sc_stu_b@test.tz', password='x', role='student'),
            student_id='SCB', classroom=cls.classroom_b,
        )

        for c, students in [(cls.classroom_a, [cls.student_in_a, cls.student_in_a2]), (cls.classroom_b, [cls.student_in_b])]:
            for s in students:
                for i, score in enumerate([50, 60]):
                    exam = make_exam(cls.subject, c, datetime.date(2026, 1, i + 1))
                    ExamScore.objects.create(exam=exam, student=s, score=score)

    def test_teacher_can_compare_two_students_in_own_classroom(self):
        self.client.force_authenticate(self.teacher_a)
        resp = self.client.get('/api/analytics/students/compare/', {
            'student_ids': f'{self.student_in_a.id},{self.student_in_a2.id}',
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data['students']), 2)

    def test_teacher_blocked_comparing_student_outside_scope(self):
        self.client.force_authenticate(self.teacher_a)
        resp = self.client.get('/api/analytics/students/compare/', {
            'student_ids': f'{self.student_in_a.id},{self.student_in_b.id}',
        })
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_compare_across_classrooms(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.get('/api/analytics/students/compare/', {
            'student_ids': f'{self.student_in_a.id},{self.student_in_b.id}',
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_single_student_id_rejected(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.get('/api/analytics/students/compare/', {'student_ids': str(self.student_in_a.id)})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_too_many_students_rejected(self):
        self.client.force_authenticate(self.admin)
        ids = ','.join(str(i) for i in range(1, 8))
        resp = self.client.get('/api/analytics/students/compare/', {'student_ids': ids})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_malformed_ids_rejected(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.get('/api/analytics/students/compare/', {'student_ids': 'abc,def'})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_student_role_cannot_compare_others(self):
        self.client.force_authenticate(self.student_in_a.user)
        resp = self.client.get('/api/analytics/students/compare/', {
            'student_ids': f'{self.student_in_a.id},{self.student_in_a2.id}',
        })
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_parent_can_compare_own_linked_children(self):
        parent = User.objects.create_user(email='sc_parent@test.tz', password='x', role='parent')
        ParentStudentLink.objects.create(parent=parent, student=self.student_in_a, is_primary=True)
        ParentStudentLink.objects.create(parent=parent, student=self.student_in_a2, is_primary=False)
        self.client.force_authenticate(parent)
        resp = self.client.get('/api/analytics/students/compare/', {
            'student_ids': f'{self.student_in_a.id},{self.student_in_a2.id}',
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_parent_blocked_comparing_unlinked_student(self):
        parent = User.objects.create_user(email='sc_parent2@test.tz', password='x', role='parent')
        ParentStudentLink.objects.create(parent=parent, student=self.student_in_a, is_primary=True)
        self.client.force_authenticate(parent)
        resp = self.client.get('/api/analytics/students/compare/', {
            'student_ids': f'{self.student_in_a.id},{self.student_in_a2.id}',
        })
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


class ComparisonPDFTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.subject = Subject.objects.create(name='PDF Compare Maths', code='PCMP')
        cls.grade = GradeLevel.objects.create(name='Form 4', short_name='F4', education_level='secondary', order=4)
        cls.classroom = Classroom.objects.create(name='4B', grade_level=cls.grade, stream='general', academic_year='2026')
        cls.admin = User.objects.create_user(email='pdf_admin@test.tz', password='x', role='super_admin')

        cls.students = []
        for i in range(2):
            s = StudentProfile.objects.create(
                user=User.objects.create_user(email=f'pdf_stu{i}@test.tz', password='x', role='student'),
                student_id=f'PDF{i:03d}', classroom=cls.classroom,
            )
            for j, score in enumerate([40 + i * 10, 60 + i * 10]):
                exam = make_exam(cls.subject, cls.classroom, datetime.date(2026, 1, j + 1))
                ExamScore.objects.create(exam=exam, student=s, score=score)
            cls.students.append(s)

    def test_pdf_export_returns_valid_pdf(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.get('/api/analytics/students/compare/pdf/', {
            'student_ids': f'{self.students[0].id},{self.students[1].id}',
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp['Content-Type'], 'application/pdf')
        self.assertTrue(resp.content.startswith(b'%PDF'))

    def test_pdf_export_works_with_students_with_no_topic_data(self):
        # No TopicScore rows exist for these students -> topics list is empty.
        self.client.force_authenticate(self.admin)
        resp = self.client.get('/api/analytics/students/compare/pdf/', {
            'student_ids': f'{self.students[0].id},{self.students[1].id}',
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_pdf_export_three_students(self):
        third = StudentProfile.objects.create(
            user=User.objects.create_user(email='pdf_stu2@test.tz', password='x', role='student'),
            student_id='PDF002x', classroom=self.classroom,
        )
        exam = make_exam(self.subject, self.classroom, datetime.date(2026, 1, 1))
        ExamScore.objects.create(exam=exam, student=third, score=90)
        self.client.force_authenticate(self.admin)
        resp = self.client.get('/api/analytics/students/compare/pdf/', {
            'student_ids': f'{self.students[0].id},{self.students[1].id},{third.id}',
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.content.startswith(b'%PDF'))
