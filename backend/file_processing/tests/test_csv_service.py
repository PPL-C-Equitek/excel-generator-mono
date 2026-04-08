from unittest.mock import patch
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from io import BytesIO
import json
from file_processing.services.csv_service import parse_csv, process_uploaded_csv
from file_processing.services.upload_service import (
    _validate_csv_content,
    CSV_CORRUPT_ERROR,
    CSV_PROTECTED_ERROR,
    FILE_EXTENSION_MISMATCH_ERROR,
    process_upload,
)

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

def _bio(content: bytes) -> BytesIO:
    buf = BytesIO(content)
    return buf

class CsvUnitTests(TestCase):

    def test_ole_header_returns_csv_protected_error(self):
        ole = b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1" + b"\x00" * 8
        buf = _bio(ole)
        ok, err = _validate_csv_content(buf, "application/octet-stream")
        self.assertFalse(ok)
        self.assertEqual(err, CSV_PROTECTED_ERROR)

    def test_non_ole_binary_signature_returns_mismatch_error(self):
        zip_content = b"\x50\x4B\x03\x04" + b"\x00" * 8
        buf = _bio(zip_content)
        ok, err = _validate_csv_content(buf, "application/zip")
        self.assertFalse(ok)
        self.assertEqual(err, FILE_EXTENSION_MISMATCH_ERROR)

    def test_text_mime_is_accepted(self):
        buf = _bio(b"id,name\n1,Alice\n")
        ok, err = _validate_csv_content(buf, "text/plain")
        self.assertTrue(ok)
        self.assertIsNone(err)

    def test_allowed_non_text_mime_is_accepted(self):
        buf = _bio(b"id,name\n1,Alice\n")
        ok, err = _validate_csv_content(buf, "application/csv")
        self.assertTrue(ok)
        self.assertIsNone(err)

    def test_unknown_mime_returns_csv_corrupt_error(self):
        buf = _bio(b"id,name\n1,Alice\n")
        ok, err = _validate_csv_content(buf, "application/random-illegal")
        self.assertFalse(ok)
        self.assertEqual(err, CSV_CORRUPT_ERROR)

    def test_none_mime_falls_through_to_corrupt_error(self):
        buf = _bio(b"id,name\n1,Alice\n")
        ok, err = _validate_csv_content(buf, None)
        self.assertFalse(ok)
        self.assertEqual(err, CSV_CORRUPT_ERROR)

class CsvProcessUploadTests(TestCase):
    @patch("file_processing.services.upload_service.validate_file")
    def test_process_upload_csv_success(self, mock_validate):
        mock_validate.return_value = (True, None)

        f = _csv_file("data.csv", b"id,name\n1,Alice\n", "text/csv")
        success, error, _, data = process_upload(f)

        self.assertTrue(success)
        self.assertIsNone(error)
        self.assertIsNotNone(data)

    @patch("file_processing.services.upload_service.process_uploaded_csv")
    @patch("file_processing.services.upload_service.validate_file")
    def test_process_upload_csv_failure_propagates_error(
        self, mock_validate, mock_csv
    ):
        mock_validate.return_value = (True, None)
        mock_csv.return_value = (False, "CSV parse error", None)

        f = _csv_file("bad.csv", b"broken", "text/csv")
        success, error, _, data = process_upload(f)

        self.assertFalse(success)
        self.assertEqual(error, "CSV parse error")
        self.assertIsNone(data)

def _make_csv_file(name: str, content: bytes, content_type: str = "text/csv") -> SimpleUploadedFile:
    return SimpleUploadedFile(name, content, content_type=content_type)
 
def _csv_bytes(*rows: str, encoding: str = "utf-8") -> bytes:
    return "\n".join(rows).encode(encoding)
 
def _bio(content: bytes) -> BytesIO:
    return BytesIO(content)
 
