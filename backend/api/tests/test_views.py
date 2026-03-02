from PyPDF2 import PdfReader, PdfWriter
from django.test import TestCase
from rest_framework.test import APIClient
from django.core.files.uploadedfile import SimpleUploadedFile

from api.models import GroupMember
from io import BytesIO
from reportlab.pdfgen import canvas


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


class UploadEndpointTest(TestCase):
    def setUp(self):
        self.client = APIClient()

    def _post_file(self, name, content, content_type):
        f = SimpleUploadedFile(name, content, content_type=content_type)
        return self.client.post("/api/upload/", {"file": f}, format="multipart")

    def generate_valid_pdf_bytes(self):
        buffer = BytesIO()
        p = canvas.Canvas(buffer)
        p.drawString(100, 750, "Hello PDF")
        p.save()
        buffer.seek(0)
        return buffer.read()

    def generate_private_pdf_bytes(self, password="secret"):
        valid_pdf_bytes = self.generate_valid_pdf_bytes()

        input_buffer = BytesIO(valid_pdf_bytes)
        output_buffer = BytesIO()

        reader = PdfReader(input_buffer)
        writer = PdfWriter()

        for page in reader.pages:
            writer.add_page(page)

        writer.encrypt(password)
        writer.write(output_buffer)

        output_buffer.seek(0)
        return output_buffer.read()

    def test_upload_pdf_success(self):
        pdf_doc = self.generate_valid_pdf_bytes()
        resp = self._post_file("doc.pdf", pdf_doc, "application/pdf")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("path", resp.data)
        self.assertTrue(resp.data["path"].endswith("doc.pdf"))

    def test_upload_xls_success(self):
        resp = self._post_file("sheet.xls", b"data", "application/vnd.ms-excel")
        self.assertEqual(resp.status_code, 200)

    def test_upload_xlsx_success(self):
        resp = self._post_file(
            "sheet.xlsx",
            b"data",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        self.assertEqual(resp.status_code, 200)

    def test_upload_unsupported_type(self):
        resp = self._post_file("note.txt", b"hello", "text/plain")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data["status"], "error")
        self.assertIn("message", resp.data)

    def test_upload_no_file(self):
        resp = self.client.post("/api/upload/", {}, format="multipart")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data["status"], "error")
        self.assertIn("message", resp.data)

    def test_file_header_not_pdf_with_extension_pdf(self):
        resp = self._post_file("doc.pdf", b"data", "application/pdf")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data["status"], "error")
        self.assertIn("message", resp.data)

    def test_file_is_corrupt_pdf(self):
        pdf_doc = self.generate_valid_pdf_bytes()
        corrupt_pdf = pdf_doc[:20]

        resp = self._post_file("corrupt.pdf", corrupt_pdf, "application/pdf")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data["status"], "error")
        self.assertIn("message", resp.data)

    def test_upload_file_too_large(self):
        big_content = b"a" * (11 * 1024 * 1024)
        resp = self._post_file("big.pdf", big_content, "application/pdf")

    def test_file_is_private_pdf(self):
        private_pdf = self.generate_private_pdf_bytes(password="1234")

        resp = self._post_file("private.pdf", private_pdf, "application/pdf")

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
