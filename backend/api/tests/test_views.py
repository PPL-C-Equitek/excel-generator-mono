from PyPDF2 import PdfReader, PdfWriter
from django.test import TestCase
from rest_framework.test import APIClient
from django.core.files.uploadedfile import SimpleUploadedFile
from unittest.mock import patch

from api.models import GroupMember
from io import BytesIO
from reportlab.pdfgen import canvas
from openpyxl import Workbook


class BaseApiViewTest(TestCase):
    def setUp(self):
        self.client = APIClient()


class HealthCheckViewTest(BaseApiViewTest):
    def test_health_endpoint_returns_200(self):
        response = self.client.get("/health/")
        self.assertEqual(response.status_code, 200)

    def test_health_endpoint_returns_correct_data(self):
        response = self.client.get("/health/")
        self.assertEqual(response.data["status"], "ok")
        self.assertEqual(response.data["message"], "Backend is running!")

    def test_health_endpoint_rejects_post(self):
        response = self.client.post("/health/")
        self.assertEqual(response.status_code, 405)


class AboutViewTest(BaseApiViewTest):
    def test_about_endpoint_returns_200(self):
        response = self.client.get("/about/")
        self.assertEqual(response.status_code, 200)

    def test_about_endpoint_returns_correct_data(self):
        response = self.client.get("/about/")
        self.assertEqual(response.data["team"], "PPL C - Equitek")
        self.assertEqual(response.data["project"], "Excel Generator")

    def test_about_endpoint_rejects_post(self):
        response = self.client.post("/about/")
        self.assertEqual(response.status_code, 405)


class MembersViewTest(BaseApiViewTest):
    @classmethod
    def setUpTestData(cls):
        GroupMember.objects.create(npm="2306152260", name="Steven Setiawan")
        GroupMember.objects.create(npm="2306152172", name="Siti Shofi Nadhifa")

    def test_members_endpoint_returns_200(self):
        response = self.client.get("/members/")
        self.assertEqual(response.status_code, 200)

    def test_members_endpoint_returns_group_and_members(self):
        response = self.client.get("/members/")
        self.assertEqual(response.data["group"], "Kelompok 7")
        self.assertEqual(len(response.data["members"]), 2)
        self.assertEqual(response.data["members"][0]["npm"], "2306152172")
        self.assertEqual(response.data["members"][0]["name"], "Siti Shofi Nadhifa")

    def test_members_endpoint_rejects_post(self):
        response = self.client.post("/members/")
        self.assertEqual(response.status_code, 405)


