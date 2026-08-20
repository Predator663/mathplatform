"""
Tests for group-work assignments: recording marks per group (with
optional per-student adjustments), the analytics rollups, and the
performance-based reassignment suggestions. Covers both the service
layer and the API endpoints teachers actually hit.

Run with: python manage.py test mathapi.apps.groups.test_group_assignments -v 2
"""
import datetime

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from mathapi.apps.accounts.models import Subject, TeacherAssignment
from mathapi.apps.exams.models import Exam, ExamScore
from mathapi.apps.students.models import GradeLevel, Classroom, Stream, StudentProfile
from .models import (
    StudentGroup, GroupMembership, GroupAssignment, GroupAssignmentScore, GroupAssignmentMemberMark,
)
from . import services

User = get_user_model()


def make_student(email, student_id, classroom, stream=None):
    user = User.objects.create_user(email=email, password='x', role='student')
    return StudentProfile.objects.create(user=user, student_id=student_id, classroom=classroom, stream=stream)


class GroupAssignmentServiceTests(APITestCase):
    """Service-layer tests: recording, analytics, and reassignment logic."""

    @classmethod
    def setUpTestData(cls):
        cls.teacher = User.objects.create_user(email='teacher@test.tz', password='x', role='teacher')
        cls.grade = GradeLevel.objects.create(name='Form 2', short_name='F2', education_level='secondary', order=2)
        cls.classroom = Classroom.objects.create(
            name='2C', grade_level=cls.grade, stream='general', academic_year='2026',
        )
        cls.subject = Subject.objects.create(name='Mathematics GA Test', code='MATHGA')
        TeacherAssignment.objects.create(teacher=cls.teacher, classroom=cls.classroom, subject=cls.subject)

        cls.stream_a = Stream.objects.create(classroom=cls.classroom, name='A')
        cls.stream_b = Stream.objects.create(classroom=cls.classroom, name='B')

        cls.stream_a_students = [
            make_student(f'ga{i}@test.tz', f'GA{i:03d}', cls.classroom, cls.stream_a) for i in range(6)
        ]
        cls.stream_b_students = [
            make_student(f'gb{i}@test.tz', f'GB{i:03d}', cls.classroom, cls.stream_b) for i in range(6)
        ]

        cls.ga1 = StudentGroup.objects.create(classroom=cls.classroom, name='GA1', academic_year='2026', stream=cls.stream_a)
        cls.ga2 = StudentGroup.objects.create(classroom=cls.classroom, name='GA2', academic_year='2026', stream=cls.stream_a)
        cls.gb1 = StudentGroup.objects.create(classroom=cls.classroom, name='GB1', academic_year='2026', stream=cls.stream_b)
        cls.gb2 = StudentGroup.objects.create(classroom=cls.classroom, name='GB2', academic_year='2026', stream=cls.stream_b)

        for i, s in enumerate(cls.stream_a_students):
            GroupMembership.objects.create(group=cls.ga1 if i % 2 == 0 else cls.ga2, student=s)
        for i, s in enumerate(cls.stream_b_students):
            GroupMembership.objects.create(group=cls.gb1 if i % 2 == 0 else cls.gb2, student=s)

        cls.assignment = GroupAssignment.objects.create(
            classroom=cls.classroom, subject=cls.subject, title='Group Project 1',
            assignment_type='project', term='term_1', academic_year='2026',
            date_given=datetime.date(2026, 3, 1), max_score=50,
        )

    def test_record_scores_creates_score_and_member_marks_for_every_member(self):
        result = services.record_group_assignment_scores(
            self.assignment,
            [{'group_id': self.ga1.id, 'score': 40, 'remarks': 'Good work'}],
            self.teacher,
        )
        self.assertEqual(result['errors'], [])
        self.assertEqual(len(result['scores']), 1)

        score = GroupAssignmentScore.objects.get(assignment=self.assignment, group=self.ga1)
        self.assertEqual(float(score.score), 40.0)
        self.assertEqual(score.percentage, 80.0)

        marks = GroupAssignmentMemberMark.objects.filter(group_score=score)
        self.assertEqual(marks.count(), self.ga1.memberships.count())
        for mark in marks:
            self.assertEqual(mark.effective_score, 40.0)
            self.assertEqual(float(mark.adjustment), 0.0)

    def test_invalid_group_id_is_reported_without_aborting_the_batch(self):
        result = services.record_group_assignment_scores(
            self.assignment,
            [
                {'group_id': 999999, 'score': 40},
                {'group_id': self.ga2.id, 'score': 35},
            ],
            self.teacher,
        )
        self.assertEqual(len(result['errors']), 1)
        self.assertEqual(len(result['scores']), 1)
        self.assertTrue(GroupAssignmentScore.objects.filter(assignment=self.assignment, group=self.ga2).exists())

    def test_per_student_adjustment_overrides_only_that_student(self):
        services.record_group_assignment_scores(
            self.assignment,
            [{'group_id': self.ga1.id, 'score': 40}],
            self.teacher,
        )
        member = self.ga1.memberships.first().student
        services.record_group_assignment_scores(
            self.assignment,
            [{
                'group_id': self.ga1.id, 'score': 40,
                'member_adjustments': [{'student_id': member.id, 'adjustment': -10, 'note': 'Absent for part'}],
            }],
            self.teacher,
        )
        score = GroupAssignmentScore.objects.get(assignment=self.assignment, group=self.ga1)
        adjusted = GroupAssignmentMemberMark.objects.get(group_score=score, student=member)
        untouched = GroupAssignmentMemberMark.objects.exclude(student=member).filter(group_score=score).first()

        self.assertEqual(adjusted.effective_score, 30.0)
        self.assertEqual(float(untouched.adjustment), 0.0)
        self.assertEqual(untouched.effective_score, 40.0)

    def test_effective_score_is_clamped_to_max_score(self):
        services.record_group_assignment_scores(
            self.assignment,
            [{'group_id': self.ga1.id, 'score': 48}],
            self.teacher,
        )
        member = self.ga1.memberships.first().student
        services.record_group_assignment_scores(
            self.assignment,
            [{
                'group_id': self.ga1.id, 'score': 48,
                'member_adjustments': [{'student_id': member.id, 'adjustment': 20}],
            }],
            self.teacher,
        )
        score = GroupAssignmentScore.objects.get(assignment=self.assignment, group=self.ga1)
        mark = GroupAssignmentMemberMark.objects.get(group_score=score, student=member)
        self.assertEqual(mark.effective_score, 50.0)  # clamped to max_score

    def test_is_absent_zeroes_group_score(self):
        result = services.record_group_assignment_scores(
            self.assignment,
            [{'group_id': self.ga1.id, 'score': 40, 'is_absent': True}],
            self.teacher,
        )
        self.assertEqual(result['errors'], [])
        score = GroupAssignmentScore.objects.get(assignment=self.assignment, group=self.ga1)
        self.assertEqual(float(score.score), 0.0)
        self.assertTrue(score.is_absent)

    def test_analytics_rollups_and_distribution(self):
        services.record_group_assignment_scores(self.assignment, [
            {'group_id': self.ga1.id, 'score': 45},  # 90%
            {'group_id': self.ga2.id, 'score': 25},  # 50%
            {'group_id': self.gb1.id, 'score': 10},  # 20%
            {'group_id': self.gb2.id, 'score': 15},  # 30%
        ], self.teacher)

        analytics = services.get_group_assignment_analytics(self.classroom.id, academic_year='2026')
        self.assertEqual(analytics['assignments_count'], 1)
        self.assertEqual(analytics['groups_scored_count'], 4)
        self.assertAlmostEqual(analytics['classroom_average_pct'], (90 + 50 + 20 + 30) / 4, places=1)
        self.assertEqual(sum(analytics['distribution'].values()), 4)

        by_group = {g['group_id']: g for g in analytics['per_group']}
        self.assertEqual(by_group[self.ga1.id]['average_pct'], 90.0)
        self.assertEqual(by_group[self.gb1.id]['average_pct'], 20.0)

        stream_analytics = services.get_group_assignment_analytics(
            self.classroom.id, stream_id=self.stream_b.id, academic_year='2026',
        )
        self.assertEqual({g['group_id'] for g in stream_analytics['per_group']}, {self.gb1.id, self.gb2.id})

    def test_reassignment_suggestions_flag_underperforming_group_with_same_stream_candidate(self):
        # GB1 scores far below the classroom average; GB2 (same stream) scores well.
        services.record_group_assignment_scores(self.assignment, [
            {'group_id': self.ga1.id, 'score': 45},  # 90%
            {'group_id': self.ga2.id, 'score': 40},  # 80%
            {'group_id': self.gb1.id, 'score': 45},  # 90% — strong, will supply the candidate
            {'group_id': self.gb2.id, 'score': 5},   # 10% — underperforming
        ], self.teacher)

        exam = Exam.objects.create(
            title='Midterm', exam_type='mid_term', term='term_1', academic_year='2026',
            exam_date=datetime.date(2026, 2, 1), max_score=100, passing_score=30,
            subject=self.subject, created_by=self.teacher,
        )
        exam.classrooms.add(self.classroom)
        for s in self.gb1.memberships.all():
            ExamScore.objects.create(exam=exam, student=s.student, score=85, entered_by=self.teacher)
        for s in self.gb2.memberships.all():
            ExamScore.objects.create(exam=exam, student=s.student, score=30, entered_by=self.teacher)

        suggestions = services.get_group_assignment_reassignment_suggestions(
            self.classroom.id, academic_year='2026',
        )
        underperforming_ids = {u['group_id'] for u in suggestions['underperforming']}
        self.assertIn(self.gb2.id, underperforming_ids)

        gb2_entry = next(u for u in suggestions['underperforming'] if u['group_id'] == self.gb2.id)
        self.assertTrue(gb2_entry['candidates'], 'expected a same-stream strong candidate for GB2')
        for c in gb2_entry['candidates']:
            self.assertEqual(c['from_group_id'], self.gb1.id)


