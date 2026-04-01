import io
import json
import os
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from file_processing.services.txt_service import (
    _read_lines,
    parse_txt,
    parse_txt_with_delimiter,
    process_uploaded_txt,
)

def _make_txt_file(content: str, suffix: str = ".txt") -> str:
    fd, path = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(content)
    return path


def _make_bytes_io(content: str) -> io.BytesIO:
    return io.BytesIO(content.encode("utf-8"))


def _make_str_io(content: str) -> io.StringIO:
    return io.StringIO(content)


class PositiveTxtExtractionTests(TestCase):
    def test_single_line_returns_correct_structure(self):
        path = _make_txt_file("Hello World")
        try:
            result = parse_txt(path)

            self.assertIsInstance(result, list)
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0], ["Hello World"])
        finally:
            os.remove(path)

    def test_extracts_text_from_txt_file(self):
        path = _make_txt_file("Baris pertama\nBaris kedua\nBaris ketiga")
        try:
            result = parse_txt(path)

            self.assertEqual(len(result), 3)
            self.assertEqual(result[0], ["Baris pertama"])
            self.assertEqual(result[1], ["Baris kedua"])
            self.assertEqual(result[2], ["Baris ketiga"])
        finally:
            os.remove(path)

    def test_each_row_is_a_single_element_list(self):
        path = _make_txt_file("A\nB\nC\nD")
        try:
            result = parse_txt(path)
            self.assertEqual(result, [["A"], ["B"], ["C"], ["D"]])
        finally:
            os.remove(path)

    def test_multi_line_text_all_lines_are_read(self):
        lines = [f"Baris ke-{i}" for i in range(1, 11)]
        path = _make_txt_file("\n".join(lines))
        try:
            result = parse_txt(path)
            self.assertEqual(len(result), 10)
            for idx, expected_text in enumerate(lines):
                self.assertEqual(result[idx], [expected_text])
        finally:
            os.remove(path)

    def test_multi_line_preserves_whitespace_within_lines(self):
        path = _make_txt_file("  leading space\ntrailing space  \n  both  ")
        try:
            result = parse_txt(path)
            self.assertEqual(result[0], ["  leading space"])
            self.assertEqual(result[1], ["trailing space  "])
            self.assertEqual(result[2], ["  both  "])
        finally:
            os.remove(path)

    def test_blank_lines_in_between_are_skipped(self):
        path = _make_txt_file("Atas\n\nBawah")
        try:
            result = parse_txt(path)
            self.assertEqual(len(result), 2)
            self.assertEqual(result[0], ["Atas"])
            self.assertEqual(result[1], ["Bawah"])
        finally:
            os.remove(path)

    def test_comma_delimiter_splits_fields_correctly(self):
        path = _make_txt_file("NIM,Nama,Jurusan\n12345,Alice,Teknik Informatika")
        try:
            result = parse_txt_with_delimiter(path, delimiter=",")

            self.assertIsInstance(result, list)
            self.assertEqual(result[0], ["NIM", "Nama", "Jurusan"])
            self.assertEqual(result[1], ["12345", "Alice", "Teknik Informatika"])
        finally:
            os.remove(path)

    def test_tab_delimiter_splits_fields_correctly(self):
        path = _make_txt_file("Kolom1\tKolom2\tKolom3\nA\tB\tC")
        try:
            result = parse_txt_with_delimiter(path, delimiter="\t")
            self.assertEqual(result[0], ["Kolom1", "Kolom2", "Kolom3"])
            self.assertEqual(result[1], ["A", "B", "C"])
        finally:
            os.remove(path)

    def test_pipe_delimiter_splits_fields_correctly(self):
        path = _make_txt_file("A|B|C\n1|2|3")
        try:
            result = parse_txt_with_delimiter(path, delimiter="|")
            self.assertEqual(result[0], ["A", "B", "C"])
            self.assertEqual(result[1], ["1", "2", "3"])
        finally:
            os.remove(path)

    def test_default_delimiter_is_comma(self):
        path = _make_txt_file("x,y,z")
        try:
            result = parse_txt_with_delimiter(path)
            self.assertEqual(result[0], ["x", "y", "z"])
        finally:
            os.remove(path)

    def test_parse_txt_from_bytes_io_object(self):
        buf = _make_bytes_io("Baris satu\nBaris dua")
        result = parse_txt(buf)

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], ["Baris satu"])
        self.assertEqual(result[1], ["Baris dua"])

    def test_parse_txt_from_string_io_object(self):
        buf = _make_str_io("Hello\nWorld")
        result = parse_txt(buf)

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], ["Hello"])

    def test_process_uploaded_txt_returns_success_tuple(self):
        path = _make_txt_file("isi file")
        try:
            success, error, data = process_uploaded_txt(path)

            self.assertTrue(success)
            self.assertIsNone(error)
            self.assertIsNotNone(data)
            self.assertIsInstance(data, list)
        finally:
            os.remove(path)

    def test_process_uploaded_txt_content_matches_file_content(self):
        path = _make_txt_file("Satu\nDua\nTiga")
        try:
            _, _, data = process_uploaded_txt(path)
            texts = [row[0] for row in data]
            self.assertEqual(texts, ["Satu", "Dua", "Tiga"])
        finally:
            os.remove(path)


