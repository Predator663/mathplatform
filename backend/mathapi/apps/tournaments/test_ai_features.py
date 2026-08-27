"""
Tests for the AI-assisted tournament-matching features:
  - suggest_level_groups()/ai_refine_groups() 'ai_used' / 'ai_attempted' /
    'ai_error' contract (auto-match by level)
  - compatibility_note generation on manually-declared (or edited-into)
    skill mismatches, with and without Claude actually available
    (services.sync_compatibility_note / generate_incompatibility_note)

Every Claude call goes through services._call_claude, so these mock that
one seam rather than the network — no real API calls are made.
Run with: python manage.py test mathapi.apps.tournaments.test_ai_features -v 2
"""
import datetime
from unittest.mock import patch

from django.test import override_settings
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model

from mathapi.apps.accounts.models import Subject, TeacherAssignment
from mathapi.apps.students.models import GradeLevel, Classroom, StudentProfile
from mathapi.apps.exams.models import Exam, ExamScore
from .models import Tournament, Challenge
from . import services

User = get_user_model()


class TournamentAIFeatureTestBase(APITestCase):
    """Shared fixture: two tight skill tiers (top ~90s, bottom ~50s) more
    than LEVEL_COMPATIBILITY_GAP apart, so pairing across tiers is a
    reliable, deterministic mismatch and pairing within a tier is a
    reliable, deterministic match."""

    @classmethod
    def setUpTestData(cls):
        cls.subject = Subject.objects.create(name='AI Match Maths', code='AIMM')
        cls.grade = GradeLevel.objects.create(name='TF3', short_name='TF3', education_level='secondary', order=3)
        cls.classroom = Classroom.objects.create(name='AI Match Class', grade_level=cls.grade,
                                                  stream='general', academic_year='2026')
        cls.teacher = User.objects.create_user(email='ai_teacher@test.tz', password='x', role='teacher')
        TeacherAssignment.objects.create(teacher=cls.teacher, subject=cls.subject, classroom=cls.classroom)

        cls.prior_exam = Exam.objects.create(
            title='AI Prior Exam', exam_type='monthly_test', term='term_1', academic_year='2026',
            exam_date=datetime.date(2026, 1, 1), max_score=100, passing_score=40,
            subject=cls.subject, created_by=cls.teacher, is_published=True,
        )
        cls.prior_exam.classrooms.add(cls.classroom)

        cls.exam = Exam.objects.create(
            title='AI Cup Exam', exam_type='monthly_test', term='term_1', academic_year='2026',
            exam_date=datetime.date(2026, 3, 1), max_score=100, passing_score=40,
            subject=cls.subject, created_by=cls.teacher,
        )
        cls.exam.classrooms.add(cls.classroom)

        cls.students = []
        for i, score in enumerate([92, 89, 50, 47]):  # top pair, bottom pair
            u = User.objects.create_user(email=f'ai{i}@test.tz', password='x', role='student',
                                          first_name=f'Ai{i}', last_name='Student')
            student = StudentProfile.objects.create(user=u, student_id=f'A{i:04d}', classroom=cls.classroom)
            ExamScore.objects.create(exam=cls.prior_exam, student=student, score=score, entered_by=cls.teacher)
            cls.students.append(student)
        cls.top_a, cls.top_b, cls.bottom_a, cls.bottom_b = cls.students

    def _open_tournament(self):
        self.client.force_authenticate(self.teacher)
        resp = self.client.post('/api/tournaments/tournaments/', dict(
            title='AI Cup', classroom=self.classroom.id, exam=self.exam.id, mode='individual',
            registration_deadline='2026-02-01T00:00:00Z',
        ), format='json')
        tournament = Tournament.objects.get(id=resp.data['id'])
        self.client.post(f'/api/tournaments/tournaments/{tournament.id}/open-registration/')
        for s in self.students:
            self.client.post(f'/api/tournaments/tournaments/{tournament.id}/register/', {'student_id': s.id})
        return tournament