class ParseCsvPositiveTests(TestCase):
    def test_standard_csv_returns_list_of_dicts(self):
        content = _csv_bytes(
            "NIM,Nama,Jurusan",
            "12345,Alice,Teknik Informatika",
            "67890,Bob,Sistem Informasi",
        )
        result = parse_csv(_bio(content))
 
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)
        self.assertIsInstance(result[0], dict)
 
    def test_header_keys_match_csv_columns_exactly(self):
        content = _csv_bytes("product_id,product_name,price", "001,Laptop,15000000")
        result = parse_csv(_bio(content))
 
        self.assertEqual(list(result[0].keys()), ["product_id", "product_name", "price"])
 
    def test_multirow_csv_all_rows_parsed(self):
        rows = ["id,nama,email"] + [f"{i},User{i},user{i}@mail.com" for i in range(1, 51)]
        content = _csv_bytes(*rows)
        result = parse_csv(_bio(content))
 
        self.assertEqual(len(result), 50)
 
    def test_single_data_row_returns_one_item_list(self):
        content = _csv_bytes("kode,nilai", "A,100")
        result = parse_csv(_bio(content))
 
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], {"kode": "A", "nilai": "100"})
 
    def test_csv_with_spaces_in_values_preserved(self):
        content = _csv_bytes("nama,kota", "  Alice  ,  Bandung  ")
        result = parse_csv(_bio(content))
 
        self.assertIn("nama", result[0])
        self.assertIn("kota", result[0])
 
 
class ParseCsvNegativeTests(TestCase):
    def test_empty_file_returns_empty_list_or_raises(self):
        result_or_exc = None
        try:
            result_or_exc = parse_csv(_bio(b""))
        except Exception as exc:
            result_or_exc = exc
 
        if isinstance(result_or_exc, list):
            self.assertEqual(result_or_exc, [])
        else:
            self.assertNotIsInstance(result_or_exc, AttributeError)
 
    def test_header_only_no_data_rows_returns_empty_list(self):
        content = _csv_bytes("id,nama,email")
        result = parse_csv(_bio(content))
 
        self.assertEqual(result, [])
 
    def test_none_input_raises_type_error(self):
        with self.assertRaises((TypeError, ValueError)):
            parse_csv(None)
 
    def test_binary_garbage_does_not_raise_unhandled_500(self):
        garbage = b"\xff\xfe" + b"\x00\x01" * 50
        try:
            parse_csv(_bio(garbage))
        except Exception as exc:
            self.assertNotIsInstance(exc, (MemoryError, RecursionError))
 
    def test_mismatched_column_count_strict_mode_raises(self):
        content = _csv_bytes("id,nama", "1,Alice,kolom_ekstra")
        with self.assertRaises(Exception):
            parse_csv(_bio(content), strict=True)
    
    def test_non_utf8_encoding_handled_gracefully(self):
        content = b"id,nama\n1,Caf\xe9" 
        with self.assertRaises(UnicodeDecodeError):
            parse_csv(_bio(content))
    
class ParseCsvEdgeCaseTests(TestCase):
 
    def test_quoted_field_containing_comma_not_split(self):
        content = _csv_bytes(
            "name,address,phone",
            'John,"Jl. Merdeka, No. 10, Jakarta",08123456789',
        )
        result = parse_csv(_bio(content))
 
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["address"], "Jl. Merdeka, No. 10, Jakarta")
        self.assertEqual(result[0]["phone"], "08123456789")
 
    def test_quoted_field_containing_newline_treated_as_single_field(self):
        raw = 'id,deskripsi\n1,"baris pertama\nbaris kedua"'
        content = raw.encode("utf-8")
        result = parse_csv(_bio(content))
 
        self.assertEqual(result[0]["deskripsi"], "baris pertama\nbaris kedua")
 
    def test_escaped_double_quote_inside_field_unescaped(self):
        raw = 'word,quote\nhello,"dia berkata ""halo"""'
        result = parse_csv(_bio(raw.encode("utf-8")))
 
        self.assertEqual(result[0]["quote"], 'dia berkata "halo"')
 
    def test_missing_value_stored_as_empty_string_not_omitted(self):
        content = _csv_bytes("id,nama,email", "1,,budi@mail.com", "2,Sari,")
        result = parse_csv(_bio(content))
 
        self.assertIn("nama", result[0])
        self.assertEqual(result[0]["nama"], "")
        self.assertIn("email", result[1])
        self.assertEqual(result[1]["email"], "")
 
    def test_row_with_fewer_columns_than_header_fills_missing_as_empty(self):
        content = _csv_bytes("a,b,c", "1,2", "4,5,6")
        result = parse_csv(_bio(content))
 
        self.assertIn("c", result[0])
        self.assertIn(result[0]["c"], ["", None])
        self.assertEqual(result[1], {"a": "4", "b": "5", "c": "6"})
 
    def test_windows_crlf_line_endings_parsed_correctly(self):
        content = "id,nama\r\n1,Andi\r\n2,Bela".encode("utf-8")
        result = parse_csv(_bio(content))
 
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["nama"], "Andi")
        self.assertEqual(result[1]["nama"], "Bela")
 
    def test_duplicate_header_columns_handled_without_data_loss(self):
        content = _csv_bytes("nama,nilai,nilai,nilai", "Alice,90,80,70")
        result = parse_csv(_bio(content))
 
        values = list(result[0].values())
        self.assertIn("90", values)
        self.assertIn("80", values)
        self.assertIn("70", values)
 
    def test_semicolon_delimiter_parsed_with_option(self):
        content = _csv_bytes("nama;kota;kode_pos", "Rahma;Bandung;40123")
        result = parse_csv(_bio(content), delimiter=";")
 
        self.assertEqual(result[0], {"nama": "Rahma", "kota": "Bandung", "kode_pos": "40123"})
 
    def test_tab_delimiter_parsed_with_option(self):
        content = "col1\tcol2\tcol3\nval1\tval2\tval3".encode("utf-8")
        result = parse_csv(_bio(content), delimiter="\t")
 
        self.assertEqual(result[0], {"col1": "val1", "col2": "val2", "col3": "val3"})
 
    def test_utf8_bom_header_stripped_correctly(self):
        content = b"\xef\xbb\xbfid,nama\n1,Rini"
        result = parse_csv(_bio(content))
 
        first_key = list(result[0].keys())[0]
        self.assertFalse(first_key.startswith("\ufeff"), "BOM tidak di-strip dari header")
 
    def test_large_value_field_not_truncated(self):
        long_value = "x" * 5000
        content = _csv_bytes("id,blob", f"1,{long_value}")
        result = parse_csv(_bio(content))
 
        self.assertEqual(len(result[0]["blob"]), 5000)
    
    def test_empty_lines_in_middle_are_ignored(self):
        content = _csv_bytes("id,nama", "1,Alice", "", "2,Bob", "")
        result = parse_csv(_bio(content))
        
        self.assertEqual(len(result), 2)
        self.assertEqual(result[1]["nama"], "Bob") 
 
