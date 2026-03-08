import os
import tempfile

from unittest.mock import patch

from django.test import TestCase
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from file_processing.services.upload_service import extract_pdf_to_json

from django.test import SimpleTestCase
from rest_framework.test import APIClient

from file_processing.services.export_service import (
    OutputCSVGenerationError,
    OutputLLMValidationError,
)


class ExportCsvEndpointTest(SimpleTestCase):
    def setUp(self):
        self.client = APIClient()

    def _valid_output_json(self):
        return {
            "document_info": {
                "source_type": "Excel",
                "filename": "laporan_tahunan.xlsx",
            },
            "summary": {
                "grand_total": 1500000,
                "period": "2026",
            },
            "content_data": [
                {
                    "table_name": "Sheet1_Januari",
                    "headers": ["item_name", "quantity", "price"],
                    "rows": [
                        {"item_name": "Kertas", "quantity": 10, "price": 50000},
                        {"item_name": "Pena", "quantity": 5, "price": 10000},
                    ],
                }
            ],
        }

    @patch("api.views.export_csv_to_filesystem")
    def test_export_csv_returns_200_and_metadata_for_valid_payload(
        self,
        mock_export_csv_to_filesystem,
    ):
        output_json = self._valid_output_json()
        saved_metadata = {
            "file_id": "csv_8fa2e3d1",
            "file_name": "export_123.csv",
            "artifact_type": "csv",
            "size_bytes": 15,
            "created_at": "2026-03-06T10:00:00Z",
        }

        mock_export_csv_to_filesystem.return_value = saved_metadata

        response = self.client.post(
            "/export/csv",
            {"output_json": output_json},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["file_id"], "csv_8fa2e3d1")
        self.assertEqual(response.data["file_name"], "export_123.csv")
        self.assertEqual(response.data["artifact_type"], "csv")
        self.assertEqual(response.data["size_bytes"], 15)
        self.assertNotIn("path", response.data)
        self.assertNotIn("file_path", response.data)

        mock_export_csv_to_filesystem.assert_called_once()

    def test_export_csv_rejects_missing_output_json(self):
        response = self.client.post("/export/csv", {}, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertIn("output_json", response.data)

    @patch("api.views.export_csv_to_filesystem")
    def test_export_csv_rejects_invalid_schema_payload(
        self,
        mock_export_csv_to_filesystem,
    ):
        mock_export_csv_to_filesystem.side_effect = OutputLLMValidationError(
            "Invalid output schema."
        )

        response = self.client.post(
            "/export/csv",
            {"output_json": self._valid_output_json()},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertTrue("detail" in response.data or "message" in response.data)

    @patch("api.views.export_csv_to_filesystem")
    def test_export_csv_returns_500_when_filesystem_save_fails(
        self,
        mock_export_csv_to_filesystem,
    ):
        mock_export_csv_to_filesystem.side_effect = OutputCSVGenerationError(
            "Disk write failed"
        )

        response = self.client.post(
            "/export/csv",
            {"output_json": self._valid_output_json()},
            format="json",
        )

        self.assertEqual(response.status_code, 500)
        self.assertTrue("detail" in response.data or "message" in response.data)

    def test_export_csv_rejects_get(self):
        response = self.client.get("/export/csv")
        self.assertEqual(response.status_code, 405)


class ExtractPdfToJsonTest(TestCase):
    """Tests covering extract_pdf_to_json."""

    def _create_pdf(self, texts: list[str]) -> str:
        """Create a real PDF with one page per text entry and return its path."""
        buf = BytesIO()
        p = canvas.Canvas(buf)
        for text in texts:
            p.drawString(72, 720, text)
            p.showPage()
        p.save()
        buf.seek(0)

        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        tmp.write(buf.read())
        tmp.close()
        return tmp.name

    def _create_blank_pdf(self) -> str:
        """Create a PDF whose page returns empty text."""
        buf = BytesIO()
        p = canvas.Canvas(buf)
        p.showPage()
        p.save()
        buf.seek(0)

        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        tmp.write(buf.read())
        tmp.close()
        return tmp.name

    def _create_table_pdf(self) -> str:
        """Create a PDF containing a table (triggers table-extraction path)."""
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        tmp.close()

        doc = SimpleDocTemplate(tmp.name, pagesize=A4)
        data = [
            ["NAMA", "NPM", "SEMESTER"],
            ["Alice", "123", "6"],
            ["Bob", "456", "4"],
        ]
        table = Table(data)
        table.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 1, colors.black),
                ]
            )
        )
        doc.build([table])
        return tmp.name

    def _create_table_with_none_cell_pdf(self) -> str:
        """Create a table PDF where a cell is empty (None → '')."""
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        tmp.close()

        doc = SimpleDocTemplate(tmp.name, pagesize=A4)
        data = [
            ["COL1", "COL2"],
            ["val", ""],
        ]
        table = Table(data)
        table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 1, colors.black)]))
        doc.build([table])
        return tmp.name

    def _create_table_plus_text_pdf(self) -> str:
        """Create a PDF with a table AND plain text below it."""
        from reportlab.platypus import Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet

        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        tmp.close()

        doc = SimpleDocTemplate(tmp.name, pagesize=A4)
        styles = getSampleStyleSheet()

        data = [
            ["NAMA", "NPM"],
            ["Alice", "123"],
        ]
        table = Table(data)
        table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 1, colors.black)]))

        text_paragraph = Paragraph(
            "Please ignore this. THIS IS ONLY FOR TESTING.", styles["Normal"]
        )

        doc.build([table, Spacer(1, 20), text_paragraph])
        return tmp.name

    def test_single_page_text_returns_lines(self):
        """Plain-text page → text is a list of line strings."""
        path = self._create_pdf(["Hello World"])
        try:
            result = extract_pdf_to_json(path)
            self.assertEqual(result["document_info"]["source_type"], "pdf")
            self.assertTrue(result["document_info"]["file_name"].endswith(".pdf"))
            self.assertEqual(result["document_info"]["total_pages"], 1)
            self.assertEqual(len(result["content"]), 1)
            self.assertEqual(result["content"][0]["page"], 1)

            text = result["content"][0]["text"]
            self.assertIsInstance(text, list)
            joined = " ".join(text) if isinstance(text[0], str) else str(text)
            self.assertIn("Hello World", joined)
        finally:
            os.unlink(path)

    def test_multi_page_pdf(self):
        """Covers loop iteration for multiple pages."""
        path = self._create_pdf(["Page one", "Page two", "Page three"])
        try:
            result = extract_pdf_to_json(path)
            self.assertEqual(result["document_info"]["total_pages"], 3)
            self.assertEqual(len(result["content"]), 3)
            for i, entry in enumerate(result["content"], start=1):
                self.assertEqual(entry["page"], i)
                self.assertIsInstance(entry["text"], list)
        finally:
            os.unlink(path)

    def test_blank_page_returns_empty_list(self):
        """Covers the branch when page has no text and no tables."""
        path = self._create_blank_pdf()
        try:
            result = extract_pdf_to_json(path)
            self.assertEqual(result["document_info"]["total_pages"], 1)
            self.assertEqual(result["content"][0]["text"], [])
        finally:
            os.unlink(path)

    def test_table_pdf_returns_rows(self):
        """Pages with tables → text is list of row-arrays."""
        path = self._create_table_pdf()
        try:
            result = extract_pdf_to_json(path)
            text = result["content"][0]["text"]
            self.assertIsInstance(text, list)
            self.assertGreaterEqual(len(text), 3)
            for row in text:
                self.assertIsInstance(row, list)
            self.assertIn("NAMA", text[0])
            self.assertIn("NPM", text[0])
        finally:
            os.unlink(path)

    def test_table_none_cell_replaced_with_empty_string(self):
        """None cells in tables are replaced with empty strings."""
        path = self._create_table_with_none_cell_pdf()
        try:
            result = extract_pdf_to_json(path)
            text = result["content"][0]["text"]
            for row in text:
                if isinstance(row, list):
                    for cell in row:
                        self.assertIsNotNone(cell)
                        self.assertIsInstance(cell, str)
        finally:
            os.unlink(path)

    def test_table_plus_outside_text(self):
        """Text outside table area is also captured as plain strings."""
        path = self._create_table_plus_text_pdf()
        try:
            result = extract_pdf_to_json(path)
            text = result["content"][0]["text"]

            table_rows = [e for e in text if isinstance(e, list)]
            plain_lines = [e for e in text if isinstance(e, str)]

            self.assertGreaterEqual(len(table_rows), 2)
            self.assertGreaterEqual(len(plain_lines), 1)
            combined = " ".join(plain_lines)
            self.assertIn("TESTING", combined)
        finally:
            os.unlink(path)

    def test_document_info_file_name(self):
        path = self._create_pdf(["test"])
        try:
            result = extract_pdf_to_json(path)
            expected_name = os.path.basename(path)
            self.assertEqual(result["document_info"]["file_name"], expected_name)
        finally:
            os.unlink(path)

    def test_document_info_source_type_is_pdf(self):
        path = self._create_pdf(["abc"])
        try:
            result = extract_pdf_to_json(path)
            self.assertEqual(result["document_info"]["source_type"], "pdf")
        finally:
            os.unlink(path)

    def test_corrupt_file_raises_exception(self):
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        tmp.write(b"not a pdf at all")
        tmp.close()
        try:
            with self.assertRaises(Exception):
                extract_pdf_to_json(tmp.name)
        finally:
            os.unlink(tmp.name)

    def test_nonexistent_file_raises_exception(self):
        with self.assertRaises(Exception):
            extract_pdf_to_json("/tmp/nonexistent_file_12345.pdf")

    def test_return_structure_keys(self):
        path = self._create_pdf(["structure test"])
        try:
            result = extract_pdf_to_json(path)
            self.assertIn("document_info", result)
            self.assertIn("content", result)
            info = result["document_info"]
            self.assertIn("source_type", info)
            self.assertIn("file_name", info)
            self.assertIn("total_pages", info)
        finally:
            os.unlink(path)

    def test_content_entry_keys(self):
        path = self._create_pdf(["key test"])
        try:
            result = extract_pdf_to_json(path)
            for entry in result["content"]:
                self.assertIn("page", entry)
                self.assertIn("text", entry)
        finally:
            os.unlink(path)
