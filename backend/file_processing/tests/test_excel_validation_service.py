from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from file_processing.services import excel_validation_service
from file_processing.services.upload_file_types import EXCEL_CORRUPT_ERROR


class TestExcelValidationService(TestCase):
    def _xlsx_file(self):
        return SimpleUploadedFile(
            "sheet.xlsx",
            b"PK\x03\x04dummy",
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    @patch("file_processing.services.excel_validation_service.check_excel_sheet_count")
    @patch("file_processing.services.excel_validation_service._get_xls_sheet_count", return_value=3)
    @patch("file_processing.services.excel_validation_service._should_parse_as_xls", return_value=True)
    def test_validate_excel_sheet_count_uses_xls_branch(
        self,
        _should_parse,
        _get_xls,
        mock_check,
    ):
        mock_check.return_value = (True, None)

        ok, err = excel_validation_service.validate_excel_sheet_count(self._xlsx_file(), ".xlsx")

        self.assertTrue(ok)
        self.assertIsNone(err)
        mock_check.assert_called_once_with(3)

    @patch("file_processing.services.excel_validation_service.check_excel_sheet_count")
    @patch("file_processing.services.excel_validation_service._get_xlsx_sheet_count", return_value=4)
    @patch("file_processing.services.excel_validation_service._should_parse_as_xls", return_value=False)
    def test_validate_excel_sheet_count_uses_xlsx_branch(
        self,
        _should_parse,
        _get_xlsx,
        mock_check,
    ):
        mock_check.return_value = (True, None)

        ok, err = excel_validation_service.validate_excel_sheet_count(self._xlsx_file(), ".xlsx")

        self.assertTrue(ok)
        self.assertIsNone(err)
        mock_check.assert_called_once_with(4)

    @patch("file_processing.services.excel_validation_service._get_xlsx_sheet_count", side_effect=Exception("boom"))
    @patch("file_processing.services.excel_validation_service._should_parse_as_xls", return_value=False)
    def test_validate_excel_sheet_count_returns_corrupt_on_exception(self, _should_parse, _get_xlsx):
        ok, err = excel_validation_service.validate_excel_sheet_count(self._xlsx_file(), ".xlsx")

        self.assertFalse(ok)
        self.assertEqual(err, EXCEL_CORRUPT_ERROR)
