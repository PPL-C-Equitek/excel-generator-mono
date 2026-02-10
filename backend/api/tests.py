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