class JsonOutputContractTests(TestCase):
    def _parse(self, *rows):
        return parse_csv(_bio(_csv_bytes(*rows)))
 
    def test_output_is_list_of_plain_dicts(self):
        result = self._parse("k,v", "a,1")
 
        self.assertIsInstance(result, list)
        self.assertIsInstance(result[0], dict)
        self.assertEqual(type(result[0]), dict)
 
    def test_all_values_are_strings_no_auto_coercion(self):
        result = self._parse("id,flag,score", "1,true,3.14")
 
        for val in result[0].values():
            self.assertIsInstance(val, str, f"Value '{val}' seharusnya string, bukan {type(val)}")
 
    def test_key_order_follows_header_column_order(self):
        result = self._parse("z,a,m", "3,1,2")
 
        self.assertEqual(list(result[0].keys()), ["z", "a", "m"])
 
    def test_every_row_has_all_header_keys(self):
        result = self._parse("id,nama,email", "1,Alice,a@b.com", "2,Bob,b@b.com")
 
        for row in result:
            self.assertEqual(set(row.keys()), {"id", "nama", "email"})
 
    def test_json_serializable_without_error(self):
        result = self._parse("id,nama", "1,Alice")
 
        try:
            serialized = json.dumps(result)
        except TypeError as exc:
            self.fail(f"Output tidak JSON-serializable: {exc}")
 
        parsed_back = json.loads(serialized)
        self.assertEqual(parsed_back, result)
 
    def test_row_count_matches_non_header_lines(self):
        result = self._parse("col", "a", "b", "c", "d", "e")
 
        self.assertEqual(len(result), 5)
 
    def test_empty_csv_produces_empty_list_json_serializable(self):
        result = parse_csv(_bio(b""))
 
        if result is not None:
            self.assertIsInstance(result, list)
            self.assertEqual(json.dumps(result), "[]")
 
