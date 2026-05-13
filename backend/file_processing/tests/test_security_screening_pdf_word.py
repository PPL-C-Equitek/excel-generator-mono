import json
import zipfile
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from file_processing.services.upload_service import OLE_SIGNATURE


class TestSecurityScreeningPdfWord(TestCase):
    def _upload(self, name: str, content: bytes, content_type: str):
        uploaded = SimpleUploadedFile(name, content, content_type=content_type)
        return self.client.post("/upload/", {"file": uploaded}, format="multipart")

    def _minimal_valid_docx_bytes(self, pages: int = 1) -> bytes:
        payload = BytesIO()
        with zipfile.ZipFile(payload, "w") as archive:
            archive.writestr(
                "[Content_Types].xml",
                """
                <Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\">
                    <Default Extension=\"xml\" ContentType=\"application/xml\"/>
                </Types>
                """.strip(),
            )
            archive.writestr(
                "word/document.xml",
                """
                <w:document xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\">
                    <w:body><w:p><w:r><w:t>hello</w:t></w:r></w:p></w:body>
                </w:document>
                """.strip(),
            )
            archive.writestr(
                "docProps/app.xml",
                (
                    '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties">'
                    f"<Pages>{pages}</Pages>"
                    "</Properties>"
                ),
            )
        return payload.getvalue()

    def test_upload_rejects_docx_mime_spoof_plaintext(self):
        response = self._upload(
            "spoofed.docx",
            b"this is plain text pretending to be docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["status"], "error")
        self.assertIn("does not match", response.data["message"].lower())

    def test_upload_rejects_encrypted_ooxml_wrapped_as_ole(self):
        response = self._upload(
            "encrypted.docx",
            OLE_SIGNATURE + b"EncryptedPackage" + b"padding",
            "application/octet-stream",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["status"], "error")
        self.assertIn("password-protected", response.data["message"].lower())

    def test_upload_rejects_corrupt_pdf(self):
        response = self._upload(
            "broken.pdf",
            b"%PDF-1.4\nthis is not a real pdf body",
            "application/pdf",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["status"], "error")
        self.assertIn("pdf", response.data["message"].lower())

    def test_upload_rejects_doc_with_page_limit_bypass_attempt(self):
        # Use many form-feed markers to emulate >100 pages in legacy .doc binary content.
        payload = OLE_SIGNATURE + b"WordDocument" + (b"\x0c" * 101)
        response = self._upload("too-many-pages.doc", payload, "application/msword")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["status"], "error")
        self.assertIn("maximum allowed page count", response.data["message"].lower())

    def test_upload_accepts_minimal_valid_docx(self):
        response = self._upload(
            "valid.docx",
            self._minimal_valid_docx_bytes(pages=2),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "success")

    def test_json_response_shape_is_stable_for_rejected_upload(self):
        response = self._upload(
            "spoofed.docx",
            b"not a zip",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

        serialized = json.loads(json.dumps(response.data))
        self.assertIn("status", serialized)
        self.assertIn("message", serialized)
        self.assertEqual(serialized["status"], "error")
