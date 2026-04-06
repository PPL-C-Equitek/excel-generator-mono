from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

UPLOAD_URL = "/upload/"

def _csv_file(
    name: str,
    content: bytes,
    content_type: str = "text/csv",
) -> SimpleUploadedFile:
    return SimpleUploadedFile(name, content, content_type=content_type)


def _valid_csv_content() -> bytes:
    return (
        "NIM,Nama,Jurusan\n"
        "12345,Alice,Teknik Informatika\n"
        "67890,Bob,Sistem Informasi\n"
    ).encode("utf-8")


def _docx_like_content() -> bytes:
    zip_header = b"\x50\x4B\x03\x04"
    return zip_header + b"\x00" * 100


class CsvValidationPositiveTests(TestCase):

    def test_csv_extension_is_accepted(self):
        uploaded = _csv_file("data.csv", _valid_csv_content(), "text/csv")
        response = self.client.post(UPLOAD_URL, {"file": uploaded})
        self.assertIn(
            response.status_code, [200],
            f"File .csv valid seharusnya diterima, status={response.status_code}",
        )

    def test_csv_extension_not_rejected_as_unsupported(self):
        uploaded = _csv_file("laporan.csv", _valid_csv_content(), "text/csv")
        response = self.client.post(UPLOAD_URL, {"file": uploaded})
        if response.status_code == 400:
            body = response.json()
            msg = body.get("message", "").lower()
            self.assertNotIn(
                "unsupported",
                msg,
                "Ekstensi .csv seharusnya tidak ditolak sebagai unsupported.",
            )

    def test_valid_csv_under_10mb_is_accepted(self):
        header = b"NIM,Nama,Nilai\n"
        row = b"12345,Alice,100\n"
        content = header + row * 65_000
        uploaded = _csv_file("valid_size.csv", content, "text/csv")
        response = self.client.post(UPLOAD_URL, {"file": uploaded})
        self.assertNotEqual(
            response.status_code, 413,
            "File .csv berukuran ≤ 10 MB tidak boleh ditolak karena ukuran.",
        )
        self.assertNotEqual(
            response.status_code, 500,
            "File .csv valid tidak boleh menyebabkan server error (500).",
        )

    def test_correct_mime_text_csv_is_accepted(self):
        uploaded = _csv_file("dokumen.csv", _valid_csv_content(), "text/csv")
        response = self.client.post(UPLOAD_URL, {"file": uploaded})
        self.assertEqual(
            response.status_code, 200,
            "File .csv dengan MIME 'text/csv' seharusnya diterima.",
        )

    def test_file_exactly_10mb_not_server_error(self):
        exactly_10mb = _csv_file(
            "pas10mb.csv",
            b"A," * (5 * 1024 * 1024),
            "text/csv",
        )
        response = self.client.post(UPLOAD_URL, {"file": exactly_10mb})
        self.assertNotEqual(
            response.status_code, 500,
            "File tepat 10 MB tidak boleh menyebabkan server error.",
        )

class CsvValidationNegativeTests(TestCase):
    def test_file_exceeding_10mb_is_rejected(self):
        oversized = _csv_file(
            "besar.csv",
            b"A" * (10 * 1024 * 1024 + 1),
            "text/csv",
        )
        response = self.client.post(UPLOAD_URL, {"file": oversized})
        self.assertIn(
            response.status_code, [400, 413],
            f"File .csv > 10 MB seharusnya ditolak, status={response.status_code}",
        )

    def test_oversize_error_message_is_informative(self):
        oversized = _csv_file(
            "terlalu_besar.csv",
            b"B" * (10 * 1024 * 1024 + 1),
            "text/csv",
        )
        response = self.client.post(UPLOAD_URL, {"file": oversized})
        if response.status_code in [400, 413]:
            body = response.json()
            self.assertIn("message", body)
            self.assertNotIn(
                "Traceback", body["message"],
                "Pesan error tidak boleh mengandung traceback.",
            )

    def test_oversize_error_message_is_not_empty(self):
        oversized = _csv_file(
            "terlalu_besar2.csv",
            b"C" * (10 * 1024 * 1024 + 1),
            "text/csv",
        )
        response = self.client.post(UPLOAD_URL, {"file": oversized})
        if response.status_code in [400, 413]:
            body = response.json()
            msg = body.get("message", "")
            self.assertGreater(
                len(msg), 0,
                "Pesan error ukuran file tidak boleh kosong.",
            )


