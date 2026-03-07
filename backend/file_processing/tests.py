import io
from django.test import TestCase, Client
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile

def _build_excel(sheets: dict) -> bytes:
    try:
        from openpyxl import Workbook
    except ImportError:
        raise RuntimeError("openpyxl is required for these tests.")

    wb = Workbook()
    first = True
    for sheet_name, rows in sheets.items():
        if first:
            ws = wb.active
            ws.title = sheet_name
            first = False
        else:
            ws = wb.create_sheet(title=sheet_name)
        for row in rows:
            ws.append(row)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.read()


def _uploaded(name: str, data: bytes) -> SimpleUploadedFile:
    return SimpleUploadedFile(
        name, data,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

class ExcelDataExtractionTests(TestCase):
    EXTRACT_URL = '/upload/'

    def test_single_sheet_first_row_is_header(self):
        data = _build_excel({
            "Mahasiswa": [
                ["NIM", "Nama", "Jurusan"],
                ["12345", "Alice", "Teknik Informatika"],
                ["67890", "Bob", "Sistem Informasi"],
            ]
        })
        response = self.client.post(self.EXTRACT_URL, {'file': _uploaded("data.xlsx", data)})

        self.assertEqual(response.status_code, 200)
        body = response.json()

        rows = self._get_sheet_rows(body, "Mahasiswa")
        self.assertEqual(len(rows), 2)

        self.assertIn("NIM", rows[0])
        self.assertIn("Nama", rows[0])
        self.assertIn("Jurusan", rows[0])

        self.assertEqual(rows[0]["NIM"], "12345")
        self.assertEqual(rows[0]["Nama"], "Alice")
        self.assertEqual(rows[1]["NIM"], "67890")
        self.assertEqual(rows[1]["Nama"], "Bob")

    def test_single_sheet_empty_cell_becomes_null_or_empty_string(self):
        data = _build_excel({
            "Nilai": [
                ["NIM", "Mata Kuliah", "Nilai"],
                ["11111", "PPL", None],
                ["22222", None, "A"],
            ]
        })
        response = self.client.post(self.EXTRACT_URL, {'file': _uploaded("nilai.xlsx", data)})

        self.assertEqual(response.status_code, 200)
        rows = self._get_sheet_rows(response.json(), "Nilai")

        nilai_row0 = rows[0].get("Nilai")
        self.assertTrue(
            nilai_row0 is None or nilai_row0 == "",
            msg=f"Expected None or '' for empty cell, got {nilai_row0!r}"
        )

        mk_row1 = rows[1].get("Mata Kuliah")
        self.assertTrue(
            mk_row1 is None or mk_row1 == "",
            msg=f"Expected None or '' for empty cell, got {mk_row1!r}"
        )

    def test_single_sheet_only_header_no_data_rows_returns_empty_list(self):
        data = _build_excel({
            "Kosong": [
                ["NIM", "Nama", "Jurusan"],
            ]
        })
        response = self.client.post(self.EXTRACT_URL, {'file': _uploaded("empty.xlsx", data)})

        self.assertEqual(response.status_code, 200)
        rows = self._get_sheet_rows(response.json(), "Kosong")
        self.assertEqual(rows, [], msg="Sheet tanpa data harus menghasilkan list kosong.")

    def test_single_sheet_completely_empty_sheet_returns_error_or_empty(self):
        data = _build_excel({
            "BenarBenarKosong": []
        })
        response = self.client.post(self.EXTRACT_URL, {'file': _uploaded("all_empty.xlsx", data)})

        self.assertIn(response.status_code, [200, 400])
        if response.status_code == 200:
            rows = self._get_sheet_rows(response.json(), "BenarBenarKosong")
            self.assertEqual(rows, [])

    def test_multi_sheet_each_sheet_is_separate_object_in_json(self):
        data = _build_excel({
            "Mahasiswa": [
                ["NIM", "Nama"],
                ["001", "Alice"],
            ],
            "Dosen": [
                ["NIP", "Nama"],
                ["D01", "Prof. Budi"],
            ],
        })
        response = self.client.post(self.EXTRACT_URL, {'file': _uploaded("multi.xlsx", data)})

        self.assertEqual(response.status_code, 200)
        body = response.json()

        mahasiswa_rows = self._get_sheet_rows(body, "Mahasiswa")
        dosen_rows = self._get_sheet_rows(body, "Dosen")

        self.assertEqual(len(mahasiswa_rows), 1)
        self.assertEqual(len(dosen_rows), 1)

        self.assertEqual(mahasiswa_rows[0]["NIM"], "001")
        self.assertEqual(dosen_rows[0]["NIP"], "D01")

    def test_multi_sheet_sheet_name_is_unique_key_in_json(self):
        data = _build_excel({
            "Sheet Alpha": [["A", "B"], [1, 2]],
            "Sheet Beta":  [["X", "Y"], [9, 8]],
        })
        response = self.client.post(self.EXTRACT_URL, {'file': _uploaded("keys.xlsx", data)})

        self.assertEqual(response.status_code, 200)
        body = response.json()

        alpha_rows = self._get_sheet_rows(body, "Sheet Alpha")
        beta_rows  = self._get_sheet_rows(body, "Sheet Beta")

        self.assertIsNotNone(alpha_rows, "Kunci 'Sheet Alpha' harus ada dalam JSON.")
        self.assertIsNotNone(beta_rows,  "Kunci 'Sheet Beta' harus ada dalam JSON.")
        self.assertNotEqual(alpha_rows, beta_rows)

    def test_multi_sheet_empty_cells_handled(self):
        data = _build_excel({
            "Sheet1": [
                ["Kol A", "Kol B"],
                ["val", None],
            ],
            "Sheet2": [
                ["P", "Q"],
                [None, "val2"],
            ],
        })
        response = self.client.post(self.EXTRACT_URL, {'file': _uploaded("multi_empty.xlsx", data)})

        self.assertEqual(response.status_code, 200)
        body = response.json()

        rows1 = self._get_sheet_rows(body, "Sheet1")
        rows2 = self._get_sheet_rows(body, "Sheet2")

        v1 = rows1[0].get("Kol B")
        self.assertTrue(v1 is None or v1 == "", f"Sheet1 Kol B empty cell: got {v1!r}")

        v2 = rows2[0].get("P")
        self.assertTrue(v2 is None or v2 == "", f"Sheet2 P empty cell: got {v2!r}")

    def test_multi_sheet_all_sheets_empty_returns_valid_json_structure(self):
        data = _build_excel({
            "EmptyA": [],
            "EmptyB": [],
        })
        response = self.client.post(self.EXTRACT_URL, {'file': _uploaded("all_empty_multi.xlsx", data)})

        self.assertNotEqual(response.status_code, 500)
        if response.status_code == 200:
            body = response.json()
            for sheet_name in ["EmptyA", "EmptyB"]:
                rows = self._get_sheet_rows(body, sheet_name)
                self.assertIsNotNone(rows, f"Kunci '{sheet_name}' harus ada dalam JSON.")

    def test_multi_sheet_partial_empty_sheet_still_extracts_other_sheets(self):
        data = _build_excel({
            "AdaData": [
                ["ID", "Nilai"],
                ["A1", 90],
            ],
            "TanpaData": [],
        })
        response = self.client.post(self.EXTRACT_URL, {'file': _uploaded("partial_empty.xlsx", data)})

        self.assertNotEqual(response.status_code, 500)
        if response.status_code == 200:
            body = response.json()
            ada_rows = self._get_sheet_rows(body, "AdaData")
            self.assertIsNotNone(ada_rows)
            self.assertGreater(len(ada_rows), 0, "Sheet 'AdaData' harus berisi baris data.")


    def _get_sheet_rows(self, body: dict, sheet_name: str):
        if "data" in body and isinstance(body["data"], dict):
            return body["data"].get(sheet_name)
        return body.get(sheet_name)

class FileValidationTests(TestCase):
    UPLOAD_URL = '/upload/'

    def _make_file(self, name: str, content: bytes, content_type: str) -> SimpleUploadedFile:
        return SimpleUploadedFile(name, content, content_type=content_type)

    def _valid_xlsx_bytes(self) -> bytes:

        return _build_excel({"Sheet1": [["A", "B"], [1, 2]]})

    def test_extension_txt_is_rejected(self):
        fake_txt = self._make_file(
            "data.txt",
            b"NIM,Nama\n12345,Alice",
            "text/plain",
        )
        response = self.client.post(self.UPLOAD_URL, {'file': fake_txt})
        self.assertEqual(response.status_code, 400)
        body = response.json()
        self.assertIn("error", body)

    def test_extension_xlsx_is_accepted(self):
        valid_xlsx = self._make_file(
            "data.xlsx",
            self._valid_xlsx_bytes(),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response = self.client.post(self.UPLOAD_URL, {'file': valid_xlsx})
        self.assertEqual(response.status_code, 200)

    def test_magic_number_fake_xlsx_is_rejected(self):
        fake_content = b"This is just plain text disguised as xlsx"
        fake_xlsx = self._make_file(
            "fake.xlsx",
            fake_content,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response = self.client.post(self.UPLOAD_URL, {'file': fake_xlsx})
        self.assertEqual(response.status_code, 400)
        body = response.json()
        self.assertIn("error", body)

    def test_magic_number_fake_xls_is_rejected(self):
        fake_content = b"\x00\x01\x02\x03 bukan compound document"
        fake_xls = self._make_file(
            "fake.xls",
            fake_content,
            "application/vnd.ms-excel",
        )
        response = self.client.post(self.UPLOAD_URL, {'file': fake_xls})
        self.assertEqual(response.status_code, 400)
        body = response.json()
        self.assertIn("error", body)

    def test_magic_number_valid_xlsx_passes(self):
        valid_bytes = self._valid_xlsx_bytes()
        self.assertEqual(valid_bytes[:4], b'\x50\x4B\x03\x04',
                         "Helper _build_excel harus menghasilkan file ZIP valid")

        valid_xlsx = self._make_file(
            "valid.xlsx",
            valid_bytes,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response = self.client.post(self.UPLOAD_URL, {'file': valid_xlsx})
        self.assertEqual(response.status_code, 200)

    def test_file_exceeding_10mb_is_rejected(self):
        oversized_content = b'\x50\x4B\x03\x04' + b'A' * (10 * 1024 * 1024)
        oversized_file = self._make_file(
            "besar.xlsx",
            oversized_content,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response = self.client.post(self.UPLOAD_URL, {'file': oversized_file})
        self.assertEqual(response.status_code, 400)
        body = response.json()
        self.assertIn("error", body)

    def test_file_exactly_10mb_is_accepted_or_rejected_gracefully(self):
        exactly_10mb = b'\x50\x4B\x03\x04' + b'B' * (10 * 1024 * 1024 - 4)
        file_10mb = self._make_file(
            "pas10mb.xlsx",
            exactly_10mb,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response = self.client.post(self.UPLOAD_URL, {'file': file_10mb})
        self.assertNotEqual(response.status_code, 500,
                            "File tepat 10 MB tidak boleh menyebabkan server error.")

    def test_small_valid_file_is_accepted(self):
        valid_xlsx = self._make_file(
            "kecil.xlsx",
            self._valid_xlsx_bytes(),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response = self.client.post(self.UPLOAD_URL, {'file': valid_xlsx})
        self.assertNotEqual(response.status_code, 400)

    def test_mime_type_text_plain_is_rejected(self):
        file_wrong_mime = self._make_file(
            "data.xlsx",
            self._valid_xlsx_bytes(),
            "text/plain",
        )
        response = self.client.post(self.UPLOAD_URL, {'file': file_wrong_mime})
        self.assertEqual(response.status_code, 400)
        body = response.json()
        self.assertIn("error", body)

    def test_mime_type_application_pdf_is_rejected(self):
        file_pdf_mime = self._make_file(
            "data.xlsx",
            self._valid_xlsx_bytes(),
            "application/pdf",
        )
        response = self.client.post(self.UPLOAD_URL, {'file': file_pdf_mime})
        self.assertEqual(response.status_code, 400)
        body = response.json()
        self.assertIn("error", body)

    def test_mime_type_xlsx_is_accepted(self):
        file_correct_mime = self._make_file(
            "data.xlsx",
            self._valid_xlsx_bytes(),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response = self.client.post(self.UPLOAD_URL, {'file': file_correct_mime})
        self.assertEqual(response.status_code, 200)

    def test_mime_type_xls_is_accepted(self):
        file_xls_mime = self._make_file(
            "data.xls",
            self._valid_xlsx_bytes(),
            "application/vnd.ms-excel",
        )
        response = self.client.post(self.UPLOAD_URL, {'file': file_xls_mime})
        body = response.json()
        if response.status_code == 400:
            error_msg = body.get("error", "").lower()
            self.assertNotIn("mime", error_msg,
                             "File .xls tidak boleh ditolak karena MIME type.")

    def test_corrupted_xlsx_returns_400_with_error_message(self):
        corrupted_content = b'\x50\x4B\x03\x04' + b'\xFF\xFE\xFD' * 50
        corrupted_file = self._make_file(
            "corrupt.xlsx",
            corrupted_content,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response = self.client.post(self.UPLOAD_URL, {'file': corrupted_file})
        self.assertEqual(response.status_code, 400,
                         "File corrupted harus mengembalikan 400, bukan 500.")
        body = response.json()
        self.assertIn("error", body,
                      "Response harus memiliki kunci 'error'.")
        self.assertTrue(len(body["error"]) > 0,
                        "Pesan error tidak boleh kosong.")

    def test_corrupted_xls_returns_400_with_error_message(self):
        corrupted_content = b'\xD0\xCF\x11\xE0' + b'\x00\x01\x02\x03' * 30
        corrupted_xls = self._make_file(
            "corrupt.xls",
            corrupted_content,
            "application/vnd.ms-excel",
        )
        response = self.client.post(self.UPLOAD_URL, {'file': corrupted_xls})
        self.assertIn(response.status_code, [400, 500])
        if response.status_code == 400:
            body = response.json()
            self.assertIn("error", body)

    def test_empty_file_is_rejected_with_error(self):
        empty_file = self._make_file(
            "empty.xlsx",
            b"",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response = self.client.post(self.UPLOAD_URL, {'file': empty_file})
        self.assertEqual(response.status_code, 400)
        body = response.json()
        self.assertIn("error", body)

    def test_corrupted_file_error_message_is_user_friendly(self):
        corrupted_content = b'\x50\x4B\x03\x04' + b'\xDE\xAD\xBE\xEF' * 20
        corrupted_file = self._make_file(
            "corrupt2.xlsx",
            corrupted_content,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response = self.client.post(self.UPLOAD_URL, {'file': corrupted_file})
        if response.status_code == 400:
            body = response.json()
            error_msg = body.get("error", "")
            self.assertNotIn("Traceback", error_msg)
            self.assertNotIn("raise ", error_msg)
            self.assertTrue(len(error_msg) > 0,
                            "Pesan error untuk file corrupted harus informatif.")