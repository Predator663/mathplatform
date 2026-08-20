"""
Tests for the advanced audit-log endpoints: facets, stats, single/batch
PDF card exports, CSV export, and — most importantly — that every one of
them is restricted to super_admin, exactly like the underlying list view.

Run with: python manage.py test mathapi.apps.accounts.test_audit_advanced -v 2
"""
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model

from .models import AuditLog

User = get_user_model()


class AuditLogAdvancedEndpointsTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(email='admin_adv@audit.tz', password='x', role='super_admin')
        cls.teacher = User.objects.create_user(email='teacher_adv@audit.tz', password='x', role='teacher')

        cls.log1 = AuditLog.objects.create(
            user=cls.admin, action=AuditLog.Action.CREATE, model_name='subject', object_id='1',
            description='POST /api/auth/subjects/', ip_address='10.0.0.1',
            changes={'name': {'old': None, 'new': 'Physics'}, 'code': {'old': None, 'new': 'PHY'}},
        )
        cls.log2 = AuditLog.objects.create(
            user=cls.teacher, action=AuditLog.Action.UPDATE, model_name='subject', object_id='1',
            description='PATCH /api/auth/subjects/1/', ip_address='10.0.0.2',
            changes={'name': {'old': 'Physics', 'new': 'Applied Physics'}},
        )
        cls.log3 = AuditLog.objects.create(
            user=cls.teacher, action=AuditLog.Action.DELETE, model_name='exam', object_id='9',
            description='DELETE /api/exams/exams/9/', ip_address='10.0.0.2', changes=None,
        )

    # ── Access control ───────────────────────────────────────────────

    def test_all_endpoints_reject_unauthenticated(self):
        urls = [
            '/api/auth/audit-log/', '/api/auth/audit-log/facets/', '/api/auth/audit-log/stats/',
            f'/api/auth/audit-log/{self.log1.id}/card/pdf/',
            '/api/auth/audit-log/export/cards/pdf/', '/api/auth/audit-log/export/csv/',
        ]
        for url in urls:
            res = self.client.get(url)
            self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED, url)

    def test_all_endpoints_reject_non_super_admin(self):
        self.client.force_authenticate(self.teacher)
        urls = [
            '/api/auth/audit-log/', '/api/auth/audit-log/facets/', '/api/auth/audit-log/stats/',
            f'/api/auth/audit-log/{self.log1.id}/card/pdf/',
            '/api/auth/audit-log/export/cards/pdf/', '/api/auth/audit-log/export/csv/',
        ]
        for url in urls:
            res = self.client.get(url)
            self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN, url)

    # ── Facets ───────────────────────────────────────────────────────

    def test_facets_returns_distinct_models_and_users(self):
        self.client.force_authenticate(self.admin)
        res = self.client.get('/api/auth/audit-log/facets/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn('subject', res.data['models'])
        self.assertIn('exam', res.data['models'])
        user_ids = {u['id'] for u in res.data['users']}
        self.assertIn(self.admin.id, user_ids)
        self.assertIn(self.teacher.id, user_ids)

    # ── Stats ────────────────────────────────────────────────────────

    def test_stats_reflects_current_filters(self):
        self.client.force_authenticate(self.admin)
        res = self.client.get('/api/auth/audit-log/stats/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['total'], 3)
        self.assertEqual(res.data['by_action']['create'], 1)
        self.assertEqual(res.data['by_action']['update'], 1)
        self.assertEqual(res.data['by_action']['delete'], 1)

        res_scoped = self.client.get('/api/auth/audit-log/stats/', {'model_name': 'exam'})
        self.assertEqual(res_scoped.data['total'], 1)
        self.assertEqual(res_scoped.data['by_action']['delete'], 1)
        self.assertEqual(res_scoped.data['by_action']['create'], 0)

    # ── Object-id / IP filters on the list endpoint ─────────────────

    def test_list_filters_by_object_id_and_ip(self):
        self.client.force_authenticate(self.admin)
        res = self.client.get('/api/auth/audit-log/', {'model_name': 'subject', 'object_id': '1'})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['count'], 2)  # log1 + log2, both object_id=1

        res_ip = self.client.get('/api/auth/audit-log/', {'ip_address': '10.0.0.1'})
        self.assertEqual(res_ip.data['count'], 1)

    # ── PDF card exports ─────────────────────────────────────────────

    def test_single_card_pdf_download(self):
        self.client.force_authenticate(self.admin)
        res = self.client.get(f'/api/auth/audit-log/{self.log1.id}/card/pdf/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res['Content-Type'], 'application/pdf')
        content = b''.join(res.streaming_content) if res.streaming else res.content
        self.assertTrue(content.startswith(b'%PDF'))

    def test_batch_card_pdf_download(self):
        self.client.force_authenticate(self.admin)
        res = self.client.get('/api/auth/audit-log/export/cards/pdf/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res['Content-Type'], 'application/pdf')

    def test_batch_card_pdf_rejects_when_over_limit(self):
        AuditLog.objects.bulk_create([
            AuditLog(user=self.admin, action=AuditLog.Action.LOGIN, model_name='', description='login')
            for _ in range(160)
        ])
        self.client.force_authenticate(self.admin)
        res = self.client.get('/api/auth/audit-log/export/cards/pdf/')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_batch_card_pdf_404s_on_empty_filter(self):
        self.client.force_authenticate(self.admin)
        res = self.client.get('/api/auth/audit-log/export/cards/pdf/', {'model_name': 'does-not-exist'})
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    # ── CSV export ───────────────────────────────────────────────────

    def test_csv_export_contains_all_rows_and_header(self):
        self.client.force_authenticate(self.admin)
        res = self.client.get('/api/auth/audit-log/export/csv/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res['Content-Type'], 'text/csv')
        body = res.content.decode('utf-8')
        self.assertIn('ID,Timestamp,User Name,User Email,Action,Model', body)
        self.assertEqual(body.strip().count('\n'), 3)  # header + 3 rows - 1 (no trailing after last)
