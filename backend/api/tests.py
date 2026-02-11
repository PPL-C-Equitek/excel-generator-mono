from django.test import TestCase
from django.core.management import call_command
from rest_framework.test import APIClient
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


class MembersTest(TestCase):
    def setUp(self):
        GroupMember.objects.create(npm='2306152172', name='Siti Shofi Nadhifa')
        GroupMember.objects.create(npm='2306152260', name='Steven Setiawan')

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


class SeedMembersCommandTest(TestCase):
    def test_seed_members_creates_expected_records(self):
        call_command('seed_members')
        self.assertEqual(GroupMember.objects.count(), 7)

    def test_seed_members_is_idempotent(self):
        call_command('seed_members')
        call_command('seed_members')
        self.assertEqual(GroupMember.objects.count(), 7)