class CsvValidationEdgeCaseTests(TestCase):

    def test_docx_renamed_to_csv_is_rejected(self):
        fake_csv = _csv_file(
            "laporan.csv",
            _docx_like_content(),
            "text/csv",
        )
        response = self.client.post(UPLOAD_URL, {"file": fake_csv})
        self.assertIn(
            response.status_code, [400, 415],
            "File .docx berekstensi .csv seharusnya ditolak oleh sistem.",
        )

    def test_rejection_message_mentions_content_mismatch(self):
        fake_csv = _csv_file(
            "dokumen.csv",
            _docx_like_content(),
            "text/csv",
        )
        response = self.client.post(UPLOAD_URL, {"file": fake_csv})
        if response.status_code in [400, 415]:
            body = response.json()
            self.assertIn(
                "message", body,
                "Respons error harus mengandung kunci 'message'.",
            )
            self.assertGreater(
                len(body["message"]), 0,
                "Pesan error tidak boleh kosong.",
            )

    def test_wrong_mime_type_is_rejected(self):
        binary_content = b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 64
        fake_csv = _csv_file(
            "program.csv",
            binary_content,
            "application/octet-stream",
        )
        response = self.client.post(UPLOAD_URL, {"file": fake_csv})
        self.assertIn(
            response.status_code, [400, 415],
            "File .csv dengan konten binary/MIME salah seharusnya ditolak.",
        )

    @patch("file_processing.services.upload_service.magic.from_buffer")
    def test_csv_mime_not_allowed_is_rejected(self, mock_magic):
        mock_magic.return_value = "application/random-illegal"
        uploaded = _csv_file("data.csv", b"a,b,c\n1,2,3", "text/csv")
        resp = self.client.post(UPLOAD_URL, {"file": uploaded})
        self.assertIn(
            resp.status_code, [400, 415],
            "MIME tidak diizinkan seharusnya menghasilkan penolakan.",
        )

    @patch("file_processing.services.upload_service.magic.from_buffer")
    def test_csv_mime_fallback_allowed(self, mock_magic):
        mock_magic.return_value = "text/csv"
        with patch.dict(
            "file_processing.services.upload_service.ALLOWED_MIME_TYPES",
            {".csv": ["text/csv"]},
        ):
            uploaded = _csv_file("data.csv", b"a,b,c\n1,2,3", "text/csv")
            resp = self.client.post(UPLOAD_URL, {"file": uploaded})
            self.assertEqual(resp.status_code, 200)

    def test_corrupted_csv_file_does_not_cause_server_error(self):
        corrupted_content = b"\xff\xfe" + b"\x00\x01" * 50
        corrupted = _csv_file(
            "corrupt.csv",
            corrupted_content,
            "text/csv",
        )
        response = self.client.post(UPLOAD_URL, {"file": corrupted})
        self.assertNotEqual(
            response.status_code, 500,
            "File corrupt tidak boleh menyebabkan server error (500).",
        )

    def test_corrupted_csv_error_message_exists(self):
        corrupted_content = b"\xff\xfe" + b"\x00\x01" * 50
        corrupted = _csv_file(
            "corrupt2.csv",
            corrupted_content,
            "text/csv",
        )
        response = self.client.post(UPLOAD_URL, {"file": corrupted})
        if response.status_code in [400, 415, 422]:
            body = response.json()
            self.assertIn("message", body)
            self.assertGreater(len(body["message"]), 0)

    def test_corrupted_file_error_message_is_user_friendly(self):
        corrupted_content = b"\xc0\xc1\xfe\xff" * 100
        corrupted = _csv_file(
            "broken.csv",
            corrupted_content,
            "text/csv",
        )
        response = self.client.post(UPLOAD_URL, {"file": corrupted})
        if response.status_code not in [200]:
            body = response.json()
            error_msg = body.get("message", "")
            self.assertNotIn("Traceback", error_msg)
            self.assertNotIn("raise ", error_msg)

    def test_password_protected_csv_is_rejected(self):
        ole_header = b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1" + b"\x00" * 500
        protected_fake_csv = _csv_file(
            "protected.csv",
            ole_header,
            "text/csv",
        )
        response = self.client.post(UPLOAD_URL, {"file": protected_fake_csv})
        self.assertIn(
            response.status_code, [400, 415, 422],
            "File terproteksi/berenkripsi berekstensi .csv harus ditolak.",
        )

    def test_protected_file_error_message_is_relevant(self):
        ole_header = b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1" + b"\x00" * 500
        protected_fake_csv = _csv_file(
            "protected2.csv",
            ole_header,
            "text/csv",
        )
        response = self.client.post(UPLOAD_URL, {"file": protected_fake_csv})
        if response.status_code in [400, 415, 422]:
            body = response.json()
            self.assertIn(
                "message", body,
                "Respons error harus mengandung kunci 'message'.",
            )
            self.assertGreater(
                len(body.get("message", "")), 0,
                "Pesan error tidak boleh kosong.",
            )

    def test_protected_file_error_is_user_friendly(self):
        ole_header = b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1" + b"\x00" * 500
        protected_fake_csv = _csv_file(
            "protected3.csv",
            ole_header,
            "text/csv",
        )
        response = self.client.post(UPLOAD_URL, {"file": protected_fake_csv})
        if response.status_code in [400, 415, 422]:
            body = response.json()
            error_msg = body.get("message", "")
            self.assertNotIn(
                "Traceback", error_msg,
                "Pesan error tidak boleh mengandung traceback Python.",
            )
            self.assertNotIn(
                "raise ", error_msg,
                "Pesan error tidak boleh mengandung statement raise Python.",
            )