class CompatibilityNoteTests(TournamentAIFeatureTestBase):
    @override_settings(ANTHROPIC_API_KEY='test-key')
    @patch('mathapi.apps.tournaments.services._call_claude')
    def test_mismatched_manual_challenge_gets_ai_note(self, mock_call):
        mock_call.return_value = 'This could be a real giant-slayer opportunity for the underdog.'
        tournament = self._open_tournament()
        entries = list(tournament.entries.all())
        top_entry = next(e for e in entries if e.student_id == self.top_a.id)
        bottom_entry = next(e for e in entries if e.student_id == self.bottom_a.id)

        resp = self.client.post(f'/api/tournaments/tournaments/{tournament.id}/challenges/',
                                 {'entry_ids': [top_entry.id, bottom_entry.id]}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertEqual(resp.data['compatibility_note'], mock_call.return_value)
        self.assertEqual(resp.data['compatibility']['compatible'], False)

        challenge = Challenge.objects.get(id=resp.data['id'])
        self.assertEqual(challenge.compatibility_note, mock_call.return_value)
        mock_call.assert_called_once()

    def test_mismatched_manual_challenge_falls_back_without_ai_key(self):
        # No ANTHROPIC_API_KEY override -> _call_claude short-circuits to
        # None before ever making a request; the note should still be set,
        # just from the plain algorithmic reason instead of Claude.
        tournament = self._open_tournament()
        entries = list(tournament.entries.all())
        top_entry = next(e for e in entries if e.student_id == self.top_a.id)
        bottom_entry = next(e for e in entries if e.student_id == self.bottom_a.id)

        resp = self.client.post(f'/api/tournaments/tournaments/{tournament.id}/challenges/',
                                 {'entry_ids': [top_entry.id, bottom_entry.id]}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertTrue(resp.data['compatibility_note'])
        self.assertIn('percentage points apart', resp.data['compatibility_note'])

    def test_compatible_manual_challenge_has_no_note(self):
        tournament = self._open_tournament()
        entries = list(tournament.entries.all())
        top_entry = next(e for e in entries if e.student_id == self.top_a.id)
        top_entry_b = next(e for e in entries if e.student_id == self.top_b.id)

        resp = self.client.post(f'/api/tournaments/tournaments/{tournament.id}/challenges/',
                                 {'entry_ids': [top_entry.id, top_entry_b.id]}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertEqual(resp.data['compatibility_note'], '')

    def test_editing_challenge_to_a_compatible_pairing_clears_note(self):
        tournament = self._open_tournament()
        entries = list(tournament.entries.all())
        top_entry = next(e for e in entries if e.student_id == self.top_a.id)
        top_entry_b = next(e for e in entries if e.student_id == self.top_b.id)
        bottom_entry = next(e for e in entries if e.student_id == self.bottom_a.id)

        resp = self.client.post(f'/api/tournaments/tournaments/{tournament.id}/challenges/',
                                 {'entry_ids': [top_entry.id, bottom_entry.id]}, format='json')
        challenge_id = resp.data['id']
        self.assertTrue(resp.data['compatibility_note'])

        resp = self.client.patch(
            f'/api/tournaments/tournaments/{tournament.id}/challenges/{challenge_id}/',
            {'entry_ids': [top_entry.id, top_entry_b.id]}, format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(resp.data['compatibility_note'], '')
        self.assertEqual(Challenge.objects.get(id=challenge_id).compatibility_note, '')

    def test_sync_compatibility_note_unit_level(self):
        # Direct unit coverage of the function auto_create_level_challenges
        # also relies on for forced-incompatible auto-matched groups.
        tournament = self._open_tournament()
        entries = list(tournament.entries.all())
        top_entry = next(e for e in entries if e.student_id == self.top_a.id)
        bottom_entry = next(e for e in entries if e.student_id == self.bottom_a.id)

        challenge = Challenge.objects.create(tournament=tournament, initiated_by=self.teacher)
        challenge.entries.set([top_entry, bottom_entry])

        with patch('mathapi.apps.tournaments.services._call_claude', return_value=None):
            services.sync_compatibility_note(challenge)
        challenge.refresh_from_db()
        self.assertTrue(challenge.compatibility_note)


class AutoMatchAIContractTests(TournamentAIFeatureTestBase):
    def test_ai_not_attempted_without_api_key(self):
        tournament = self._open_tournament()
        resp = self.client.get(f'/api/tournaments/tournaments/{tournament.id}/suggested-pairs/',
                                {'use_ai': 'true'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(resp.data['ai_used'])
        self.assertFalse(resp.data['ai_attempted'])
        self.assertIsNone(resp.data['ai_error'])

    @override_settings(ANTHROPIC_API_KEY='test-key')
    @patch('mathapi.apps.tournaments.services._call_claude')
    def test_ai_attempted_and_error_surfaced_when_call_fails(self, mock_call):
        mock_call.return_value = None  # simulates a failed/timed-out call
        tournament = self._open_tournament()
        resp = self.client.get(f'/api/tournaments/tournaments/{tournament.id}/suggested-pairs/',
                                {'use_ai': 'true'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(resp.data['ai_used'])
        self.assertTrue(resp.data['ai_attempted'])
        self.assertIsNotNone(resp.data['ai_error'])
        # Falls back to a real (algorithmic) grouping rather than empty-handed.
        self.assertTrue(len(resp.data['proposed_groups']) > 0)

    @override_settings(ANTHROPIC_API_KEY='test-key')
    @patch('mathapi.apps.tournaments.services._call_claude')
    def test_ai_note_surfaced_per_group_when_call_succeeds(self, mock_call):
        tournament = self._open_tournament()
        entries = {e.student_id: e for e in tournament.entries.all()}
        import json
        mock_call.return_value = json.dumps({
            'groups': [
                {'ids': [entries[self.top_a.id].id, entries[self.top_b.id].id], 'note': 'Both consistently strong.'},
                {'ids': [entries[self.bottom_a.id].id, entries[self.bottom_b.id].id], 'note': 'Evenly matched pair.'},
            ],
            'bye_ids': [],
        })
        resp = self.client.get(f'/api/tournaments/tournaments/{tournament.id}/suggested-pairs/',
                                {'use_ai': 'true'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data['ai_used'])
        notes = {g['ai_note'] for g in resp.data['proposed_groups']}
        self.assertIn('Both consistently strong.', notes)
        self.assertIn('Evenly matched pair.', notes)
