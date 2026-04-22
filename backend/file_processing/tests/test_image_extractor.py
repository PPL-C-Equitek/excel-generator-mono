import os
import tempfile
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from hypothesis import given, settings, strategies as st
from PIL import Image

from file_processing.extractors.image_extractor import ImageExtractor
from file_processing.extractors.image_preprocessors import GrayscaleThresholdPreprocessor
from file_processing.extractors.ocr.base_ocr_engine import BaseOCREngine
from file_processing.extractors.ocr.tesseract_engine import TesseractEngine
from file_processing.services.upload_service import _process_image


class _DummyEngine(BaseOCREngine):
    def __init__(self, text="", confidence=0.0):
        self.text = text
        self.confidence = confidence

    def extract_text(self, image):
        return self.text

    def extract_text_with_confidence(self, image):
        return self.text, self.confidence


class TestImageExtractor(SimpleTestCase):
    @patch("file_processing.extractors.image_extractor.TesseractEngine")
    def test_default_engine_disables_internal_preprocessing(self, mock_tesseract_engine):
        mock_engine = MagicMock()
        mock_tesseract_engine.return_value = mock_engine

        extractor = ImageExtractor()

        mock_tesseract_engine.assert_called_once_with(apply_preprocessing=False)
        self.assertIs(extractor.ocr_engine, mock_engine)

    def _make_temp_image(self, suffix=".png", fmt="PNG"):
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            path = temp_file.name

        image = Image.new("RGB", (32, 32), color="white")
        image.save(path, format=fmt)
        return path

    def test_extract_success_returns_pipeline_shape(self):
        path = self._make_temp_image()
        try:
            extractor = ImageExtractor(
                ocr_engine=_DummyEngine("line one\nline two", 97.5),
                preprocessor=GrayscaleThresholdPreprocessor(apply_thresholding=False),
            )

            result = extractor.extract(path)

            self.assertEqual(result["content"][0]["page"], 1)
            self.assertEqual(result["content"][0]["text"], ["line one", "line two"])
        finally:
            os.unlink(path)

    def test_extract_unsupported_extension_raises(self):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".gif") as temp_file:
            path = temp_file.name
            temp_file.write(b"GIF89a")

        try:
            extractor = ImageExtractor(ocr_engine=_DummyEngine("ignored", 0.0))
            with self.assertRaises(ValueError) as context:
                extractor.extract(path)

            self.assertIn("Unsupported image type", str(context.exception))
        finally:
            os.unlink(path)

    def test_extract_corrupted_image_raises(self):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as temp_file:
            path = temp_file.name
            temp_file.write(b"not-a-real-image")

        try:
            extractor = ImageExtractor(ocr_engine=_DummyEngine("ignored", 0.0))
            with self.assertRaises(ValueError) as context:
                extractor.extract(path)

            self.assertEqual(str(context.exception), "Image file is corrupted or unreadable.")
        finally:
            os.unlink(path)

    def test_extract_unexpected_exception_wrapped_as_value_error(self):
        path = self._make_temp_image()
        try:
            # Mock preprocessor to raise generic Exception
            mock_preprocessor = MagicMock()
            mock_preprocessor.preprocess.side_effect = Exception("unexpected failure")

            extractor = ImageExtractor(
                ocr_engine=MagicMock(),  # won't be reached
                preprocessor=mock_preprocessor,
            )

            with self.assertRaises(ValueError) as context:
                extractor.extract(path)

            self.assertEqual(str(context.exception), "Image OCR extraction failed.")
        finally:
            os.unlink(path)


class TestImagePreprocessor(SimpleTestCase):
    def test_base_preprocessor_is_abstract(self):
        from file_processing.extractors.image_preprocessors import BaseImagePreprocessor

        with self.assertRaises(TypeError):
            BaseImagePreprocessor()

    def test_base_preprocessor_default_method_raises_not_implemented(self):
        from file_processing.extractors.image_preprocessors import BaseImagePreprocessor

        class _CallsSuperPreprocessor(BaseImagePreprocessor):
            def preprocess(self, image):
                return super().preprocess(image)

        preprocessor = _CallsSuperPreprocessor()
        with self.assertRaises(NotImplementedError):
            preprocessor.preprocess(Image.new("RGB", (1, 1), color="white"))

    def test_grayscale_threshold_applied(self):
        image = Image.new("L", (2, 2))
        image.putdata([10, 200, 30, 255])

        preprocessor = GrayscaleThresholdPreprocessor(
            apply_thresholding=True,
            threshold_value=100,
        )

        result = preprocessor.preprocess(image)

        self.assertEqual(result.mode, "1")
        pixels = list(result.getdata())
        self.assertTrue(all(p in (0, 255) for p in pixels))