class ProcessUploadedCsvPositiveTests(TestCase):
 
    def _uploaded(self, content: bytes) -> SimpleUploadedFile:
        return _make_csv_file("data.csv", content)
 
    def test_valid_csv_returns_success_true(self):
        content = _csv_bytes("id,nama", "1,Alice", "2,Bob")
        success, _, _ = process_uploaded_csv(self._uploaded(content))
 
        self.assertTrue(success)
 
    def test_valid_csv_error_is_none(self):
        content = _csv_bytes("id,nama", "1,Alice")
        _, error, _ = process_uploaded_csv(self._uploaded(content))
 
        self.assertIsNone(error)
 
    def test_valid_csv_data_is_list_of_dicts(self):
        content = _csv_bytes("id,nama", "1,Alice", "2,Bob")
        _, _, data = process_uploaded_csv(self._uploaded(content))
 
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)
        self.assertIsInstance(data[0], dict)
 
    def test_valid_csv_data_keys_match_header(self):
        content = _csv_bytes("kode,produk,harga", "A001,Laptop,15000000")
        _, _, data = process_uploaded_csv(self._uploaded(content))
 
        self.assertEqual(set(data[0].keys()), {"kode", "produk", "harga"})
 
    def test_valid_csv_returns_all_rows(self):
        rows = ["x,y"] + [f"{i},{i*2}" for i in range(10)]
        content = _csv_bytes(*rows)
        _, _, data = process_uploaded_csv(self._uploaded(content))
 
        self.assertEqual(len(data), 10)
 
class ProcessUploadedCsvNegativeTests(TestCase):
 
    def _uploaded(self, content: bytes, name: str = "data.csv") -> SimpleUploadedFile:
        return _make_csv_file(name, content)
 
    def test_empty_file_returns_success_false(self):
        success, _, _ = process_uploaded_csv(self._uploaded(b""))
 
        self.assertFalse(success)
 
    def test_empty_file_error_message_not_empty(self):
        _, error, _ = process_uploaded_csv(self._uploaded(b""))
 
        self.assertIsNotNone(error)
        self.assertGreater(len(error), 0)
 
    def test_empty_file_data_is_none_or_empty(self):
        _, _, data = process_uploaded_csv(self._uploaded(b""))
 
        self.assertIn(data, [None, [], {}])
 
    def test_corrupt_bytes_returns_success_false(self):
        garbage = b"\xff\xfe" + b"\x00\x01" * 50
        success, _, _ = process_uploaded_csv(self._uploaded(garbage))
        self.assertIsNotNone(success)
        self.assertFalse(success)
 
    def test_error_message_no_traceback_exposed(self):
        garbage = b"\xc0\xc1\xfe\xff" * 100
        _, error, _ = process_uploaded_csv(self._uploaded(garbage))
 
        if error:
            self.assertNotIn("Traceback", error)
            self.assertNotIn("raise ", error)
 
    def test_header_only_no_data_returns_empty_data(self):
        content = _csv_bytes("id,nama,email")
        success, error, data = process_uploaded_csv(self._uploaded(content))
 
        if success:
            self.assertEqual(data, [])
        else:
            self.assertIsNotNone(error) 
 
class ProcessUploadedCsvEdgeCaseTests(TestCase):
 
    def _uploaded(self, content: bytes) -> SimpleUploadedFile:
        return _make_csv_file("data.csv", content)
 
    def test_csv_with_quoted_commas_data_intact(self):
        content = _csv_bytes(
            "name,address",
            '"Ahmad","Jl. Sudirman, Blok A, No.5"',
        )
        success, _, data = process_uploaded_csv(self._uploaded(content))
 
        if success and data:
            self.assertEqual(data[0]["address"], "Jl. Sudirman, Blok A, No.5")
 
    def test_csv_missing_values_keys_present_in_output(self):
        content = _csv_bytes("id,nama,nilai", "1,,90", "2,Sari,")
        _, _, data = process_uploaded_csv(self._uploaded(content))
 
        if data:
            self.assertIn("nama", data[0])
            self.assertIn("nilai", data[1])
 
    def test_large_csv_does_not_timeout_or_crash(self):
        rows = ["col1,col2,col3"] + [f"val{i},val{i},val{i}" for i in range(500)]
        content = _csv_bytes(*rows)
        success, _, data = process_uploaded_csv(self._uploaded(content))
 
        self.assertIsNotNone(success)
        if success:
            self.assertEqual(len(data), 500)
 
    def test_return_tuple_has_exactly_three_elements(self):
        content = _csv_bytes("x", "1")
        result = process_uploaded_csv(self._uploaded(content))
 
        self.assertEqual(len(result), 3, "process_uploaded_csv harus return tuple 3 elemen")
 
    def test_crlf_csv_parses_without_carriage_return_in_values(self):
        content = "id,nama\r\n1,Andi\r\n2,Bela".encode("utf-8")
        success, _, data = process_uploaded_csv(self._uploaded(content))
 
        if success and data:
            for row in data:
                for val in row.values():
                    self.assertNotIn("\r", val, f"Carriage return masih ada di value: {repr(val)}")
 