class UploadEndpointTest(TestCase):
    def setUp(self):
        self.client = APIClient()

    def _post_file(self, name, content, content_type):
        f = SimpleUploadedFile(name, content, content_type=content_type)
        return self.client.post("/upload/", {"file": f}, format="multipart")

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
    
    def generate_valid_xlsx_bytes(self):
        buffer = BytesIO()
        wb = Workbook()
        ws = wb.active
        ws["A1"] = "Hello"
        wb.save(buffer)
        buffer.seek(0)
        return buffer.read()

    def test_upload_pdf_success(self):
        pdf_doc = self.generate_valid_pdf_bytes()
        resp = self._post_file("doc.pdf", pdf_doc, "application/pdf")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["status"], "success")
        self.assertEqual(resp.data["filename"], "doc.pdf")

    def test_upload_xls_success(self):
        xls_content = b"\xD0\xCF\x11\xE0" + b"\x00" * 100

        resp = self._post_file(
            "sheet.xls",
            xls_content,
            "application/vnd.ms-excel",
        )

        self.assertEqual(resp.status_code, 200)

    def test_upload_xlsx_success(self):
        xlsx_content = b"PK\x03\x04" + b"\x00" * 100

        resp = self._post_file(
            "sheet.xlsx",
            xlsx_content,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        self.assertEqual(resp.status_code, 200)

    def test_upload_unsupported_type(self):
        resp = self._post_file("note.txt", b"hello", "text/plain")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data["status"], "error")
        self.assertIn("message", resp.data)

    def test_upload_no_file(self):
        resp = self.client.post("/upload/", {}, format="multipart")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data["status"], "error")
        self.assertIn("message", resp.data)

    def test_upload_response_does_not_expose_path(self):
        pdf_doc = self.generate_valid_pdf_bytes()

        resp = self._post_file(
            "doc.pdf",
            pdf_doc,
            "application/pdf"
        )

        self.assertEqual(resp.status_code, 200)
        self.assertNotIn("path", resp.data)

    def test_invalid_file_path_detection(self):
        pdf_doc = self.generate_valid_pdf_bytes()

        with patch(
            "file_processing.services.upload_service.os.path.abspath"
        ) as mock_abspath:

            def fake_abspath(path):
                if "doc.pdf" in path:
                    return "/evil/path/file.pdf"
                return "/safe/base"

            mock_abspath.side_effect = fake_abspath

            with self.assertRaises(ValueError):
                from file_processing.services.upload_service import save_temp_file

                f = SimpleUploadedFile(
                    "doc.pdf",
                    pdf_doc,
                    content_type="application/pdf"
                )
                save_temp_file(f)

    def test_save_temp_file_success(self):
        from file_processing.services.upload_service import save_temp_file

        pdf_doc = self.generate_valid_pdf_bytes()

        f = SimpleUploadedFile(
            "doc.pdf",
            pdf_doc,
            content_type="application/pdf",
        )

        path = save_temp_file(f)

        self.assertTrue(path.endswith(".pdf"))

    def test_upload_pdf_uppercase_extension(self):
        pdf_doc = self.generate_valid_pdf_bytes()

        resp = self._post_file(
            "DOC.PDF",
            pdf_doc,
            "application/pdf",
        )

        self.assertEqual(resp.status_code, 200)

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

        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data["status"], "error")
        self.assertIn("message", resp.data)

    def test_upload_file_exact_10mb_allowed(self):
        valid_pdf = self.generate_valid_pdf_bytes()
        remaining_size = (10 * 1024 * 1024) - len(valid_pdf)

        padding = b"\0" * remaining_size
        exact_content = valid_pdf + padding
        resp = self._post_file("exact.pdf", exact_content, "application/pdf")
        self.assertEqual(resp.status_code, 200)

    def test_upload_file_less_than_10mb_allowed(self):
        valid_pdf = self.generate_valid_pdf_bytes()
        padding = b"\0" * (5 * 1024 * 1024)
        less_content = valid_pdf + padding
        resp = self._post_file("small.pdf", less_content, "application/pdf")
        self.assertEqual(resp.status_code, 200)

    def test_file_is_private_pdf(self):
        private_pdf = self.generate_private_pdf_bytes(password="1234")

        resp = self._post_file("private.pdf", private_pdf, "application/pdf")

        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data["status"], "error")
        self.assertIn("message", resp.data)

    def test_xls_extension_but_invalid_mime(self):
        resp = self._post_file(
            "fake.xls",
            b"not an excel file",
            "application/vnd.ms-excel",
        )

        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data["status"], "error")

    def test_xlsx_extension_but_invalid_mime(self):
        resp = self._post_file(
            "fake.xlsx",
            b"this is not an excel file",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data["status"], "error")
        self.assertIn("message", resp.data)

    def test_mime_detection_exception(self):
        with patch(
            "file_processing.services.upload_service.magic.from_buffer"
        ) as mock_magic:

            mock_magic.side_effect = Exception("libmagic failure")

            resp = self._post_file(
                "sheet.xlsx",
                b"dummy content",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

            self.assertEqual(resp.status_code, 400)
            self.assertEqual(resp.data["status"], "error")
            self.assertEqual(resp.data["message"], "Unable to determine file type.")
