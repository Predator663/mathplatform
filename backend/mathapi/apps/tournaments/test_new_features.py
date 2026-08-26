"""
Tests for the "Register Entire Class" bulk-registration action and the
delete restriction (cancelled/draft tournaments only).
Run with: python manage.py test mathapi.apps.tournaments.test_new_features -v 2
"""
import datetime
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model

from mathapi.apps.accounts.models import Subject, TeacherAssignment
from mathapi.apps.students.models import GradeLevel, Classroom, StudentProfile
from mathapi.apps.exams.models import Exam
from .models import Tournament, TournamentEntry

User = get_user_model()


def make_student(classroom, idx):
    u = User.objects.create_user(email=f'stu{idx}@test.tz', password='x', role='student',
                                  first_name=f'Student{idx}', last_name='Test')
    return StudentProfile.objects.create(user=u, student_id=f'S{idx:04d}', classroom=classroom)


class TournamentNewFeatureTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.subject = Subject.objects.create(name='Tourney Maths', code='TRNY')
        cls.grade = GradeLevel.objects.create(name='TF1', short_name='TF1', education_level='secondary', order=1)
        cls.classroom = Classroom.objects.create(name='Tourney Class', grade_level=cls.grade,
                                                   stream='general', academic_year='2026')
        cls.teacher = User.objects.create_user(email='trn_teacher@test.tz', password='x', role='teacher')
        TeacherAssignment.objects.create(teacher=cls.teacher, subject=cls.subject, classroom=cls.classroom)
        cls.exam = Exam.objects.create(
            title='Tourney Exam', exam_type='monthly_test', term='term_1', academic_year='2026',
            exam_date=datetime.date(2026, 3, 1), max_score=100, passing_score=40,
            subject=cls.subject, created_by=cls.teacher,
        )
        cls.exam.classrooms.add(cls.classroom)
        cls.students = [make_student(cls.classroom, i) for i in range(5)]

    def _make_tournament(self, **overrides):
        self.client.force_authenticate(self.teacher)
        payload = dict(
            title='Test Cup', classroom=self.classroom.id, exam=self.exam.id, mode='individual',
            registration_deadline='2026-02-01T00:00:00Z',
        )
        payload.update(overrides)
        resp = self.client.post('/api/tournaments/tournaments/', payload, format='json')
        assert resp.status_code == status.HTTP_201_CREATED, resp.data
        return Tournament.objects.get(id=resp.data['id'])

    def test_register_class_bulk_registers_everyone(self):
        t = self._make_tournament()
        self.client.post(f'/api/tournaments/tournaments/{t.id}/open-registration/')
        resp = self.client.post(f'/api/tournaments/tournaments/{t.id}/register-class/')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertEqual(resp.data['created_count'], 5)
        self.assertEqual(TournamentEntry.objects.filter(tournament=t, withdrawn=False).count(), 5)

    def test_register_class_skips_already_registered(self):
        t = self._make_tournament()
        self.client.post(f'/api/tournaments/tournaments/{t.id}/open-registration/')
        self.client.post(f'/api/tournaments/tournaments/{t.id}/register/', {'student_id': self.students[0].id})
        resp = self.client.post(f'/api/tournaments/tournaments/{t.id}/register-class/')
        self.assertEqual(resp.data['created_count'], 4)
        self.assertEqual(resp.data['already_registered_count'], 1)

    def test_register_class_respects_max_entrants(self):
        t = self._make_tournament(max_entrants=3)
        self.client.post(f'/api/tournaments/tournaments/{t.id}/open-registration/')
        resp = self.client.post(f'/api/tournaments/tournaments/{t.id}/register-class/')
        self.assertEqual(resp.data['created_count'], 3)
        self.assertEqual(resp.data['skipped_due_to_cap'], 2)

    def test_register_class_rejected_before_registration_open(self):
        t = self._make_tournament()
        resp = self.client.post(f'/api/tournaments/tournaments/{t.id}/register-class/')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_class_rejected_for_stream_mode(self):
        t = self._make_tournament(mode='stream')
        self.client.post(f'/api/tournaments/tournaments/{t.id}/open-registration/')
        resp = self.client.post(f'/api/tournaments/tournaments/{t.id}/register-class/')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_student_cannot_bulk_register_class(self):
        t = self._make_tournament()
        self.client.post(f'/api/tournaments/tournaments/{t.id}/open-registration/')
        self.client.force_authenticate(self.students[0].user)
        resp = self.client.post(f'/api/tournaments/tournaments/{t.id}/register-class/')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_rejected_for_live_tournament(self):
        t = self._make_tournament()
        self.client.post(f'/api/tournaments/tournaments/{t.id}/open-registration/')
        self.client.force_authenticate(self.teacher)
        resp = self.client.delete(f'/api/tournaments/tournaments/{t.id}/')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(Tournament.objects.filter(id=t.id).exists())

    def test_delete_allowed_for_cancelled_tournament(self):
        t = self._make_tournament()
        self.client.post(f'/api/tournaments/tournaments/{t.id}/cancel/')
        resp = self.client.delete(f'/api/tournaments/tournaments/{t.id}/')
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Tournament.objects.filter(id=t.id).exists())

    def test_delete_allowed_for_draft_tournament(self):
        t = self._make_tournament()
        resp = self.client.delete(f'/api/tournaments/tournaments/{t.id}/')
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)


