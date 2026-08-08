"""
API-level verification for the exams list export (CSV) and the
academic-years lookup used by the frontend's filter dropdown. Run with:
    python manage.py test mathapi.apps.exams.test_export -v 2
"""
import csv
import datetime
import io
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model

from mathapi.apps.accounts.models import Subject
from mathapi.apps.students.models import GradeLevel, Classroom
from mathapi.apps.exams.models import Exam

User = get_user_model()


class ExamExportTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(email='admin@export.tz', password='x', role='super_admin')
        cls.teacher = User.objects.create_user(email='teacher@export.tz', password='x', role='teacher')
        cls.subject = Subject.objects.create(name='Export Maths', code='EXPM')
        cls.grade = GradeLevel.objects.create(name='Form 2', short_name='F2', education_level='secondary', order=2)
        cls.classroom_a = Classroom.objects.create(name='2A', grade_level=cls.grade, stream='general', academic_year='2025')
        cls.classroom_b = Classroom.objects.create(name='2B', grade_level=cls.grade, stream='general', academic_year='2026')

        cls.exam_2025 = Exam.objects.create(
            title='2025 Mid Term', exam_type='mid_term', term='term_1', academic_year='2025',
            exam_date=datetime.date(2025, 4, 1), max_score=100, passing_score=30,
            subject=cls.subject, created_by=cls.admin, is_published=True,
        )
        cls.exam_2025.classrooms.add(cls.classroom_a)

        cls.exam_2026 = Exam.objects.create(
            title='2026 Terminal', exam_type='terminal', term='term_2', academic_year='2026',
            exam_date=datetime.date(2026, 6, 1), max_score=100, passing_score=40,
            subject=cls.subject, created_by=cls.teacher, is_published=False,
        )
        cls.exam_2026.classrooms.add(cls.classroom_b)

    # ── Academic years ───────────────────────────────────────────────────
    def test_academic_years_lists_distinct_years(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.get('/api/exams/exams/academic-years/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(set(resp.data), {'2025', '2026'})

    def test_academic_years_requires_auth(self):
        resp = self.client.get('/api/exams/exams/academic-years/')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    # ── CSV export ───────────────────────────────────────────────────────
    def test_export_csv_returns_all_matching_rows(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.get('/api/exams/exams/export-csv/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp['Content-Type'], 'text/csv')
        rows = list(csv.reader(io.StringIO(resp.content.decode('utf-8'))))
        titles = {r[0] for r in rows[1:]}
        self.assertEqual(titles, {'2025 Mid Term', '2026 Terminal'})

    def test_export_csv_respects_filters(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.get('/api/exams/exams/export-csv/', {'academic_year': '2025'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        rows = list(csv.reader(io.StringIO(resp.content.decode('utf-8'))))
        titles = [r[0] for r in rows[1:]]
        self.assertEqual(titles, ['2025 Mid Term'])

    def test_export_csv_respects_search(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.get('/api/exams/exams/export-csv/', {'search': 'Terminal'})
        rows = list(csv.reader(io.StringIO(resp.content.decode('utf-8'))))
        titles = [r[0] for r in rows[1:]]
        self.assertEqual(titles, ['2026 Terminal'])

    def test_export_csv_requires_auth(self):
        resp = self.client.get('/api/exams/exams/export-csv/')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

class ExamClassroomFilterTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(email='admin@clsfilter.tz', password='x', role='super_admin')
        cls.subject = Subject.objects.create(name='ClsFilter Maths', code='CLSF')
        cls.grade = GradeLevel.objects.create(name='Form 1', short_name='F1', education_level='secondary', order=1)
        cls.classroom_a = Classroom.objects.create(name='1A', grade_level=cls.grade, stream='general', academic_year='2026')
        cls.classroom_b = Classroom.objects.create(name='1B', grade_level=cls.grade, stream='general', academic_year='2026')

        cls.exam_a = Exam.objects.create(
            title='Exam For 1A', exam_type='mid_term', term='term_1', academic_year='2026',
            exam_date=datetime.date(2026, 3, 1), max_score=100, passing_score=30,
            subject=cls.subject, created_by=cls.admin, is_published=True,
        )
        cls.exam_a.classrooms.add(cls.classroom_a)

        cls.exam_b = Exam.objects.create(
            title='Exam For 1B', exam_type='mid_term', term='term_1', academic_year='2026',
            exam_date=datetime.date(2026, 3, 1), max_score=100, passing_score=30,
            subject=cls.subject, created_by=cls.admin, is_published=True,
        )
        cls.exam_b.classrooms.add(cls.classroom_b)

    def test_filter_by_single_classroom_id(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.get('/api/exams/exams/', {'classrooms': self.classroom_a.id})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        titles = {e['title'] for e in resp.data['results']}
        self.assertEqual(titles, {'Exam For 1A'})
