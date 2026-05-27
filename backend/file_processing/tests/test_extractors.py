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
        mock_convert.assert_called_once_with("dummy_scanned_path.pdf", dpi=400)

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
        mock_convert.assert_called_once_with("dummy_multi_page.pdf", dpi=400)

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
        mock_convert.assert_called_once_with("dummy.pdf", first_page=2, last_page=2, dpi=400)

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
        mock_convert.assert_called_once_with("dummy.pdf", dpi=400)

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
        mock_convert.assert_called_once_with("dummy.pdf", dpi=400)

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
        mock_convert.assert_called_once_with("dummy.pdf", first_page=3, last_page=3, dpi=400)

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

    def test_extract_without_engine_raises(self):
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)

            extractor = PdfOcrExtractor()

            with self.assertRaises(RuntimeError):
                extractor.extract("dummy.pdf")

    def test_extract_pages_without_engine_raises(self):
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)

            extractor = PdfOcrExtractor()

            with self.assertRaises(RuntimeError):
                extractor.extract_pages("dummy.pdf")

    @patch("file_processing.extractors.pdf_ocr_extractor.convert_from_path")
    def test_convert_pages_specific_no_images(self, mock_convert):
        mock_convert.return_value = []

        extractor = PdfOcrExtractor()
        result = extractor.convert_pages("dummy.pdf", page_numbers=[5])

        self.assertEqual(result, [])

    @patch("file_processing.extractors.pdf_ocr_extractor.convert_from_path")
    def test_extract_pages_specific_no_image(self, mock_convert):

        mock_convert.return_value = []

        class MockEngine(BaseOCREngine):
            def extract_text(self, image): return "x"
            def extract_text_with_confidence(self, image): return "x", 1.0

        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)

            extractor = PdfOcrExtractor(ocr_engine=MockEngine())
            result = extractor.extract_pages("dummy.pdf", page_numbers=[3])

        self.assertEqual(result[0]["text"], "")
        self.assertEqual(result[0]["confidence"], 0.0)

