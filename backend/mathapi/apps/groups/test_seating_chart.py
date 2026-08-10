"""
Tests for services.generate_seating_chart and its API endpoint.
Run with: python manage.py test mathapi.apps.groups.test_seating_chart -v 2
"""
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model

from mathapi.apps.accounts.models import TeacherAssignment, Subject
from mathapi.apps.students.models import GradeLevel, Classroom, StudentProfile, Stream
from .models import PeerConstraint, StudentGroup, GroupMembership
from . import services

User = get_user_model()


def make_student(email, student_id, classroom, stream=None):
    user = User.objects.create_user(email=email, password='x', role='student')
    return StudentProfile.objects.create(user=user, student_id=student_id, classroom=classroom, stream=stream)


class SeatingChartServiceTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.grade = GradeLevel.objects.create(name='Form 2', short_name='F2', education_level='secondary', order=2)
        cls.classroom = Classroom.objects.create(name='2C', grade_level=cls.grade, stream='general', academic_year='2026')
        cls.students = [
            make_student(f'seat{i}@test.tz', f'SEAT{i:03d}', cls.classroom) for i in range(9)
        ]

    def test_grid_seats_every_active_student(self):
        chart = services.generate_seating_chart(self.classroom)
        self.assertEqual(chart['seated_count'], 9)
        self.assertEqual(chart['rows'] * chart['cols'], chart['capacity'])
        self.assertGreaterEqual(chart['capacity'], 9)

    def test_explicit_dimensions_are_respected(self):
        chart = services.generate_seating_chart(self.classroom, rows=3, cols=3)
        self.assertEqual(chart['rows'], 3)
        self.assertEqual(chart['cols'], 3)

    def test_avoid_pair_kept_apart_when_grid_has_room(self):
        a, b = self.students[0], self.students[1]
        PeerConstraint.objects.create(
            classroom=self.classroom, student_a=a, student_b=b,
            constraint_type=PeerConstraint.ConstraintType.AVOID,
        )
        chart = services.generate_seating_chart(self.classroom, rows=3, cols=3)
        pos = {}
        for seat in chart['seats']:
            if seat['student']:
                pos[seat['student']['id']] = (seat['row'], seat['col'])
        ra, ca = pos[a.id]
        rb, cb = pos[b.id]
        adjacent = (abs(ra - rb) + abs(ca - cb)) == 1
        self.assertFalse(adjacent, 'AVOID pair should not be seated in adjacent desks')
        self.assertEqual(chart['warnings'], [])

    def test_prefer_pair_seated_adjacent_when_possible(self):
        a, b = self.students[2], self.students[3]
        PeerConstraint.objects.create(
            classroom=self.classroom, student_a=a, student_b=b,
            constraint_type=PeerConstraint.ConstraintType.PREFER,
        )
        chart = services.generate_seating_chart(self.classroom, rows=3, cols=3)
        pos = {}
        for seat in chart['seats']:
            if seat['student']:
                pos[seat['student']['id']] = (seat['row'], seat['col'])
        ra, ca = pos[a.id]
        rb, cb = pos[b.id]
        adjacent = (abs(ra - rb) + abs(ca - cb)) == 1
        self.assertTrue(adjacent, 'PREFER pair should be seated in adjacent desks when the grid allows it')

    def test_stream_filter_only_seats_that_streams_students(self):
        stream = Stream.objects.create(classroom=self.classroom, name='A')
        streamed_student = make_student('seat_streamed@test.tz', 'SEATSTREAM', self.classroom, stream=stream)
        chart = services.generate_seating_chart(self.classroom, stream_id=stream.id)
        self.assertEqual(chart['seated_count'], 1)
        self.assertEqual(chart['seats'][0]['student']['id'], streamed_student.id)

    def test_group_filter_only_seats_that_groups_members(self):
        group = StudentGroup.objects.create(classroom=self.classroom, name='Alpha', academic_year='2026')
        GroupMembership.objects.create(group=group, student=self.students[0])
        GroupMembership.objects.create(group=group, student=self.students[1])
        chart = services.generate_seating_chart(self.classroom, group_id=group.id)
        self.assertEqual(chart['seated_count'], 2)

    def test_grid_too_small_leaves_students_unseated(self):
        chart = services.generate_seating_chart(self.classroom, rows=2, cols=2)  # capacity 4, 9 students
        self.assertEqual(chart['capacity'], 4)
        self.assertEqual(chart['seated_count'], 4)
        self.assertEqual(len(chart['unseated']), 5)

    def test_inactive_students_are_excluded(self):
        inactive = make_student('seat_inactive@test.tz', 'SEATINACT', self.classroom)
        inactive.is_active = False
        inactive.save()
        chart = services.generate_seating_chart(self.classroom)
        seated_ids = {s['student']['id'] for s in chart['seats'] if s['student']}
        self.assertNotIn(inactive.id, seated_ids)


class SeatingChartViewTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.subject = Subject.objects.create(name='Seating Maths', code='SEATM')
        cls.grade = GradeLevel.objects.create(name='Form 1', short_name='F1', education_level='secondary', order=1)
        cls.classroom = Classroom.objects.create(name='1D', grade_level=cls.grade, stream='general', academic_year='2026')
        for i in range(4):
            make_student(f'seatview{i}@test.tz', f'SEATV{i:03d}', cls.classroom)

        cls.teacher_a = User.objects.create_user(email='seat_teacher_a@test.tz', password='x', role='teacher')
        cls.teacher_b = User.objects.create_user(email='seat_teacher_b@test.tz', password='x', role='teacher')
        TeacherAssignment.objects.create(teacher=cls.teacher_b, subject=cls.subject, classroom=cls.classroom)

    def test_assigned_teacher_can_fetch_chart(self):
        self.client.force_authenticate(self.teacher_b)
        resp = self.client.get(f'/api/groups/classroom/{self.classroom.id}/seating-chart/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['seated_count'], 4)

    def test_unassigned_teacher_is_blocked(self):
        self.client.force_authenticate(self.teacher_a)
        resp = self.client.get(f'/api/groups/classroom/{self.classroom.id}/seating-chart/')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_invalid_rows_cols_rejected(self):
        self.client.force_authenticate(self.teacher_b)
        resp = self.client.get(f'/api/groups/classroom/{self.classroom.id}/seating-chart/?rows=0')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_stream_from_another_classroom_rejected(self):
        other_classroom = Classroom.objects.create(name='1E', grade_level=self.grade, stream='general', academic_year='2026')
        other_stream = Stream.objects.create(classroom=other_classroom, name='X')
        self.client.force_authenticate(self.teacher_b)
        resp = self.client.get(f'/api/groups/classroom/{self.classroom.id}/seating-chart/?stream_id={other_stream.id}')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