class NegativeTxtExtractionTests(TestCase):

    def test_empty_file_returns_empty_list(self):
        path = _make_txt_file("")
        try:
            result = parse_txt(path)
            self.assertIsInstance(result, list)
            self.assertEqual(result, [])
        finally:
            os.remove(path)

    def test_process_uploaded_txt_empty_file_returns_success_with_empty_list(self):
        path = _make_txt_file("")
        try:
            success, error, data = process_uploaded_txt(path)
            self.assertTrue(success)
            self.assertIsNone(error)
            self.assertEqual(data, [])
        finally:
            os.remove(path)

    def test_nonexistent_file_raises_file_not_found(self):
        with self.assertRaises(FileNotFoundError):
            parse_txt("/tmp/__nonexistent_test_file_xyz__.txt")

    def test_process_uploaded_txt_nonexistent_file_returns_error(self):
        success, error, data = process_uploaded_txt("/tmp/__nonexistent_txt_file__.txt")

        self.assertFalse(success)
        self.assertIsNotNone(error)
        self.assertIsNone(data)
        self.assertIn("File tidak ditemukan", error)

    def test_process_uploaded_txt_error_message_is_user_friendly(self):
        success, error, data = process_uploaded_txt("/no/such/file.txt")

        self.assertFalse(success)
        self.assertNotIn("Traceback", error)
        self.assertNotIn("raise ", error)
        self.assertTrue(len(error) > 0)

    def test_parse_txt_with_delimiter_on_empty_file_returns_empty_list(self):
        path = _make_txt_file("")
        try:
            result = parse_txt_with_delimiter(path, delimiter=",")
            self.assertEqual(result, [])
        finally:
            os.remove(path)


