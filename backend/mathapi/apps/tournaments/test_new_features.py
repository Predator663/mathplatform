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


class GroupAutoMatchAndEditTests(APITestCase):
    """
    Tests for the generalised (N-way, not just pairs) auto-match-by-level
    grouping and for editing an already-declared challenge while
    registration is open.
    """

    @classmethod
    def setUpTestData(cls):
        cls.subject = Subject.objects.create(name='Group Match Maths', code='GRPM')
        cls.grade = GradeLevel.objects.create(name='TF2', short_name='TF2', education_level='secondary', order=2)
        cls.classroom = Classroom.objects.create(name='Group Match Class', grade_level=cls.grade,
                                                   stream='general', academic_year='2026')
        cls.teacher = User.objects.create_user(email='grp_teacher@test.tz', password='x', role='teacher')
        TeacherAssignment.objects.create(teacher=cls.teacher, subject=cls.subject, classroom=cls.classroom)

        # A prior, already-published exam so get_prior_average has something
        # to read — auto-match needs history to rank/cluster entrants.
        cls.prior_exam = Exam.objects.create(
            title='Prior Exam', exam_type='monthly_test', term='term_1', academic_year='2026',
            exam_date=datetime.date(2026, 1, 1), max_score=100, passing_score=40,
            subject=cls.subject, created_by=cls.teacher, is_published=True,
        )
        cls.prior_exam.classrooms.add(cls.classroom)

        cls.exam = Exam.objects.create(
            title='Group Cup Exam', exam_type='monthly_test', term='term_1', academic_year='2026',
            exam_date=datetime.date(2026, 3, 1), max_score=100, passing_score=40,
            subject=cls.subject, created_by=cls.teacher,
        )
        cls.exam.classrooms.add(cls.classroom)

        # Six students forming two tight skill tiers of three (roughly
        # 90/88/86 and 50/48/46) so the clustering algorithm should propose
        # two 3-way groups rather than three pairs.
        from mathapi.apps.exams.models import ExamScore
        cls.students = []
        for i, score in enumerate([90, 88, 86, 50, 48, 46]):
            u = User.objects.create_user(email=f'grp{i}@test.tz', password='x', role='student',
                                          first_name=f'Grp{i}', last_name='Student')
            student = StudentProfile.objects.create(user=u, student_id=f'G{i:04d}', classroom=cls.classroom)
            ExamScore.objects.create(exam=cls.prior_exam, student=student, score=score, entered_by=cls.teacher)
            cls.students.append(student)

    def _open_tournament(self):
        self.client.force_authenticate(self.teacher)
        resp = self.client.post('/api/tournaments/tournaments/', dict(
            title='Group Cup', classroom=self.classroom.id, exam=self.exam.id, mode='individual',
            registration_deadline='2026-02-01T00:00:00Z',
        ), format='json')
        tournament = Tournament.objects.get(id=resp.data['id'])
        self.client.post(f'/api/tournaments/tournaments/{tournament.id}/open-registration/')
        for s in self.students:
            self.client.post(f'/api/tournaments/tournaments/{tournament.id}/register/', {'student_id': s.id})
        return tournament

    def test_suggested_pairs_can_propose_groups_larger_than_two(self):
        tournament = self._open_tournament()
        resp = self.client.get(f'/api/tournaments/tournaments/{tournament.id}/suggested-pairs/',
                                {'group_size': 3})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        groups = resp.data['proposed_groups']
        self.assertTrue(any(g['size'] > 2 for g in groups),
                         f'expected at least one 3+ way group, got sizes {[g["size"] for g in groups]}')
        self.assertEqual(len(resp.data['byes']), 0)

    def test_auto_match_creates_multi_combatant_challenges(self):
        tournament = self._open_tournament()
        resp = self.client.post(f'/api/tournaments/tournaments/{tournament.id}/auto-match/',
                                 {'group_size': 3, 'only_compatible': True}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        created = resp.data['created']
        self.assertTrue(any(len(c['entries']) > 2 for c in created),
                         f'expected a challenge with 3+ entries, got {[len(c["entries"]) for c in created]}')

    def test_manual_declare_still_allows_three_or_more(self):
        tournament = self._open_tournament()
        entries = list(tournament.entries.all()[:3])
        resp = self.client.post(f'/api/tournaments/tournaments/{tournament.id}/challenges/',
                                 {'entry_ids': [e.id for e in entries]}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(resp.data['entries']), 3)

    def test_teacher_can_edit_challenge_while_registration_open(self):
        tournament = self._open_tournament()
        entries = list(tournament.entries.all())
        resp = self.client.post(f'/api/tournaments/tournaments/{tournament.id}/challenges/',
                                 {'entry_ids': [entries[0].id, entries[1].id]}, format='json')
        challenge_id = resp.data['id']

        resp = self.client.patch(
            f'/api/tournaments/tournaments/{tournament.id}/challenges/{challenge_id}/',
            {'label': 'Updated Label', 'entry_ids': [entries[0].id, entries[1].id, entries[2].id]},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(resp.data['label'], 'Updated Label')
        self.assertEqual(len(resp.data['entries']), 3)

    def test_edit_rejected_once_registration_closed(self):
        tournament = self._open_tournament()
        entries = list(tournament.entries.all())
        resp = self.client.post(f'/api/tournaments/tournaments/{tournament.id}/challenges/',
                                 {'entry_ids': [entries[0].id, entries[1].id]}, format='json')
        challenge_id = resp.data['id']
        self.client.post(f'/api/tournaments/tournaments/{tournament.id}/close-registration/')

        resp = self.client.patch(
            f'/api/tournaments/tournaments/{tournament.id}/challenges/{challenge_id}/',
            {'label': 'Nope'}, format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_student_cannot_edit_a_challenge_she_is_not_part_of(self):
        tournament = self._open_tournament()
        entries = list(tournament.entries.all())
        resp = self.client.post(f'/api/tournaments/tournaments/{tournament.id}/challenges/',
                                 {'entry_ids': [entries[0].id, entries[1].id]}, format='json')
        challenge_id = resp.data['id']

        outsider = self.students[3]  # not one of entries[0]/entries[1]
        self.client.force_authenticate(outsider.user)
        resp = self.client.patch(
            f'/api/tournaments/tournaments/{tournament.id}/challenges/{challenge_id}/',
            {'label': 'Hijacked'}, format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
