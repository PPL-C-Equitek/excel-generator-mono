from django.test import TestCase
from rest_framework.test import APIClient

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