class EdgeCaseTxtExtractionTests(TestCase):

    def test_very_long_single_line_is_read_completely(self):
        long_line = "X" * 10_001
        path = _make_txt_file(long_line)
        try:
            result = parse_txt(path)
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0], [long_line])
        finally:
            os.remove(path)

    def test_extremely_long_line_over_100k_chars_is_still_readable(self):
        long_line = "A" * 100_001
        buf = _make_bytes_io(long_line)
        result = parse_txt(buf)

        self.assertEqual(len(result), 1)
        self.assertEqual(len(result[0][0]), 100_001)

    def test_file_with_only_newlines_returns_empty_list(self):
        path = _make_txt_file("\n\n\n")
        try:
            result = parse_txt(path)
            self.assertEqual(result, [])
        finally:
            os.remove(path)

    def test_file_with_special_characters_and_unicode(self):
        path = _make_txt_file("áéíóú\n한국어\n日本語\n🎉🚀")
        try:
            result = parse_txt(path)
            self.assertEqual(result[0], ["áéíóú"])
            self.assertEqual(result[1], ["한국어"])
            self.assertEqual(result[2], ["日本語"])
            self.assertEqual(result[3], ["🎉🚀"])
        finally:
            os.remove(path)

    def test_file_with_windows_crlf_line_endings(self):
        fd, path = tempfile.mkstemp(suffix=".txt")
        with os.fdopen(fd, "wb") as fh:
            fh.write(b"Baris satu\r\nBaris dua\r\nBaris tiga\r\n")
        try:
            result = parse_txt(path)
            self.assertEqual(len(result), 3)
            for row in result:
                self.assertNotIn("\r", row[0])
        finally:
            os.remove(path)

    def test_single_character_file(self):
        path = _make_txt_file("Z")
        try:
            result = parse_txt(path)
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0], ["Z"])
        finally:
            os.remove(path)

    def test_many_lines_all_read_correctly(self):
        n = 500
        path = _make_txt_file("\n".join(f"Baris {i}" for i in range(1, n + 1)))
        try:
            result = parse_txt(path)
            self.assertEqual(len(result), n)
            for idx, row in enumerate(result, start=1):
                self.assertEqual(row, [f"Baris {idx}"])
        finally:
            os.remove(path)

    def test_delimiter_with_no_delimiter_in_line_returns_single_field(self):
        path = _make_txt_file("TidakAdaKoma")
        try:
            result = parse_txt_with_delimiter(path, delimiter=",")
            self.assertEqual(result[0], ["TidakAdaKoma"])
        finally:
            os.remove(path)

    def test_delimiter_line_starting_with_delimiter_yields_empty_first_field(self):
        path = _make_txt_file(",a,b")
        try:
            result = parse_txt_with_delimiter(path, delimiter=",")
            self.assertEqual(result[0][0], "")
            self.assertEqual(result[0][1], "a")
            self.assertEqual(result[0][2], "b")
        finally:
            os.remove(path)

    def test_mixed_blank_and_content_lines_skips_blanks(self):
        path = _make_txt_file("A\n\nB\n\nC")
        try:
            result = parse_txt(path)
            self.assertEqual(len(result), 3)
            self.assertEqual(result, [["A"], ["B"], ["C"]])
        finally:
            os.remove(path)

    def test_bytes_io_with_bom_utf8(self):
        bom = b"\xef\xbb\xbf"
        buf = io.BytesIO(bom + "Hello\nWorld".encode("utf-8"))
        try:
            result = parse_txt(buf)
            self.assertIsInstance(result, list)
        except Exception as exc:
            self.fail(f"parse_txt melempar exception tak terduga: {exc}")

    def test_read_lines_from_bytes_io_returns_list_of_strings(self):
        buf = _make_bytes_io("Baris 1\nBaris 2")
        lines = _read_lines(buf)
        self.assertIsInstance(lines, list)
        self.assertTrue(all(isinstance(line, str) for line in lines))

    def test_parse_txt_output_is_json_serialisable(self):
        path = _make_txt_file("Test JSON\nSerialisasi")
        try:
            result = parse_txt(path)
            serialised = json.dumps(result)
            parsed_back = json.loads(serialised)
            self.assertEqual(parsed_back[0], ["Test JSON"])
        finally:
            os.remove(path)

UPLOAD_URL = "/upload/"

def _txt_file(name: str, content: bytes, content_type: str = "text/plain") -> SimpleUploadedFile:
    return SimpleUploadedFile(name, content, content_type=content_type)


def _valid_txt_content() -> bytes:
    return "NIM,Nama,Jurusan\n12345,Alice,Teknik Informatika\n".encode("utf-8")


def _docx_like_content() -> bytes:
    zip_header = b"\x50\x4B\x03\x04"
    return zip_header + b"\x00" * 100


