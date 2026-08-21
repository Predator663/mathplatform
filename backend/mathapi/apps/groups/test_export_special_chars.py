"""
Regression tests for a ReportLab XML-parse crash: any teacher-entered
text containing '<', '>', or '&' (routine on a maths platform — "x < 5",
"Form 3 & 4", "A & B") used to 500 every PDF export that fed it straight
into Paragraph markup. Covers both the groups summary PDF (pre-existing
bug) and the group-work-analytics PDF (introduced this session).

Run with: python manage.py test mathapi.apps.groups.test_export_special_chars -v 2
"""
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from mathapi.apps.students.models import GradeLevel, Classroom
from .models import StudentGroup
from . import report_engine

User = get_user_model()


class ExportSpecialCharacterTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.teacher = User.objects.create_user(email='esc_teacher@test.tz', password='x', role='teacher')
        cls.grade = GradeLevel.objects.create(name='Form 2 Esc', short_name='F2', education_level='secondary', order=2)
        cls.classroom = Classroom.objects.create(
            name='2A & 2B Esc', grade_level=cls.grade, stream='general', academic_year='2026',
        )

    def test_groups_summary_pdf_survives_ampersand_and_inequality_in_group_name(self):
        group = StudentGroup.objects.create(
            classroom=self.classroom, name='Team A < B & C', academic_year='2026', badge_color='#2563eb',
        )
        extra = {'school_name': 'Amani & Girls School', 'academic_year': '2026', 'generated_by': 'Admin'}
        pdf_bytes = report_engine.generate_groups_summary_pdf(self.classroom, [group], extra)
        self.assertTrue(pdf_bytes.startswith(b'%PDF'))

    def test_groups_roster_pdf_survives_ampersand_in_group_and_subject_name(self):
        group = StudentGroup.objects.create(
            classroom=self.classroom, name='Solve x < 5 & y > 3', academic_year='2026', badge_color='#10b981',
        )
        extra = {'school_name': 'Amani & Girls School', 'academic_year': '2026', 'generated_by': 'Admin'}
        pdf_bytes = report_engine.generate_groups_roster_pdf(self.classroom, [group], extra)
        self.assertTrue(pdf_bytes.startswith(b'%PDF'))

    def test_group_work_analytics_pdf_survives_special_characters_everywhere(self):
        analytics = {
            'classroom_average_pct': 62.3, 'assignments_count': 1, 'groups_scored_count': 1,
            'distribution': {'0-49': 0, '50-59': 0, '60-69': 0, '70-79': 0, '80-89': 0, '90-100': 1},
            'trend': [{
                'assignment_id': 1, 'title': 'Solve x < 5 & y > 3', 'date': '2026-03-01',
                'assignment_type': 'project', 'average_pct': 90.0, 'groups_scored': 1,
            }],
            'per_group': [{
                'group_id': 1, 'group_name': 'A & B Team', 'stream_id': 1, 'stream_name': 'X < Y',
                'assignments_count': 1, 'average_pct': 90.0, 'best_pct': 90.0, 'worst_pct': 90.0, 'trend': [],
            }],
            'per_stream': [{
                'stream_id': 1, 'stream_name': 'X < Y', 'group_count': 1, 'assignments_scored': 1, 'average_pct': 90.0,
            }],
            'top_groups': [], 'bottom_groups': [],
        }
        extra = {'school_name': 'Amani & Girls School', 'academic_year': '2026', 'generated_by': 'Admin'}
        extra['meta_lines'] = report_engine._meta_lines(self.classroom, extra)
        pdf_bytes = report_engine.generate_group_work_analytics_pdf(self.classroom, analytics, extra)
        self.assertTrue(pdf_bytes.startswith(b'%PDF'))

        xl_bytes = report_engine.generate_group_work_analytics_excel(self.classroom, analytics, extra)
        self.assertTrue(xl_bytes.startswith(b'PK'))