class GroupAssignmentAPITests(APITestCase):
    """API-level tests: permissions, the record-scores action, and the analytics endpoint."""

    @classmethod
    def setUpTestData(cls):
        cls.teacher = User.objects.create_user(email='api_teacher@test.tz', password='x', role='teacher')
        cls.other_teacher = User.objects.create_user(email='other_teacher@test.tz', password='x', role='teacher')
        cls.grade = GradeLevel.objects.create(name='Form 3', short_name='F3', education_level='secondary', order=3)
        cls.classroom = Classroom.objects.create(
            name='3A', grade_level=cls.grade, stream='general', academic_year='2026',
        )
        cls.subject = Subject.objects.create(name='Mathematics API', code='MATHAPI')
        TeacherAssignment.objects.create(teacher=cls.teacher, classroom=cls.classroom, subject=cls.subject)

        cls.students = [make_student(f'api{i}@test.tz', f'API{i:03d}', cls.classroom) for i in range(4)]
        cls.group = StudentGroup.objects.create(classroom=cls.classroom, name='G1', academic_year='2026')
        for s in cls.students:
            GroupMembership.objects.create(group=cls.group, student=s)

        cls.assignment = GroupAssignment.objects.create(
            classroom=cls.classroom, subject=cls.subject, title='API Project',
            assignment_type='classwork', academic_year='2026', date_given=datetime.date(2026, 3, 1), max_score=20,
            created_by=cls.teacher,
        )

    def test_record_scores_requires_authentication(self):
        url = reverse('groupassignment-record-scores', args=[self.assignment.id])
        res = self.client.post(url, {'entries': [{'group_id': self.group.id, 'score': 15}]}, format='json')
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_teacher_without_classroom_access_is_forbidden(self):
        self.client.force_authenticate(self.other_teacher)
        url = reverse('groupassignment-record-scores', args=[self.assignment.id])
        res = self.client.post(url, {'entries': [{'group_id': self.group.id, 'score': 15}]}, format='json')
        self.assertIn(res.status_code, (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND))

    def test_record_scores_happy_path(self):
        self.client.force_authenticate(self.teacher)
        url = reverse('groupassignment-record-scores', args=[self.assignment.id])
        res = self.client.post(url, {
            'entries': [{'group_id': self.group.id, 'score': 18, 'remarks': 'Great teamwork'}],
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['errors'], [])
        self.assertEqual(len(res.data['scores']), 1)
        self.assertEqual(res.data['scores'][0]['percentage'], 90.0)
        self.assertEqual(len(res.data['scores'][0]['member_marks']), len(self.students))

    def test_roster_action_lists_groups_and_members(self):
        self.client.force_authenticate(self.teacher)
        url = reverse('groupassignment-roster', args=[self.assignment.id])
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data['groups']), 1)
        self.assertEqual(res.data['groups'][0]['member_count'], len(self.students))

    def test_analytics_endpoint_reflects_recorded_scores(self):
        self.client.force_authenticate(self.teacher)
        record_url = reverse('groupassignment-record-scores', args=[self.assignment.id])
        self.client.post(record_url, {'entries': [{'group_id': self.group.id, 'score': 10}]}, format='json')

        analytics_url = reverse('group_work_analytics', args=[self.classroom.id])
        res = self.client.get(analytics_url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['classroom_average_pct'], 50.0)
        self.assertEqual(res.data['groups_scored_count'], 1)

    def test_reassignment_endpoint_returns_group_statuses(self):
        self.client.force_authenticate(self.teacher)
        record_url = reverse('groupassignment-record-scores', args=[self.assignment.id])
        self.client.post(record_url, {'entries': [{'group_id': self.group.id, 'score': 10}]}, format='json')

        url = reverse('group_assignment_reassignment', args=[self.classroom.id])
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data['groups']), 1)

    def test_marks_csv_export_requires_recorded_marks(self):
        self.client.force_authenticate(self.teacher)
        url = reverse('group_assignment_marks_csv', args=[self.classroom.id])
        res = self.client.get(url)
        # No marks recorded yet — should succeed with just a header row, not error.
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res['Content-Type'], 'text/csv')