class TxtValidationTests(TestCase):

    def test_txt_extension_is_accepted(self):
        uploaded = _txt_file("data.txt", _valid_txt_content(), "text/plain")
        response = self.client.post(UPLOAD_URL, {"file": uploaded})
        self.assertIn(
            response.status_code, [200],
            f"File .txt valid seharusnya diterima, status={response.status_code}",
        )

    def test_txt_extension_not_rejected_as_unsupported(self):
        uploaded = _txt_file("laporan.txt", _valid_txt_content(), "text/plain")
        response = self.client.post(UPLOAD_URL, {"file": uploaded})
        if response.status_code == 400:
            body = response.json()
            msg = body.get("message", "").lower()
            self.assertNotIn(
                "unsupported",
                msg,
                "Ekstensi .txt seharusnya tidak ditolak sebagai unsupported.",
            )

    def test_docx_renamed_to_txt_is_rejected(self):
        fake_txt = _txt_file(
            "laporan.txt",
            _docx_like_content(),
            "text/plain",
        )
        response = self.client.post(UPLOAD_URL, {"file": fake_txt})
        self.assertIn(
            response.status_code, [400, 415],
            "File .docx berekstensi .txt seharusnya ditolak oleh sistem.",
        )

    def test_rejection_message_mentions_content_mismatch(self):
        fake_txt = _txt_file(
            "dokumen.txt",
            _docx_like_content(),
            "text/plain",
        )
        response = self.client.post(UPLOAD_URL, {"file": fake_txt})
        if response.status_code in [400, 415]:
            body = response.json()
            self.assertIn(
                "message", body,
                "Respons error harus mengandung kunci 'message'.",
            )
            self.assertTrue(
                len(body["message"]) > 0,
                "Pesan error tidak boleh kosong.",
            )

    def test_file_exceeding_10mb_is_rejected(self):
        oversized = _txt_file(
            "besar.txt",
            b"A" * (10 * 1024 * 1024 + 1),
            "text/plain",
        )
        response = self.client.post(UPLOAD_URL, {"file": oversized})
        self.assertIn(
            response.status_code, [400, 413],
            f"File >10 MB seharusnya ditolak, status={response.status_code}",
        )

    def test_oversize_error_message_is_informative(self):
        oversized = _txt_file(
            "terlalu_besar.txt",
            b"B" * (10 * 1024 * 1024 + 1),
            "text/plain",
        )
        response = self.client.post(UPLOAD_URL, {"file": oversized})
        if response.status_code in [400, 413]:
            body = response.json()
            self.assertIn("message", body)
            self.assertNotIn("Traceback", body["message"])

    def test_file_exactly_10mb_not_server_error(self):
        exactly_10mb = _txt_file(
            "pas10mb.txt",
            b"C" * (10 * 1024 * 1024),
            "text/plain",
        )
        response = self.client.post(UPLOAD_URL, {"file": exactly_10mb})
        self.assertNotEqual(
            response.status_code, 500,
            "File tepat 10 MB tidak boleh menyebabkan server error.",
        )

    def test_correct_mime_text_plain_is_accepted(self):
        uploaded = _txt_file("dokumen.txt", _valid_txt_content(), "text/plain")
        response = self.client.post(UPLOAD_URL, {"file": uploaded})
        self.assertEqual(
            response.status_code, 200,
            "File .txt dengan MIME 'text/plain' seharusnya diterima.",
        )

    def test_wrong_mime_type_is_rejected(self):
        binary_content = b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 64
        fake_txt = _txt_file(
            "program.txt",
            binary_content,
            "application/octet-stream",
        )
        response = self.client.post(UPLOAD_URL, {"file": fake_txt})
        self.assertIn(
            response.status_code, [400, 415],
            "File .txt dengan konten binary/MIME salah seharusnya ditolak.",
        )

    def test_corrupted_txt_file_returns_error(self):
        corrupted_content = b"\xff\xfe" + b"\x00\x01" * 50

        corrupted = _txt_file(
            "corrupt.txt",
            corrupted_content,
            "text/plain",
        )
        response = self.client.post(UPLOAD_URL, {"file": corrupted})
        self.assertNotEqual(
            response.status_code, 500,
            "File corrupt tidak boleh menyebabkan server error (500).",
        )
        if response.status_code in [400, 415, 422]:
            body = response.json()
            self.assertIn("message", body)
            self.assertTrue(len(body["message"]) > 0)

    def test_corrupted_file_error_message_is_user_friendly(self):
        corrupted_content = b"\xc0\xc1\xfe\xff" * 100

        corrupted = _txt_file(
            "broken.txt",
            corrupted_content,
            "text/plain",
        )
        response = self.client.post(UPLOAD_URL, {"file": corrupted})
        if response.status_code not in [200]:
            body = response.json()
            error_msg = body.get("message", "")
            self.assertNotIn("Traceback", error_msg)
            self.assertNotIn("raise ", error_msg)

    def test_password_protected_txt_is_rejected(self):
        ole_header = b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1" + b"\x00" * 500

        protected_fake_txt = _txt_file(
            "protected.txt",
            ole_header,
            "text/plain",
        )
        response = self.client.post(UPLOAD_URL, {"file": protected_fake_txt})
        self.assertIn(
            response.status_code, [400, 415, 422],
            "File terproteksi/berenkripsi berekstensi .txt harus ditolak.",
        )

    def test_protected_file_error_message_is_relevant(self):
        ole_header = b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1" + b"\x00" * 500

        protected_fake_txt = _txt_file(
            "protected2.txt",
            ole_header,
            "text/plain",
        )
        response = self.client.post(UPLOAD_URL, {"file": protected_fake_txt})
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