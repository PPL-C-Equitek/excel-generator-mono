from django.test import TestCase
from rest_framework.test import APIClient

from api.models import GroupMember


class BaseApiViewTest(TestCase):
    def setUp(self):
        self.client = APIClient()


class HealthCheckViewTest(BaseApiViewTest):
    def test_health_endpoint_returns_200(self):
        response = self.client.get("/api/health/")
        self.assertEqual(response.status_code, 200)

    def test_health_endpoint_returns_correct_data(self):
        response = self.client.get("/api/health/")
        self.assertEqual(response.data["status"], "ok")
        self.assertEqual(response.data["message"], "Backend is running!")

    def test_health_endpoint_rejects_post(self):
        response = self.client.post("/api/health/")
        self.assertEqual(response.status_code, 405)


class AboutViewTest(BaseApiViewTest):
    def test_about_endpoint_returns_200(self):
        response = self.client.get("/api/about/")
        self.assertEqual(response.status_code, 200)

    def test_about_endpoint_returns_correct_data(self):
        response = self.client.get("/api/about/")
        self.assertEqual(response.data["team"], "PPL C - Equitek")
        self.assertEqual(response.data["project"], "Excel Generator")

    def test_about_endpoint_rejects_post(self):
        response = self.client.post("/api/about/")
        self.assertEqual(response.status_code, 405)


class MembersViewTest(BaseApiViewTest):
    @classmethod
    def setUpTestData(cls):
        GroupMember.objects.create(npm="2306152260", name="Steven Setiawan")
        GroupMember.objects.create(npm="2306152172", name="Siti Shofi Nadhifa")

    def test_members_endpoint_returns_200(self):
        response = self.client.get("/api/members/")
        self.assertEqual(response.status_code, 200)

    def test_members_endpoint_returns_group_and_members(self):
        response = self.client.get("/api/members/")
        self.assertEqual(response.data["group"], "Kelompok 7")
        self.assertEqual(len(response.data["members"]), 2)
        self.assertEqual(response.data["members"][0]["npm"], "2306152172")
        self.assertEqual(response.data["members"][0]["name"], "Siti Shofi Nadhifa")

    def test_members_endpoint_rejects_post(self):
        response = self.client.post("/api/members/")
        self.assertEqual(response.status_code, 405)
