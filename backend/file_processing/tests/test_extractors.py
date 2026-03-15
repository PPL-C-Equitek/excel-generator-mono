from unittest import TestCase
from unittest.mock import patch, MagicMock

from file_processing.extractors.ocr.base_ocr_engine import BaseOCREngine
from file_processing.extractors.pdf_ocr_extractor import PdfOcrExtractor
from file_processing.extractors.ocr.tesseract_engine import TesseractEngine

class DummyOCREngine(BaseOCREngine):
    def __init__(self, text_to_return=""):
        self.text_to_return = text_to_return

    def extract_text(self, image) -> str:
        return self.text_to_return


class TestPdfOcrExtractor(TestCase):
    @patch('file_processing.extractors.pdf_ocr_extractor.convert_from_path')
    def test_ocr_extracts_text_from_scanned_pdf(self, mock_convert):
        mock_convert.return_value = [MagicMock()]
        
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            engine = DummyOCREngine(text_to_return="Sample Scanned Text")
            extractor = PdfOcrExtractor(ocr_engine=engine)
            extracted_text = extractor.extract("dummy_scanned_path.pdf")
        
        self.assertIn("Sample Scanned Text", extracted_text)
        mock_convert.assert_called_once_with("dummy_scanned_path.pdf", dpi=300)

    @patch('file_processing.extractors.pdf_ocr_extractor.convert_from_path')
    def test_multiple_pages_ocr(self, mock_convert):
        mock_convert.return_value = [MagicMock(), MagicMock(), MagicMock()]
        
        class MultiPageDummyEngine(BaseOCREngine):
            def __init__(self):
                self.page_count = 0
            
            def extract_text(self, image) -> str:
                self.page_count += 1
                return f"Text from page {self.page_count}"

        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            engine = MultiPageDummyEngine()
            extractor = PdfOcrExtractor(ocr_engine=engine)
            extracted_text = extractor.extract("dummy_multi_page.pdf")
        
        self.assertIn("Text from page 1", extracted_text)
        self.assertIn("Text from page 2", extracted_text)
        self.assertIn("Text from page 3", extracted_text)
        mock_convert.assert_called_once_with("dummy_multi_page.pdf", dpi=300)

    @patch('file_processing.extractors.pdf_ocr_extractor.convert_from_path')
    def test_extract_pages_specific(self, mock_convert):
        mock_convert.return_value = [MagicMock()]
        
        class MockEngine(BaseOCREngine):
            def extract_text(self, image): return "test"
            def extract_text_with_confidence(self, image): return "Text", 99.0

        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            extractor = PdfOcrExtractor(ocr_engine=MockEngine())
            results = extractor.extract_pages("dummy.pdf", page_numbers=[2])
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["page"], 2)
        self.assertEqual(results[0]["text"], "Text")
        self.assertEqual(results[0]["confidence"], 99.0)
        mock_convert.assert_called_once_with("dummy.pdf", first_page=2, last_page=2, dpi=300)

    @patch('file_processing.extractors.pdf_ocr_extractor.convert_from_path')
    def test_extract_pages_all(self, mock_convert):
        mock_convert.return_value = [MagicMock(), MagicMock()]
        
        class MockEngine(BaseOCREngine):
            def extract_text(self, image): return "test"
            def extract_text_with_confidence(self, image): return "Text", 85.0

        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            extractor = PdfOcrExtractor(ocr_engine=MockEngine())
            results = extractor.extract_pages("dummy.pdf")
        
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["page"], 1)
        self.assertEqual(results[1]["page"], 2)
        mock_convert.assert_called_once_with("dummy.pdf", dpi=300)

    def test_ocr_engine_abstraction(self):
        """PdfOcrExtractor can be created without an engine (new API)."""
        extractor = PdfOcrExtractor()
        self.assertIsNone(extractor.ocr_engine)

    @patch('file_processing.extractors.pdf_ocr_extractor.convert_from_path')
    def test_convert_pages_all(self, mock_convert):
        """convert_pages() returns (page_num, image) tuples for all pages."""
        mock_images = [MagicMock(), MagicMock()]
        mock_convert.return_value = mock_images

        extractor = PdfOcrExtractor()
        result = extractor.convert_pages("dummy.pdf")

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0][0], 1)  # page number
        self.assertEqual(result[1][0], 2)
        self.assertIs(result[0][1], mock_images[0])  # image
        self.assertIs(result[1][1], mock_images[1])
        mock_convert.assert_called_once_with("dummy.pdf", dpi=300)

    @patch('file_processing.extractors.pdf_ocr_extractor.convert_from_path')
    def test_convert_pages_specific(self, mock_convert):
        """convert_pages() returns only requested page numbers."""
        mock_image = MagicMock()
        mock_convert.return_value = [mock_image]

        extractor = PdfOcrExtractor()
        result = extractor.convert_pages("dummy.pdf", page_numbers=[3])

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][0], 3)
        self.assertIs(result[0][1], mock_image)
        mock_convert.assert_called_once_with("dummy.pdf", first_page=3, last_page=3, dpi=300)

    @patch('file_processing.extractors.pdf_ocr_extractor.convert_from_path')
    def test_convert_pages_empty(self, mock_convert):
        """convert_pages() returns empty list when no images."""
        mock_convert.return_value = []

        extractor = PdfOcrExtractor()
        result = extractor.convert_pages("dummy.pdf")

        self.assertEqual(result, [])
        
    def test_accuracy_threshold(self):
        from file_processing.utils.metrics import calculate_accuracy
        
        ground_truth = "Hello World"
        extracted = "Hello W0rld"
        
        acc = calculate_accuracy(ground_truth, extracted)
        self.assertGreaterEqual(acc, 0.90)
        
        bad_extracted = "Hxlzo"
        bad_acc = calculate_accuracy(ground_truth, bad_extracted)
        self.assertLess(bad_acc, 0.90)

    @patch('file_processing.extractors.pdf_ocr_extractor.convert_from_path')
    def test_error_handling_corrupted_pdf(self, mock_convert):
        from pdf2image.exceptions import PDFPageCountError

        mock_convert.side_effect = PDFPageCountError("Unable to get page count.")

        engine = DummyOCREngine()
        extractor = PdfOcrExtractor(ocr_engine=engine)

        with self.assertRaises(ValueError) as context:
            extractor.extract("corrupted.pdf")

        self.assertIn("corrupt", str(context.exception).lower())

    def test_accuracy_empty_strings(self):
        from file_processing.utils.metrics import calculate_accuracy

        acc = calculate_accuracy("", "")
        self.assertEqual(acc, 1.0)

    @patch('file_processing.extractors.pdf_ocr_extractor.convert_from_path')
    def test_poppler_not_installed(self, mock_convert):
        from pdf2image.exceptions import PDFInfoNotInstalledError

        mock_convert.side_effect = PDFInfoNotInstalledError("poppler missing")

        extractor = PdfOcrExtractor(DummyOCREngine())

        with self.assertRaises(RuntimeError) as context:
            extractor.extract("file.pdf")

        self.assertIn("poppler", str(context.exception).lower())

    @patch('file_processing.extractors.pdf_ocr_extractor.convert_from_path')
    def test_pdf_pagecount_error(self, mock_convert):
        from pdf2image.exceptions import PDFPageCountError

        mock_convert.side_effect = PDFPageCountError("page count failed")

        extractor = PdfOcrExtractor(DummyOCREngine())

        with self.assertRaises(ValueError):
            extractor.extract("broken.pdf")

    @patch('file_processing.extractors.pdf_ocr_extractor.convert_from_path')
    def test_pdf_syntax_error(self, mock_convert):
        from pdf2image.exceptions import PDFSyntaxError

        mock_convert.side_effect = PDFSyntaxError("syntax error")

        extractor = PdfOcrExtractor(DummyOCREngine())

        with self.assertRaises(ValueError):
            extractor.extract("malformed.pdf")

    @patch('file_processing.extractors.pdf_ocr_extractor.convert_from_path')
    def test_empty_ocr_result(self, mock_convert):
        mock_convert.return_value = [MagicMock()]

        engine = DummyOCREngine(text_to_return="")
        extractor = PdfOcrExtractor(engine)

        result = extractor.extract("file.pdf")

        self.assertEqual(result, "")

    @patch("file_processing.extractors.pdf_ocr_extractor.convert_from_path")
    def test_unexpected_conversion_error(self, mock_convert):
        mock_convert.side_effect = Exception("random failure")

        extractor = PdfOcrExtractor(DummyOCREngine())

        with self.assertRaises(RuntimeError) as context:
            extractor.extract("file.pdf")

        self.assertIn("Unexpected error", str(context.exception))

