import io
from django.test import TestCase, Client
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile

class ExcelParsingErrorHandlingTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.upload_url = '/api/upload/'

    def test_upload_without_file_returns_400(self):
        response = self.client.post(self.upload_url, {})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['status'], 'error')
        self.assertEqual(response.json()['message'].lower(), 'no file provided')

    def test_upload_invalid_file_extension_returns_400(self):
        text_file = SimpleUploadedFile("test.txt", b"ini bukan file excel", content_type="text/plain")
        response = self.client.post(self.upload_url, {'file': text_file})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['status'], 'error')
        self.assertIn('invalid file format', response.json()['message'].lower())

    def test_upload_corrupted_excel_file_returns_400(self):
        corrupted_file = SimpleUploadedFile(
            "corrupted.xlsx", 
            b"data binary sembarangan yang tidak valid untuk excel", 
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response = self.client.post(self.upload_url, {'file': corrupted_file})
        
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['status'], 'error')
        response_error = response.json()['message'].lower()
        self.assertTrue('corrupted' in response_error or 'cannot read' in response_error)

    def create_dummy_excel(self, sheet_title="Sheet1", headers=None):
        try:
            from openpyxl import Workbook
        except ImportError:
            self.fail("TDD Note: Harap install 'openpyxl' untuk menjalankan unit test pembuatan excel.")

        wb = Workbook()
        ws = wb.active
        ws.title = sheet_title
        if headers:
            ws.append(headers)
        
        excel_file = io.BytesIO()
        wb.save(excel_file)
        excel_file.seek(0)
        return excel_file.read()

    def test_excel_missing_required_sheet_returns_400(self):
        excel_bytes = self.create_dummy_excel(sheet_title="SheetSalah")
        excel_file = SimpleUploadedFile("test.xlsx", excel_bytes, 
                                        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        
        response = self.client.post(self.upload_url, {'file': excel_file})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['status'], 'error')
        self.assertIn('sheet', response.json()['message'].lower()) 

    def test_excel_missing_required_columns_returns_400(self):
        excel_bytes = self.create_dummy_excel(sheet_title="Data Mahasiswa", headers=['NIM', 'Nama Salah', 'Jurusan'])
        excel_file = SimpleUploadedFile("test.xlsx", excel_bytes, 
                                        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        
        response = self.client.post(self.upload_url, {'file': excel_file})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['status'], 'error')
        self.assertIn('column', response.json()['message'].lower())
