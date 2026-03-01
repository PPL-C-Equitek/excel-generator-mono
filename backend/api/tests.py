from django.test import TestCase
from django.core.management import call_command
from rest_framework.test import APIClient
from django.core.files.uploadedfile import SimpleUploadedFile
from .models import GroupMember


class HealthCheckTest(TestCase):
    def test_health_endpoint_returns_200(self):
        client = APIClient()
        response = client.get('/api/health/')
        self.assertEqual(response.status_code, 200)

    def test_health_endpoint_returns_correct_data(self):
        client = APIClient()
        response = client.get('/api/health/')
        self.assertEqual(response.data['status'], 'ok')
        self.assertEqual(response.data['message'], 'Backend is running!')

    def test_health_endpoint_rejects_post(self):
        client = APIClient()
        response = client.post('/api/health/')
        self.assertEqual(response.status_code, 405)


class AboutTest(TestCase):
    def test_about_endpoint_returns_200(self):
        client = APIClient()
        response = client.get('/api/about/')
        self.assertEqual(response.status_code, 200)

    def test_about_endpoint_returns_correct_data(self):
        client = APIClient()
        response = client.get('/api/about/')
        self.assertEqual(response.data['team'], 'PPL C - Equitek')
        self.assertEqual(response.data['project'], 'Excel Generator')

    def test_about_endpoint_rejects_post(self):
        client = APIClient()
        response = client.post('/api/about/')
        self.assertEqual(response.status_code, 405)


class MembersTest(TestCase):
    def setUp(self):
        GroupMember.objects.create(npm='2306152260', name='Steven Setiawan')
        GroupMember.objects.create(npm='2306152172', name='Siti Shofi Nadhifa')

    def test_members_endpoint_returns_200(self):
        client = APIClient()
        response = client.get('/api/members/')
        self.assertEqual(response.status_code, 200)

    def test_members_endpoint_returns_group_and_members(self):
        client = APIClient()
        response = client.get('/api/members/')
        self.assertEqual(response.data['group'], 'Kelompok 7')
        self.assertEqual(len(response.data['members']), 2)
        self.assertEqual(response.data['members'][0]['npm'], '2306152172')
        self.assertEqual(response.data['members'][0]['name'], 'Siti Shofi Nadhifa')

    def test_members_endpoint_rejects_post(self):
        client = APIClient()
        response = client.post('/api/members/')
        self.assertEqual(response.status_code, 405)

    def test_group_member_string_representation(self):
        member = GroupMember.objects.get(npm='2306152172')
        self.assertEqual(str(member), '2306152172 - Siti Shofi Nadhifa')


class UploadEndpointTest(TestCase):
    def setUp(self):
        self.client = APIClient()

    def _post_file(self, name, content, content_type):
        f = SimpleUploadedFile(name, content, content_type=content_type)
        return self.client.post('/api/upload/', {'file': f}, format='multipart')

    def test_upload_pdf_success(self):
        resp = self._post_file('doc.pdf', b'hello', 'application/pdf')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('path', resp.data)
        self.assertTrue(resp.data['path'].endswith('doc.pdf'))

    def test_upload_xls_success(self):
        resp = self._post_file('sheet.xls', b'data', 'application/vnd.ms-excel')
        self.assertEqual(resp.status_code, 200)

    def test_upload_xlsx_success(self):
        resp = self._post_file('sheet.xlsx', b'data', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        self.assertEqual(resp.status_code, 200)

    def test_upload_unsupported_type(self):
        resp = self._post_file('note.txt', b'hello', 'text/plain')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data["status"], "error")
        self.assertIn("message", resp.data)

    def test_upload_no_file(self):
        resp = self.client.post('/api/upload/', {}, format='multipart')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data["status"], "error")
        self.assertIn("message", resp.data)

    def test_upload_file_too_large(self):
        big_content = b"a" * (11 * 1024 * 1024)
        resp = self._post_file("big.pdf", big_content, "application/pdf")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data["status"], "error")
        self.assertIn("message", resp.data)

    def test_upload_file_exact_10mb_allowed(self):
        exact_content = b"a" * (10 * 1024 * 1024)
        resp = self._post_file("exact.pdf", exact_content, "application/pdf")
        self.assertEqual(resp.status_code, 200)

    def test_upload_file_less_than_10mb_allowed(self):
        less_content = b"a" * (5 * 1024 * 1024)
        resp = self._post_file("small.pdf", less_content, "application/pdf")
        self.assertEqual(resp.status_code, 200)
    

class SeedMembersCommandTest(TestCase):
    def test_seed_members_creates_expected_records(self):
        call_command('seed_members')
        self.assertEqual(GroupMember.objects.count(), 7)

    def test_seed_members_is_idempotent(self):
        call_command('seed_members')
        call_command('seed_members')
        self.assertEqual(GroupMember.objects.count(), 7)
