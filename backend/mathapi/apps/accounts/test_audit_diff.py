"""
Tests for AuditMiddleware's field-level diff capture.
Run with: python manage.py test mathapi.apps.accounts.test_audit_diff -v 2
"""
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model

from .models import AuditLog, Subject

User = get_user_model()


class AuditDiffTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(email='admin@audit.tz', password='x', role='super_admin')

    def setUp(self):
        self.client.force_authenticate(self.admin)

    def test_create_records_new_field_values(self):
        resp = self.client.post('/api/auth/subjects/', {'name': 'Diff Subject', 'code': 'DIFS'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

        log = AuditLog.objects.filter(action=AuditLog.Action.CREATE, model_name='subject').order_by('-timestamp').first()
        self.assertIsNotNone(log)
        self.assertEqual(log.object_id, str(resp.data['id']))
        self.assertIsNotNone(log.changes)
        self.assertEqual(log.changes['name']['old'], None)
        self.assertEqual(log.changes['name']['new'], 'Diff Subject')

    def test_update_records_old_and_new_values(self):
        subject = Subject.objects.create(name='Before Name', code='BFR1')
        resp = self.client.patch(f'/api/auth/subjects/{subject.id}/', {'name': 'After Name'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        log = AuditLog.objects.filter(action=AuditLog.Action.UPDATE, model_name='subject', object_id=str(subject.id)).order_by('-timestamp').first()
        self.assertIsNotNone(log)
        self.assertIsNotNone(log.changes)
        self.assertEqual(log.changes['name'], {'old': 'Before Name', 'new': 'After Name'})
        # Untouched fields shouldn't show up as "changed".
        self.assertNotIn('code', log.changes)

    def test_delete_records_final_field_values(self):
        subject = Subject.objects.create(name='Doomed Subject', code='DOOM')
        subject_id = subject.id
        resp = self.client.delete(f'/api/auth/subjects/{subject_id}/')
        self.assertIn(resp.status_code, (status.HTTP_200_OK, status.HTTP_204_NO_CONTENT))

        log = AuditLog.objects.filter(action=AuditLog.Action.DELETE, model_name='subject', object_id=str(subject_id)).order_by('-timestamp').first()
        self.assertIsNotNone(log)
        self.assertIsNotNone(log.changes)
        self.assertEqual(log.changes['name'], {'old': 'Doomed Subject', 'new': None})

    def test_no_op_update_produces_no_changes(self):
        subject = Subject.objects.create(name='Same Name', code='SAME')
        resp = self.client.patch(f'/api/auth/subjects/{subject.id}/', {'name': 'Same Name'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        log = AuditLog.objects.filter(action=AuditLog.Action.UPDATE, model_name='subject', object_id=str(subject.id)).order_by('-timestamp').first()
        self.assertIsNotNone(log)
        self.assertIsNone(log.changes)

    def test_password_never_appears_in_a_diff(self):
        resp = self.client.post('/api/auth/users/', {
            'email': 'newteacher@audit.tz', 'password': 'SuperSecret123!', 'role': 'teacher',
            'first_name': 'New', 'last_name': 'Teacher',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        log = AuditLog.objects.filter(action=AuditLog.Action.CREATE, model_name='user', object_id=str(resp.data['id'])).order_by('-timestamp').first()
        self.assertIsNotNone(log)
        self.assertIsNotNone(log.changes)
        self.assertNotIn('password', log.changes)