class ProcessUploadCsvIntegrationTests(TestCase):
    def _csv_upload(self, content: bytes) -> SimpleUploadedFile:
        return _make_csv_file("report.csv", content)
 
    @patch("file_processing.services.upload_service.validate_file")
    def test_pipeline_success_data_contains_parsed_rows(self, mock_validate):
        mock_validate.return_value = (True, None)
        content = _csv_bytes("nim,nama", "001,Alice", "002,Bob")
 
        success, error, _, data = process_upload(self._csv_upload(content))
 
        self.assertTrue(success)
        self.assertIsNone(error)
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 2)
 
    @patch("file_processing.services.upload_service.validate_file")
    def test_pipeline_success_row_values_are_correct(self, mock_validate):
        mock_validate.return_value = (True, None)
        content = _csv_bytes("nim,nama,nilai", "12345,Alice,95")
 
        _, _, _, data = process_upload(self._csv_upload(content))
 
        if data:
            self.assertEqual(data[0]["nim"], "12345")
            self.assertEqual(data[0]["nama"], "Alice")
            self.assertEqual(data[0]["nilai"], "95")
 
    @patch("file_processing.services.upload_service.process_uploaded_csv")
    @patch("file_processing.services.upload_service.validate_file")
    def test_pipeline_csv_error_propagated_to_caller(self, mock_validate, mock_csv):
        mock_validate.return_value = (True, None)
        mock_csv.return_value = (False, "Gagal parse CSV", None)
 
        success, error, _, data = process_upload(self._csv_upload(b"broken"))
 
        self.assertFalse(success)
        self.assertEqual(error, "Gagal parse CSV")
        self.assertIsNone(data)
 
    @patch("file_processing.services.upload_service.validate_file")
    def test_validation_failure_short_circuits_parsing(self, mock_validate):
        mock_validate.return_value = (False, "File tidak valid")
 
        with patch("file_processing.services.csv_service.parse_csv") as mock_parse:
            process_upload(self._csv_upload(b"id,nama\n1,Alice"))
            mock_parse.assert_not_called()
 
    @patch("file_processing.services.upload_service.validate_file")
    def test_process_upload_returns_four_element_tuple(self, mock_validate):
        mock_validate.return_value = (True, None)
        content = _csv_bytes("x,y", "1,2")
        result = process_upload(self._csv_upload(content))
 
        self.assertEqual(len(result), 4, "process_upload harus return tuple 4 elemen")
 
    @patch("file_processing.services.upload_service.validate_file")
    def test_csv_with_100_rows_all_returned(self, mock_validate):
        mock_validate.return_value = (True, None)
        rows = ["id,nilai"] + [f"{i},{i*10}" for i in range(1, 101)]
        content = _csv_bytes(*rows)
 
        success, _, _, data = process_upload(self._csv_upload(content))
 
        if success:
            self.assertEqual(len(data), 100)
 
    def test_end_to_end_upload_valid_csv_returns_200(self):
        content = _csv_bytes(
            "NIM,Nama,Jurusan",
            "12345,Alice,Teknik Informatika",
            "67890,Bob,Sistem Informasi",
        )
        uploaded = self._csv_upload(content)
        response = self.client.post(UPLOAD_URL, {"file": uploaded})
 
        self.assertEqual(
            response.status_code, 200,
            f"Upload CSV valid harus 200, dapat {response.status_code}",
        )
 
    def test_end_to_end_response_body_contains_data_key(self):
        content = _csv_bytes("id,nama", "1,Alice")
        uploaded = self._csv_upload(content)
        response = self.client.post(UPLOAD_URL, {"file": uploaded})
 
        if response.status_code == 200:
            body = response.json()
            self.assertIn(
                "extracted", body,
                "Response body harus mengandung key 'data' dengan hasil ekstraksi",
            )
 
    def test_end_to_end_response_data_row_count_matches_csv(self):
        rows = ["nim,nama"] + [f"{i},Mahasiswa{i}" for i in range(1, 6)]
        content = _csv_bytes(*rows)
        uploaded = self._csv_upload(content)
        response = self.client.post(UPLOAD_URL, {"file": uploaded})
 
        if response.status_code == 200:
            body = response.json()
            if "extracted" in body:
                self.assertEqual(
                    len(body["extracted"]), 5,
                    "Jumlah row di response harus sama dengan jumlah row di CSV",
                )
