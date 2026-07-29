"""
Standalone verification for the 5 intelligence-layer analytics features.
Run with: python manage.py test mathapi.apps.analytics.test_intelligence -v 2
Uses Django's isolated test database — never touches db.sqlite3.
"""
import datetime
from django.test import TestCase
from django.contrib.auth import get_user_model

from mathapi.apps.accounts.models import Subject, TeacherAssignment
from mathapi.apps.students.models import GradeLevel, Classroom, StudentProfile
from mathapi.apps.exams.models import MathTopic, Exam, ExamTopicWeight, ExamScore, TopicScore, ScoreEditLog
from mathapi.apps.analytics import services

User = get_user_model()


class IntelligenceLayerTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.subject = Subject.objects.create(name='Test Mathematics', code='TMTH')

        cls.teacher_a = User.objects.create_user(email='teacher.a@test.tz', password='x', first_name='Amina', last_name='Juma', role='teacher')
        cls.teacher_b = User.objects.create_user(email='teacher.b@test.tz', password='x', first_name='Baraka', last_name='Mwita', role='teacher')
        cls.teacher_c = User.objects.create_user(email='teacher.c@test.tz', password='x', first_name='Chiku', last_name='Said', role='teacher')
        cls.teacher_d = User.objects.create_user(email='teacher.d@test.tz', password='x', first_name='Daudi', last_name='Nassoro', role='teacher')

        cls.grade = GradeLevel.objects.create(name='Form Two', short_name='F2', education_level='secondary', order=2)
        cls.classroom = Classroom.objects.create(name='2A', grade_level=cls.grade, stream='A', academic_year='2026')
        cls.classroom.teachers.add(cls.teacher_a, cls.teacher_b, cls.teacher_c, cls.teacher_d)

        TeacherAssignment.objects.create(teacher=cls.teacher_a, classroom=cls.classroom, subject=cls.subject)
        TeacherAssignment.objects.create(teacher=cls.teacher_b, classroom=cls.classroom, subject=cls.subject)
        TeacherAssignment.objects.create(teacher=cls.teacher_c, classroom=cls.classroom, subject=cls.subject)
        TeacherAssignment.objects.create(teacher=cls.teacher_d, classroom=cls.classroom, subject=cls.subject)

        cls.topic_fractions = MathTopic.objects.create(subject=cls.subject, name='Fractions', order=1)
        cls.topic_algebra = MathTopic.objects.create(subject=cls.subject, name='Algebra', order=2)

        # 12 students: 6 weak in fractions (also weak in algebra -> dependency), 6 strong in both
        cls.students = []
        for i in range(12):
            u = User.objects.create_user(email=f'student{i}@test.tz', password='x', first_name=f'Student{i}', last_name='Test', role='student')
            sp = StudentProfile.objects.create(user=u, student_id=f'S{i:03d}', classroom=cls.classroom)
            cls.students.append(sp)

        # Two exams, graded by two different teachers (for the consistency check)
        cls.exam1 = Exam.objects.create(
            title='Monthly Test 1', exam_type='monthly_test', term='term_1', academic_year='2026',
            exam_date=datetime.date(2026, 2, 1), max_score=100, passing_score=30,
            subject=cls.subject, created_by=cls.teacher_a, is_published=True,
        )
        cls.exam1.classrooms.add(cls.classroom)
        ExamTopicWeight.objects.create(exam=cls.exam1, topic=cls.topic_fractions, max_marks=50, weight_percentage=50)
        ExamTopicWeight.objects.create(exam=cls.exam1, topic=cls.topic_algebra, max_marks=50, weight_percentage=50)

        cls.exam2 = Exam.objects.create(
            title='Monthly Test 2', exam_type='monthly_test', term='term_1', academic_year='2026',
            exam_date=datetime.date(2026, 3, 1), max_score=100, passing_score=30,
            subject=cls.subject, created_by=cls.teacher_a, is_published=True,
        )
        cls.exam2.classrooms.add(cls.classroom)
        ExamTopicWeight.objects.create(exam=cls.exam2, topic=cls.topic_fractions, max_marks=50, weight_percentage=50)
        ExamTopicWeight.objects.create(exam=cls.exam2, topic=cls.topic_algebra, max_marks=50, weight_percentage=50)

        # Exam 3 is created (graded) by teacher_b, who marks Algebra ~15pts more
        # leniently than teacher_a on the same material -> consistency flag.
        cls.exam3 = Exam.objects.create(
            title='Monthly Test 3', exam_type='monthly_test', term='term_1', academic_year='2026',
            exam_date=datetime.date(2026, 4, 1), max_score=100, passing_score=30,
            subject=cls.subject, created_by=cls.teacher_b, is_published=True,
        )
        cls.exam3.classrooms.add(cls.classroom)
        ExamTopicWeight.objects.create(exam=cls.exam3, topic=cls.topic_fractions, max_marks=50, weight_percentage=50)
        ExamTopicWeight.objects.create(exam=cls.exam3, topic=cls.topic_algebra, max_marks=50, weight_percentage=50)

        cls.exam4 = Exam.objects.create(
            title='Monthly Test 4', exam_type='monthly_test', term='term_1', academic_year='2026',
            exam_date=datetime.date(2026, 4, 15), max_score=100, passing_score=30,
            subject=cls.subject, created_by=cls.teacher_c, is_published=True,
        )
        cls.exam4.classrooms.add(cls.classroom)
        ExamTopicWeight.objects.create(exam=cls.exam4, topic=cls.topic_fractions, max_marks=50, weight_percentage=50)
        ExamTopicWeight.objects.create(exam=cls.exam4, topic=cls.topic_algebra, max_marks=50, weight_percentage=50)

        cls.exam5 = Exam.objects.create(
            title='Monthly Test 5', exam_type='monthly_test', term='term_1', academic_year='2026',
            exam_date=datetime.date(2026, 4, 20), max_score=100, passing_score=30,
            subject=cls.subject, created_by=cls.teacher_d, is_published=True,
        )
        cls.exam5.classrooms.add(cls.classroom)
        ExamTopicWeight.objects.create(exam=cls.exam5, topic=cls.topic_fractions, max_marks=50, weight_percentage=50)
        ExamTopicWeight.objects.create(exam=cls.exam5, topic=cls.topic_algebra, max_marks=50, weight_percentage=50)

        for i, sp in enumerate(cls.students):
            weak = i < 6
            for exam in (cls.exam1, cls.exam2, cls.exam3, cls.exam4, cls.exam5):
                grader = exam.created_by
                algebra_bonus = 15 if grader == cls.teacher_b else 0
                frac_score = 15 if weak else 45  # out of 50
                alg_score = min(50, (15 if weak else 40) + algebra_bonus)
                total = frac_score + alg_score
                es = ExamScore.objects.create(exam=exam, student=sp, score=total, entered_by=grader)
                TopicScore.objects.create(exam_score=es, topic=cls.topic_fractions, score=frac_score, max_marks=50)
                TopicScore.objects.create(exam_score=es, topic=cls.topic_algebra, score=alg_score, max_marks=50)

        # Integrity: a fail->pass edit and a large jump, both by teacher_a
        target_score = ExamScore.objects.filter(exam=cls.exam2, student=cls.students[0]).first()
        ScoreEditLog.objects.create(exam_score=target_score, changed_by=cls.teacher_a, old_score=25, new_score=target_score.score, reason='Re-marked')
        ScoreEditLog.objects.create(exam_score=target_score, changed_by=cls.teacher_a, old_score=10, new_score=60, reason='Recount')

    def test_integrity_flags(self):
        result = services.get_integrity_flags()
        print('\n[integrity]', result)
        self.assertGreaterEqual(result['boundary_crossing_count'], 1)
        self.assertGreaterEqual(result['large_jump_count'], 1)
        self.assertTrue(any(r['teacher_id'] == self.teacher_a.id for r in result['editor_rates']))

    def test_student_risk_score(self):
        weak_student = self.students[0]
        strong_student = self.students[6]
        weak_risk = services.get_student_risk_score(weak_student.id)
        strong_risk = services.get_student_risk_score(strong_student.id)
        print('\n[weak risk]', weak_risk)
        print('[strong risk]', strong_risk)
        self.assertIsNotNone(weak_risk['risk_score'])
        self.assertGreater(weak_risk['risk_score'], strong_risk['risk_score'])

    def test_classroom_risk_scores(self):
        result = services.get_classroom_risk_scores(self.classroom.id)
        print('\n[classroom risk] n=', len(result['students']))
        self.assertEqual(len(result['students']), 12)
        scores = [s['risk_score'] for s in result['students'] if s['risk_score'] is not None]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_topic_dependency_chains(self):
        result = services.get_topic_dependency_chains(self.classroom.id)
        print('\n[dependency chains]', result['dependency_chains'])
        self.assertTrue(len(result['dependency_chains']) >= 1)
        chain = result['dependency_chains'][0]
        self.assertGreater(chain['lift'], 1.0)

    def test_teacher_grading_consistency(self):
        result = services.get_teacher_grading_consistency(subject_id=self.subject.id)
        print('\n[teacher consistency]', result['flags'])
        self.assertGreaterEqual(result['flag_count'], 1)
        lenient_flags = [f for f in result['flags'] if f['direction'] == 'lenient' and f['teacher_id'] == self.teacher_b.id]
        self.assertTrue(len(lenient_flags) >= 1)

    def test_grade_boundary_whatif(self):
        result = services.get_grade_boundary_whatif(self.students[0].id)
        print('\n[whatif]', result)
        self.assertIn('predicted_average', result)