class TestTesseractEngine(TestCase):

    @patch("file_processing.extractors.ocr.tesseract_engine.pytesseract")
    def test_tesseract_extract(self, mock_pytesseract):
        mock_pytesseract.image_to_string.return_value = "hello"

        engine = TesseractEngine(apply_preprocessing=False)
        result = engine.extract_text("image")

        self.assertEqual(result, "hello")
        mock_pytesseract.image_to_string.assert_called_once_with("image", lang="eng+ind", config="--oem 3 --psm 6")

    @patch("file_processing.extractors.ocr.tesseract_engine.pytesseract", None)
    def test_tesseract_not_installed(self):
        engine = TesseractEngine()
        with self.assertRaises(ImportError):
            engine.extract_text("image")
            
    @patch("file_processing.extractors.ocr.tesseract_engine.pytesseract")
    @patch("file_processing.extractors.ocr.tesseract_engine.preprocess_image")
    def test_tesseract_with_preprocessing_and_confidence(self, mock_preprocess, mock_pytesseract):
        mock_preprocess.return_value = "processed_image"
        
        mock_pytesseract.Output.DICT = "dict"
        mock_pytesseract.image_to_data.return_value = {
            "text": ["", "Hello", "world", ""],
            "conf": [-1, 90.0, 80.0, -1]
        }
        
        engine = TesseractEngine(apply_preprocessing=True)
        text, conf = engine.extract_text_with_confidence("raw_image")
        
        self.assertEqual(text, "Hello world")
        self.assertEqual(conf, 85.0)  # (90 + 80) / 2
        mock_preprocess.assert_called_once_with("raw_image")
        mock_pytesseract.image_to_data.assert_called_once_with(
            "processed_image", lang="eng+ind", config="--oem 3 --psm 6", output_type="dict"
        )

    @patch("file_processing.extractors.ocr.tesseract_engine.pytesseract")
    @patch("file_processing.extractors.ocr.tesseract_engine.preprocess_image")
    def test_tesseract_preprocessing_failure_fallback(self, mock_preprocess, mock_pytesseract):
        mock_preprocess.side_effect = Exception("OpenCV Error")
        mock_pytesseract.image_to_string.return_value = "hello"
        
        engine = TesseractEngine(apply_preprocessing=True)
        result = engine.extract_text("raw_image")
        
        self.assertEqual(result, "hello")
        mock_pytesseract.image_to_string.assert_called_once_with(
            "raw_image", lang="eng+ind", config="--oem 3 --psm 6"
        )

