import io
from django.test import TestCase, Client
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile

class ExcelParsingErrorHandlingTests(TestCase):
    def setUp(self):
        self.client = Client()
        # TODO: Sesuaikan dengan URL endpoint API yang sebenarnya
        # self.upload_url = reverse('nama-url-upload') 
        self.upload_url = '/api/file-processing/upload/' 

    def test_upload_without_file_returns_400(self):
        response = self.client.post(self.upload_url, {})
        self.assertEqual(response.status_code, 400)
        self.assertIn('error', response.json())
        self.assertEqual(response.json()['error'], 'No file provided.')

    def test_upload_invalid_file_extension_returns_400(self):
        text_file = SimpleUploadedFile("test.txt", b"ini bukan file excel", content_type="text/plain")
        response = self.client.post(self.upload_url, {'file': text_file})
        self.assertEqual(response.status_code, 400)
        self.assertIn('error', response.json())
        self.assertIn('invalid file format', response.json()['error'].lower())

    def test_upload_corrupted_excel_file_returns_400(self):
        corrupted_file = SimpleUploadedFile(
            "corrupted.xlsx", 
            b"data binary sembarangan yang tidak valid untuk excel", 
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response = self.client.post(self.upload_url, {'file': corrupted_file})
        
        self.assertEqual(response.status_code, 400)
        self.assertIn('error', response.json())
        response_error = response.json()['error'].lower()
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
        self.assertIn('error', response.json())
        self.assertIn('sheet', response.json()['error'].lower()) 

    def test_excel_missing_required_columns_returns_400(self):
        excel_bytes = self.create_dummy_excel(sheet_title="Data Mahasiswa", headers=['NIM', 'Nama Salah', 'Jurusan'])
        excel_file = SimpleUploadedFile("test.xlsx", excel_bytes, 
                                        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        
        response = self.client.post(self.upload_url, {'file': excel_file})
        self.assertEqual(response.status_code, 400)
        self.assertIn('error', response.json())
        self.assertIn('column', response.json()['error'].lower())

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