class TestTesseractConfig(SimpleTestCase):
    @patch("file_processing.extractors.ocr.tesseract_engine.pytesseract")
    def test_tesseract_uses_env_language_default(self, mock_pytesseract):
        mock_pytesseract.pytesseract = MagicMock()

        with patch.dict(
            os.environ,
            {"TESSERACT_LANG": "eng+ind"},
            clear=False,
        ):
            engine = TesseractEngine(apply_preprocessing=False)

        self.assertEqual(engine.lang, "eng+ind")


class TestProcessImage(SimpleTestCase):
    @patch("file_processing.services.upload_service.ImageExtractor")
    def test_process_image_success(self, mock_extractor_cls):
        mock_extractor = MagicMock()
        mock_extractor.extract.return_value = {
            "content": [{"page": 1, "text": ["image text"]}]
        }
        mock_extractor_cls.return_value = mock_extractor

        success, error, data = _process_image("/tmp/example.png")

        self.assertTrue(success)
        self.assertIsNone(error)
        self.assertEqual(data["content"][0]["text"], ["image text"])

    @patch("file_processing.services.upload_service.ImageExtractor")
    def test_process_image_value_error(self, mock_extractor_cls):
        mock_extractor = MagicMock()
        mock_extractor.extract.side_effect = ValueError("Image OCR extraction failed.")
        mock_extractor_cls.return_value = mock_extractor

        success, error, data = _process_image("/tmp/example.png")

        self.assertFalse(success)
        self.assertEqual(error, "Image OCR extraction failed.")
        self.assertIsNone(data)


class TestImageExtractionHypothesis(SimpleTestCase):
    @settings(max_examples=40, deadline=None)
    @given(text=st.text())
    def test_split_lines_invariant_removes_empty_and_trims(self, text):
        lines = ImageExtractor._split_lines(text)

        expected = [line.strip() for line in text.splitlines() if line.strip()]
        self.assertEqual(lines, expected)
        self.assertTrue(all(line.strip() == line for line in lines))
        self.assertTrue(all(line != "" for line in lines))

    @settings(max_examples=40, deadline=None)
    @given(
        pixels=st.lists(
            st.integers(min_value=0, max_value=255),
            min_size=1,
            max_size=256,
        ),
        threshold=st.integers(min_value=0, max_value=255),
    )
    def test_threshold_preprocessor_outputs_binary_pixels(self, pixels, threshold):
        image = Image.new("L", (len(pixels), 1))
        image.putdata(pixels)

        preprocessor = GrayscaleThresholdPreprocessor(
            apply_thresholding=True,
            threshold_value=threshold,
        )
        processed = preprocessor.preprocess(image)

        self.assertEqual(processed.mode, "1")
        output_pixels = list(processed.getdata())
        self.assertTrue(all(pixel in (0, 255) for pixel in output_pixels))

    @settings(max_examples=40, deadline=None)
    @given(ext=st.sampled_from([".PNG", ".JpG", ".jPeG", ".png", ".jpg", ".jpeg"]))
    def test_extension_validation_is_case_insensitive(self, ext):
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as temp_file:
            path = temp_file.name

        try:
            extractor = ImageExtractor(ocr_engine=_DummyEngine("ok", 90.0))
            extractor._validate_extension(path)
        finally:
            os.unlink(path)

    @patch("file_processing.services.upload_service.ImageExtractor")
    def test_process_image_unexpected_exception_returns_generic_error(self, mock_extractor_cls):
        mock_extractor = MagicMock()
        mock_extractor.extract.side_effect = Exception("unexpected")
        mock_extractor_cls.return_value = mock_extractor

        success, error, data = _process_image("/tmp/example.png")

        self.assertFalse(success)
        self.assertEqual(error, "Image OCR extraction failed.")
        self.assertIsNone(data)