class TestEasyOCREngine(TestCase):

    @patch("file_processing.extractors.ocr.easyocr_engine.easyocr")
    def test_easyocr_extract(self, mock_easyocr):
        mock_reader = MagicMock()
        mock_reader.readtext.return_value = [
            ([0,0,1,1], "Line 1", 0.95),
            ([0,0,1,1], "Line 2", 0.85)
        ]
        mock_easyocr.Reader.return_value = mock_reader
        
        from file_processing.extractors.ocr.easyocr_engine import EasyOCREngine
        engine = EasyOCREngine(languages=["en"], gpu=False)
        result = engine.extract_text("image")
        
        self.assertEqual(result, "Line 1\nLine 2")
        mock_easyocr.Reader.assert_called_once_with(["en"], gpu=False)

    @patch("file_processing.extractors.ocr.easyocr_engine.easyocr")
    def test_easyocr_extract_with_confidence(self, mock_easyocr):
        mock_reader = MagicMock()
        mock_reader.readtext.return_value = [
            ([0,0,1,1], "Line 1", 0.95),
            ([0,0,1,1], "Line 2", 0.85)
        ]
        mock_easyocr.Reader.return_value = mock_reader
        
        import file_processing.extractors.ocr.easyocr_engine as easyocr_module
        easyocr_module._reader_cache = None
        
        engine = easyocr_module.EasyOCREngine()
        text, conf = engine.extract_text_with_confidence("image")
        
        self.assertEqual(text, "Line 1\nLine 2")
        self.assertEqual(conf, 90.0)  # (0.95 + 0.85) / 2 * 100

class TestBaseOCREngine(TestCase):

    def test_base_ocr_engine_abstract(self):

        class Dummy(BaseOCREngine):
            def extract_text(self, image):
                return "text"

        d = Dummy()
        self.assertEqual(d.extract_text(None), "text")

    def test_base_ocr_engine_concrete_implementation(self):

        class DummyEngine(BaseOCREngine):
            def extract_text(self, image):
                return "dummy"

        engine = DummyEngine()

        self.assertEqual(engine.extract_text(None), "dummy")

    def test_base_ocr_engine_not_implemented(self):
        class Dummy(BaseOCREngine):
            def extract_text(self, image):
                return super().extract_text(image)

        engine = Dummy()

        with self.assertRaises(NotImplementedError):
            engine.extract_text(None)