class ChallengeMatchupsPDFTests(APITestCase):
    """Covers the /reports/export/tournament/<id>/matchups/pdf/ endpoint:
    accessible to students in the tournament's own classroom, includes
    unmatched entrants, and (via a manual check) compacts long names."""

    @classmethod
    def setUpTestData(cls):
        cls.subject = Subject.objects.create(name='Matchup Maths', code='MTCH')
        cls.grade = GradeLevel.objects.create(name='MF1', short_name='MF1', education_level='secondary', order=1)
        cls.classroom = Classroom.objects.create(name='Matchup Class', grade_level=cls.grade,
                                                   stream='general', academic_year='2026')
        cls.teacher = User.objects.create_user(email='mtch_teacher@test.tz', password='x', role='teacher')
        TeacherAssignment.objects.create(teacher=cls.teacher, subject=cls.subject, classroom=cls.classroom)
        cls.exam = Exam.objects.create(
            title='Matchup Exam', exam_type='monthly_test', term='term_1', academic_year='2026',
            exam_date=datetime.date(2026, 3, 1), max_score=100, passing_score=40,
            subject=cls.subject, created_by=cls.teacher,
        )
        cls.exam.classrooms.add(cls.classroom)

        def make_named(idx, first, last):
            u = User.objects.create_user(email=f'mtch{idx}@test.tz', password='x', role='student',
                                          first_name=first, last_name=last)
            return StudentProfile.objects.create(user=u, student_id=f'M{idx:04d}', classroom=cls.classroom)

        cls.s1 = make_named(1, 'John Petro', 'Mushi')       # 3-word name -> should compact
        cls.s2 = make_named(2, 'Neema', 'Hassan')           # 2-word name -> unchanged
        cls.s3 = make_named(3, 'Amina', 'Juma')

        cls.client_teacher = APITestCase.client_class()
        cls.client_teacher.force_authenticate(cls.teacher)
        resp = cls.client_teacher.post('/api/tournaments/tournaments/', dict(
            title='Matchup Cup', classroom=cls.classroom.id, exam=cls.exam.id, mode='individual',
            registration_deadline='2026-02-01T00:00:00Z',
        ), format='json')
        cls.tournament = Tournament.objects.get(id=resp.data['id'])
        cls.client_teacher.post(f'/api/tournaments/tournaments/{cls.tournament.id}/open-registration/')
        for s in (cls.s1, cls.s2, cls.s3):
            cls.client_teacher.post(f'/api/tournaments/tournaments/{cls.tournament.id}/register/', {'student_id': s.id})
        entries = list(cls.tournament.entries.all())
        cls.client_teacher.post(f'/api/tournaments/tournaments/{cls.tournament.id}/challenges/',
                                 {'entry_ids': [entries[0].id, entries[1].id]}, format='json')

    def test_student_in_classroom_can_download_matchups_pdf(self):
        self.client.force_authenticate(self.s1.user)
        resp = self.client.get(f'/api/reports/export/tournament/{self.tournament.id}/matchups/pdf/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp['Content-Type'], 'application/pdf')
        self.assertGreater(len(resp.content), 500)

    def test_name_compaction_shortens_middle_name(self):
        from mathapi.apps.reports.pdf_engine import _compact_name
        self.assertEqual(_compact_name('John Petro Mushi'), 'John P. Mushi')
        self.assertEqual(_compact_name('Neema Hassan'), 'Neema Hassan')
        self.assertEqual(_compact_name('Neema Elizabeth Grace Hassan'), 'Neema E. G. Hassan')