class TestTesseractEngine(TestCase):

    @patch("file_processing.extractors.ocr.tesseract_engine.pytesseract")
    def test_tesseract_extract(self, mock_pytesseract):
        mock_pytesseract.image_to_string.return_value = "hello"

        engine = TesseractEngine(apply_preprocessing=False)
        result = engine.extract_text("image")

        self.assertEqual(result, "hello")
        # Multi-PSM strategy calls image_to_string for each PSM mode [3, 6, 4]
        self.assertEqual(mock_pytesseract.image_to_string.call_count, 3)

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
            "conf": [-1, 90.0, 80.0, -1],
            "block_num": [1, 1, 1, 1],
            "par_num": [1, 1, 1, 1],
            "line_num": [1, 1, 1, 1],
        }
        
        engine = TesseractEngine(apply_preprocessing=True)
        text, conf = engine.extract_text_with_confidence("raw_image")
        
        self.assertEqual(text, "Hello world")
        self.assertEqual(conf, 85.0)  # (90 + 80) / 2
        mock_preprocess.assert_called_once_with("raw_image")
        # Early-exit at confidence threshold (85.0) on the first PSM.
        self.assertEqual(mock_pytesseract.image_to_data.call_count, 1)

    @patch("file_processing.extractors.ocr.tesseract_engine.pytesseract")
    def test_tesseract_extract_metadata_with_custom_config_and_missing_geometry(self, mock_pytesseract):
        mock_pytesseract.Output.DICT = "dict"
        mock_pytesseract.image_to_data.return_value = {
            "text": ["alpha"],
            "conf": [91.0],
            "block_num": [1],
            "par_num": [1],
            "line_num": [1],
        }

        engine = TesseractEngine(apply_preprocessing=False, custom_config="--psm 6")
        result = engine.extract_text_with_metadata("img")

        self.assertEqual(result["text"], "alpha")
        self.assertEqual(result["word_details"][0]["left"], 0)
        self.assertEqual(result["word_details"][0]["top"], 0)
        self.assertEqual(result["word_details"][0]["width"], 0)
        self.assertEqual(result["word_details"][0]["height"], 0)
        self.assertEqual(mock_pytesseract.image_to_data.call_count, 1)

    @patch("file_processing.extractors.ocr.tesseract_engine.pytesseract", None)
    def test_tesseract_extract_metadata_not_installed(self):
        engine = TesseractEngine(apply_preprocessing=False)

        with self.assertRaises(ImportError):
            engine.extract_text_with_metadata("img")

    @patch("file_processing.extractors.ocr.tesseract_engine.pytesseract")
    def test_tesseract_extract_metadata_uses_safe_default_for_short_geometry_lists(self, mock_pytesseract):
        mock_pytesseract.Output.DICT = "dict"
        mock_pytesseract.image_to_data.return_value = {
            "text": ["alpha", "beta"],
            "conf": [91.0, 89.0],
            "block_num": [1, 1],
            "par_num": [1, 1],
            "line_num": [1, 1],
            "left": [11],
            "top": [22],
            "width": [33],
            "height": [44],
        }

        engine = TesseractEngine(apply_preprocessing=False, custom_config="--psm 6")
        result = engine.extract_text_with_metadata("img")

        self.assertEqual(result["word_details"][0]["left"], 11)
        self.assertEqual(result["word_details"][1]["left"], 0)
        self.assertEqual(result["word_details"][1]["top"], 0)
        self.assertEqual(result["word_details"][1]["width"], 0)
        self.assertEqual(result["word_details"][1]["height"], 0)

    @patch("file_processing.extractors.ocr.tesseract_engine.pytesseract")
    def test_tesseract_extract_metadata_no_early_exit_when_confidence_stays_low(self, mock_pytesseract):
        mock_pytesseract.Output.DICT = "dict"
        mock_pytesseract.image_to_data.side_effect = [
            {
                "text": ["one"],
                "conf": [60.0],
                "block_num": [1],
                "par_num": [1],
                "line_num": [1],
            },
            {
                "text": ["two"],
                "conf": [70.0],
                "block_num": [1],
                "par_num": [1],
                "line_num": [1],
            },
        ]

        engine = TesseractEngine(apply_preprocessing=False, psm_modes=[3, 6])
        result = engine.extract_text_with_metadata("img")

        self.assertEqual(result["text"], "two")
        self.assertEqual(mock_pytesseract.image_to_data.call_count, 2)

    @patch("file_processing.extractors.ocr.tesseract_engine.pytesseract")
    def test_tesseract_extract_metadata_early_exit_when_confidence_is_high(self, mock_pytesseract):
        mock_pytesseract.Output.DICT = "dict"
        mock_pytesseract.image_to_data.return_value = {
            "text": ["high"],
            "conf": [96.0],
            "block_num": [1],
            "par_num": [1],
            "line_num": [1],
        }

        engine = TesseractEngine(apply_preprocessing=False, psm_modes=[3, 6])
        result = engine.extract_text_with_metadata("img")

        self.assertEqual(result["text"], "high")
        self.assertEqual(mock_pytesseract.image_to_data.call_count, 1)

    @patch("file_processing.extractors.ocr.tesseract_engine.pytesseract")
    def test_tesseract_extract_metadata_selects_best_psm(self, mock_pytesseract):
        mock_pytesseract.Output.DICT = "dict"
        mock_pytesseract.image_to_data.side_effect = [
            {
                "text": ["one"],
                "conf": [60.0],
                "block_num": [1],
                "par_num": [1],
                "line_num": [1],
                "left": [1],
                "top": [2],
                "width": [3],
                "height": [4],
            },
            {
                "text": ["two"],
                "conf": [95.0],
                "block_num": [1],
                "par_num": [1],
                "line_num": [1],
                "left": [5],
                "top": [6],
                "width": [7],
                "height": [8],
            },
        ]

        engine = TesseractEngine(apply_preprocessing=False, psm_modes=[3, 6])
        result = engine.extract_text_with_metadata("img")

        self.assertEqual(result["text"], "two")
        self.assertEqual(result["avg_confidence"], 95.0)
        self.assertEqual(mock_pytesseract.image_to_data.call_count, 2)

    @patch("file_processing.extractors.ocr.tesseract_engine.pytesseract")
    def test_tesseract_extract_metadata_keeps_existing_winner_when_later_result_is_worse(self, mock_pytesseract):
        mock_pytesseract.Output.DICT = "dict"
        mock_pytesseract.image_to_data.side_effect = [
            {
                "text": ["better"],
                "conf": [70.0],
                "block_num": [1],
                "par_num": [1],
                "line_num": [1],
            },
            {
                "text": ["worse"],
                "conf": [60.0],
                "block_num": [1],
                "par_num": [1],
                "line_num": [1],
            },
        ]

        engine = TesseractEngine(apply_preprocessing=False, psm_modes=[3, 6])
        result = engine.extract_text_with_metadata("img")

        self.assertEqual(result["text"], "better")
        self.assertEqual(result["avg_confidence"], 70.0)
        self.assertEqual(mock_pytesseract.image_to_data.call_count, 2)

    @patch("file_processing.extractors.ocr.tesseract_engine.pytesseract")
    def test_tesseract_confidence_no_early_exit_when_below_threshold(self, mock_pytesseract):
        mock_pytesseract.Output.DICT = "dict"
        mock_pytesseract.image_to_data.side_effect = [
            {
                "text": ["Low"],
                "conf": [60.0],
                "block_num": [1],
                "par_num": [1],
                "line_num": [1],
            },
            {
                "text": ["Better"],
                "conf": [70.0],
                "block_num": [1],
                "par_num": [1],
                "line_num": [1],
            },
            {
                "text": ["Best"],
                "conf": [80.0],
                "block_num": [1],
                "par_num": [1],
                "line_num": [1],
            },
        ]

        engine = TesseractEngine(apply_preprocessing=False)
        text, conf = engine.extract_text_with_confidence("img")

        self.assertEqual(text, "Best")
        self.assertEqual(conf, 80.0)
        self.assertEqual(mock_pytesseract.image_to_data.call_count, 3)

    @patch("file_processing.extractors.ocr.tesseract_engine.pytesseract")
    @patch("file_processing.extractors.ocr.tesseract_engine.preprocess_image")
    def test_tesseract_preprocessing_failure_fallback(self, mock_preprocess, mock_pytesseract):
        mock_preprocess.side_effect = Exception("OpenCV Error")
        mock_pytesseract.image_to_string.return_value = "hello"
        
        engine = TesseractEngine(apply_preprocessing=True)
        result = engine.extract_text("raw_image")
        
        self.assertEqual(result, "hello")
        # Preprocessing failed → original image used; multi-PSM calls for each mode
        self.assertEqual(mock_pytesseract.image_to_string.call_count, 3)

    @patch("file_processing.extractors.ocr.tesseract_engine.pytesseract")
    def test_custom_config_extract(self, mock_pytesseract):
        """Cover custom_config branch in extract_text."""
        mock_pytesseract.image_to_string.return_value = "custom result"

        engine = TesseractEngine(
            custom_config="--psm 6",
            apply_preprocessing=False,
        )

        result = engine.extract_text("image")

        self.assertEqual(result, "custom result")
        mock_pytesseract.image_to_string.assert_called_once()


    @patch("file_processing.extractors.ocr.tesseract_engine.pytesseract")
    def test_custom_config_extract_with_confidence(self, mock_pytesseract):
        """Cover custom_config branch in extract_text_with_confidence."""
        mock_pytesseract.Output.DICT = "dict"

        mock_pytesseract.image_to_data.return_value = {
            "text": ["Test"],
            "conf": [90],
            "block_num": [1],
            "par_num": [1],
            "line_num": [1],
        }

        engine = TesseractEngine(
            custom_config="--psm 6",
            apply_preprocessing=False,
        )

        text, conf = engine.extract_text_with_confidence("img")

        self.assertEqual(text, "Test")
        self.assertEqual(conf, 90.0)


    @patch("file_processing.extractors.ocr.tesseract_engine.pytesseract")
    def test_run_tesseract_data_no_valid_conf(self, mock_pytesseract):
        """Cover avg_conf fallback when no valid confidences."""
        mock_pytesseract.Output.DICT = "dict"

        mock_pytesseract.image_to_data.return_value = {
            "text": ["Hello"],
            "conf": [-1],
            "block_num": [1],
            "par_num": [1],
            "line_num": [1],
        }

        engine = TesseractEngine(apply_preprocessing=False)

        text, conf = engine.extract_text_with_confidence("img")

        self.assertEqual(text, "Hello")
        self.assertEqual(conf, 0.0)

    @patch("file_processing.extractors.ocr.tesseract_engine.pytesseract", None)
    def test_tesseract_confidence_not_installed(self):
        engine = TesseractEngine()

        with self.assertRaises(ImportError):
            engine.extract_text_with_confidence("image")


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

    def test_extract_text_with_confidence_default(self):
        """
        Ensure the default implementation calls extract_text()
        and returns confidence = 0.0
        """

        class Dummy(BaseOCREngine):
            def extract_text(self, image):
                return "hello"

        engine = Dummy()

        text, confidence = engine.extract_text_with_confidence(None)

        self.assertEqual(text, "hello")
        self.assertEqual(confidence, 0.0)
