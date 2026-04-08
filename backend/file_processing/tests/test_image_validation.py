import io
import warnings
from unittest.mock import patch

from django.test import SimpleTestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from file_processing.utils.image_validators import (
    validate_image_extension,
    validate_image_size,
    validate_image_magic_number,
    validate_image_integrity,
)
from file_processing.services.image_validation_service import (
    validate_image,
    validate_image_mime_type,
)
from file_processing.services.upload_service import validate_file

def _make_image_bytes(fmt="PNG", size=(100, 100), mode="RGB"):
    """Helper: create real image bytes in the given format."""
    img = Image.new(mode, size, color="red")
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    buf.seek(0)
    return buf.read()


def _make_uploaded(name, content, content_type="application/octet-stream"):
    return SimpleUploadedFile(name, content, content_type=content_type)


class TestValidateImageExtension(SimpleTestCase):
    """validate_image_extension()"""

    def test_png_valid(self):
        f = _make_uploaded("photo.png", b"x")
        is_valid, err = validate_image_extension(f)
        self.assertTrue(is_valid)
        self.assertIsNone(err)

    def test_jpg_valid(self):
        f = _make_uploaded("photo.jpg", b"x")
        is_valid, err = validate_image_extension(f)
        self.assertTrue(is_valid)
        self.assertIsNone(err)

    def test_jpeg_valid(self):
        f = _make_uploaded("photo.jpeg", b"x")
        is_valid, err = validate_image_extension(f)
        self.assertTrue(is_valid)
        self.assertIsNone(err)

    def test_wrong_extension_rejected(self):
        f = _make_uploaded("photo.gif", b"x")
        is_valid, err = validate_image_extension(f)
        self.assertFalse(is_valid)
        self.assertIn("Unsupported image", err)

    def test_case_insensitive(self):
        f = _make_uploaded("photo.PNG", b"x")
        is_valid, _ = validate_image_extension(f)
        self.assertTrue(is_valid)


class TestValidateImageSize(SimpleTestCase):
    """validate_image_size()"""

    def test_small_file_passes(self):
        f = _make_uploaded("ok.png", b"x" * 100)
        is_valid, err = validate_image_size(f)
        self.assertTrue(is_valid)
        self.assertIsNone(err)

    def test_file_over_10mb_rejected(self):
        big = b"x" * (10 * 1024 * 1024 + 1)
        f = _make_uploaded("big.png", big)
        is_valid, err = validate_image_size(f)
        self.assertFalse(is_valid)
        self.assertIn("10MB", err)


class TestValidateImageMagicNumber(SimpleTestCase):
    """validate_image_magic_number()"""

    def test_png_magic_valid(self):
        content = _make_image_bytes("PNG")
        f = _make_uploaded("img.png", content)
        is_valid, err = validate_image_magic_number(f)
        self.assertTrue(is_valid)
        self.assertIsNone(err)

    def test_jpg_magic_valid(self):
        content = _make_image_bytes("JPEG")
        f = _make_uploaded("img.jpg", content)
        is_valid, err = validate_image_magic_number(f)
        self.assertTrue(is_valid)
        self.assertIsNone(err)

    def test_fake_image_rejected(self):
        """A .txt file renamed to .png should fail magic number check."""
        f = _make_uploaded("fake.png", b"This is plain text, not an image")
        is_valid, err = validate_image_magic_number(f)
        self.assertFalse(is_valid)
        self.assertIn("does not match", err)

    def test_png_with_only_4_byte_prefix_rejected(self):
        f = _make_uploaded("fake.png", b"\x89PNG" + b"not-real-png-data")
        is_valid, err = validate_image_magic_number(f)
        self.assertFalse(is_valid)
        self.assertIn("does not match", err)

    def test_jpg_without_following_ff_marker_rejected(self):
        f = _make_uploaded("fake.jpg", b"\xFF\xD8\x00" + b"not-real-jpeg-data")
        is_valid, err = validate_image_magic_number(f)
        self.assertFalse(is_valid)
        self.assertIn("does not match", err)

    def test_read_error_returns_unable_to_read_file_header(self):
        class _BrokenUploadedFile:
            def __init__(self):
                self.seek_calls = []

            def seek(self, *_args, **_kwargs):
                self.seek_calls.append((_args, _kwargs))
                return None

            def read(self, *_args, **_kwargs):
                raise OSError("cannot read")

        f = _BrokenUploadedFile()

        with patch("file_processing.utils.image_validators.logger.exception") as mock_exception:
            is_valid, err = validate_image_magic_number(f)

        self.assertFalse(is_valid)
        self.assertEqual(err, "Unable to read file header.")
        mock_exception.assert_called_once_with(
            "Error reading file header for magic number check."
        )
        self.assertGreaterEqual(len(f.seek_calls), 2)

    def test_finally_seek_reset_failure_is_ignored(self):
        class _SeekFailsOnResetFile:
            def __init__(self):
                self.seek_call_count = 0

            def seek(self, *_args, **_kwargs):
                self.seek_call_count += 1
                if self.seek_call_count >= 2:
                    raise OSError("seek reset failed")
                return None

            def read(self, *_args, **_kwargs):
                return b"\x89PNG\r\n\x1a\n"

        f = _SeekFailsOnResetFile()

        is_valid, err = validate_image_magic_number(f)

        self.assertTrue(is_valid)
        self.assertIsNone(err)
        self.assertEqual(f.seek_call_count, 2)


class TestValidateImageIntegrity(SimpleTestCase):
    """validate_image_integrity() — uses Pillow to detect corruption."""

    def test_uses_context_manager_and_resets_pointer(self):
        class _TrackableFile:
            def __init__(self):
                self.seek_calls = []

            def seek(self, *_args, **_kwargs):
                self.seek_calls.append((_args, _kwargs))
                return None

        class _ImageCtx:
            def __init__(self):
                self.verify_called = False
                self.exited = False
                self.size = (100, 100)  # width, height in pixels

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                self.exited = True
                return False

            def verify(self):
                self.verify_called = True

        f = _TrackableFile()
        img_ctx = _ImageCtx()

        with patch("file_processing.utils.image_validators.Image.open", return_value=img_ctx):
            is_valid, err = validate_image_integrity(f)

        self.assertTrue(is_valid)
        self.assertIsNone(err)
        self.assertTrue(img_ctx.verify_called)
        self.assertTrue(img_ctx.exited)
        self.assertGreaterEqual(len(f.seek_calls), 2)

    def test_integrity_error_not_masked_when_finally_seek_fails(self):
        class _SeekFailsOnResetFile:
            def __init__(self):
                self.seek_call_count = 0

            def seek(self, *_args, **_kwargs):
                self.seek_call_count += 1
                if self.seek_call_count >= 2:
                    raise OSError("seek reset failed")
                return None

        f = _SeekFailsOnResetFile()

        with patch("file_processing.utils.image_validators.Image.open", side_effect=OSError("bad image")):
            with patch("file_processing.utils.image_validators.logger.warning") as mock_warning:
                with patch("file_processing.utils.image_validators.logger.exception") as mock_exception:
                    is_valid, err = validate_image_integrity(f)

        self.assertFalse(is_valid)
        self.assertEqual(err, "Image file is corrupted or unreadable.")
        self.assertEqual(f.seek_call_count, 2)
        mock_warning.assert_called_once_with(
            "Invalid image upload failed integrity validation."
        )
        mock_exception.assert_called_once_with(
            "Error resetting file pointer after image integrity check."
        )

    def test_integrity_valid_result_when_finally_seek_fails_and_logs(self):
        class _SeekFailsOnResetFile:
            def __init__(self):
                self.seek_call_count = 0

            def seek(self, *_args, **_kwargs):
                self.seek_call_count += 1
                if self.seek_call_count >= 2:
                    raise OSError("seek reset failed")
                return None

        class _ImageCtx:
            def __init__(self):
                self.size = (100, 100)  # width, height in pixels

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def verify(self):
                return None

        f = _SeekFailsOnResetFile()

        with patch("file_processing.utils.image_validators.Image.open", return_value=_ImageCtx()):
            with patch("file_processing.utils.image_validators.logger.exception") as mock_exception:
                is_valid, err = validate_image_integrity(f)

        self.assertTrue(is_valid)
        self.assertIsNone(err)
        self.assertEqual(f.seek_call_count, 2)
        mock_exception.assert_called_once_with(
            "Error resetting file pointer after image integrity check."
        )

    def test_integrity_error_logs_warning(self):
        class _BrokenImageFile:
            def seek(self, *_args, **_kwargs):
                return None

        f = _BrokenImageFile()

        with patch("file_processing.utils.image_validators.Image.open", side_effect=OSError("image open failed")):
            with patch("file_processing.utils.image_validators.logger.warning") as mock_warning:
                is_valid, err = validate_image_integrity(f)

        self.assertFalse(is_valid)
        self.assertEqual(err, "Image file is corrupted or unreadable.")
        mock_warning.assert_called_once_with(
            "Invalid image upload failed integrity validation."
        )

    def test_integrity_error_logs_exception(self):
        class _BrokenImageFile:
            def seek(self, *_args, **_kwargs):
                return None

        f = _BrokenImageFile()

        with patch("file_processing.utils.image_validators.Image.open", side_effect=RuntimeError("unexpected")):
            with patch("file_processing.utils.image_validators.logger.exception") as mock_exception:
                is_valid, err = validate_image_integrity(f)

        self.assertFalse(is_valid)
        self.assertEqual(err, "Image file is corrupted or unreadable.")
        mock_exception.assert_called_once_with(
            "Error validating image integrity."
        )

    def test_valid_png(self):
        content = _make_image_bytes("PNG")
        f = _make_uploaded("good.png", content)
        is_valid, err = validate_image_integrity(f)
        self.assertTrue(is_valid)
        self.assertIsNone(err)

    def test_valid_jpeg(self):
        content = _make_image_bytes("JPEG")
        f = _make_uploaded("good.jpg", content)
        is_valid, err = validate_image_integrity(f)
        self.assertTrue(is_valid)
        self.assertIsNone(err)

    def test_corrupted_image_rejected(self):
        """Truncated PNG header + garbage should be detected as corrupt."""
        corrupted = b"\x89PNG\r\n\x1a\n" + b"\x00" * 50
        f = _make_uploaded("corrupt.png", corrupted)
        is_valid, err = validate_image_integrity(f)
        self.assertFalse(is_valid)
        self.assertIn("corrupted", err.lower())

    def test_grayscale_image_passes(self):
        """Edge: grayscale images must be accepted."""
        content = _make_image_bytes("PNG", mode="L")
        f = _make_uploaded("gray.png", content)
        is_valid, err = validate_image_integrity(f)
        self.assertTrue(is_valid)
        self.assertIsNone(err)

    def test_small_resolution_image_passes(self):
        """Edge: very small images (1×1) must be accepted."""
        content = _make_image_bytes("PNG", size=(1, 1))
        f = _make_uploaded("tiny.png", content)
        is_valid, err = validate_image_integrity(f)
        self.assertTrue(is_valid)
        self.assertIsNone(err)

    def test_image_exceeding_max_dimension_rejected(self):
        """Image with dimensions exceeding MAX_IMAGE_DIMENSION should be rejected."""
        from file_processing.utils.image_validators import MAX_IMAGE_DIMENSION

        class _HugeDimensionImage:
            def __init__(self):
                self.size = (MAX_IMAGE_DIMENSION + 1, 100)

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def verify(self):
                pass

        class _FakeFile:
            def seek(self, *_args):
                pass

        f = _FakeFile()

        with patch("file_processing.utils.image_validators.Image.open", return_value=_HugeDimensionImage()):
            is_valid, err = validate_image_integrity(f)

        self.assertFalse(is_valid)
        self.assertIn("dimensions exceed", err.lower())

    def test_image_exceeding_max_pixel_count_rejected(self):
        """Image with total pixels over MAX_IMAGE_PIXELS should be rejected."""

        class _HugePixelImage:
            def __init__(self):
                self.size = (9000, 9000)

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def verify(self):
                raise AssertionError("verify() should not be called for over-pixel image")

        class _FakeFile:
            def seek(self, *_args):
                pass

        f = _FakeFile()

        with patch("file_processing.utils.image_validators.Image.open", return_value=_HugePixelImage()):
            is_valid, err = validate_image_integrity(f)

        self.assertFalse(is_valid)
        self.assertEqual(err, "Image pixel count exceeds maximum allowed limit.")

    def test_decompression_bomb_warning_treated_as_error(self):
        """PIL's DecompressionBombWarning should cause validation to fail."""

        class _BombWarningImage:
            def __init__(self):
                self.size = (100, 100)

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def verify(self):
                # Simulate PIL raising DecompressionBombWarning
                warnings.warn(
                    "Decompression bomb detected",
                    Image.DecompressionBombWarning,
                )

        class _FakeFile:
            def seek(self, *_args):
                pass

        f = _FakeFile()

        with patch("file_processing.utils.image_validators.Image.open", return_value=_BombWarningImage()):
            is_valid, err = validate_image_integrity(f)

        self.assertFalse(is_valid)
        self.assertEqual(err, "Image file is corrupted or unreadable.")


class TestValidateImageService(SimpleTestCase):
    """validate_image() — orchestrates all image validators."""

    @patch(
        "file_processing.services.image_validation_service.validate_image_extension",
        return_value=(False, "Unsupported image format."),
    )
    @patch("file_processing.services.image_validation_service.validate_image_size")
    @patch("file_processing.services.image_validation_service.validate_image_mime_type")
    @patch("file_processing.services.image_validation_service.validate_image_magic_number")
    @patch("file_processing.services.image_validation_service.validate_image_integrity")
    def test_pipeline_short_circuits_on_extension_failure(
        self,
        mock_integrity,
        mock_magic,
        mock_mime,
        mock_size,
        _mock_extension,
    ):
        f = _make_uploaded("bad.gif", b"x", "image/gif")

        is_valid, err = validate_image(f)

        self.assertFalse(is_valid)
        self.assertEqual(err, "Unsupported image format.")
        mock_size.assert_not_called()
        mock_mime.assert_not_called()
        mock_magic.assert_not_called()
        mock_integrity.assert_not_called()

    def test_valid_png(self):
        content = _make_image_bytes("PNG")
        f = _make_uploaded("photo.png", content, "image/png")
        with patch(
            "file_processing.services.image_validation_service.validate_image_mime_type",
            return_value=(True, None),
        ):
            is_valid, err = validate_image(f)
        self.assertTrue(is_valid)
        self.assertIsNone(err)

    def test_valid_jpg(self):
        content = _make_image_bytes("JPEG")
        f = _make_uploaded("photo.jpg", content, "image/jpeg")
        with patch(
            "file_processing.services.image_validation_service.validate_image_mime_type",
            return_value=(True, None),
        ):
            is_valid, err = validate_image(f)
        self.assertTrue(is_valid)
        self.assertIsNone(err)

    def test_valid_jpeg(self):
        content = _make_image_bytes("JPEG")
        f = _make_uploaded("photo.jpeg", content, "image/jpeg")
        with patch(
            "file_processing.services.image_validation_service.validate_image_mime_type",
            return_value=(True, None),
        ):
            is_valid, err = validate_image(f)
        self.assertTrue(is_valid)
        self.assertIsNone(err)

    def test_wrong_extension_rejected(self):
        content = _make_image_bytes("PNG")
        f = _make_uploaded("photo.bmp", content, "image/png")
        is_valid, err = validate_image(f)
        self.assertFalse(is_valid)

    def test_mime_mismatch_rejected(self):
        content = _make_image_bytes("PNG")
        f = _make_uploaded("photo.png", content, "image/png")
        with patch(
            "file_processing.services.image_validation_service.validate_image_mime_type",
            return_value=(False, "File content does not match its extension."),
        ):
            is_valid, err = validate_image(f)
        self.assertFalse(is_valid)
        self.assertIn("does not match", err)

    def test_fake_image_rejected(self):
        """A text file renamed to .png should fail."""
        f = _make_uploaded("fake.png", b"Hello world, not an image", "image/png")
        with patch(
            "file_processing.services.image_validation_service.validate_image_mime_type",
            return_value=(True, None),
        ):
            is_valid, err = validate_image(f)
        self.assertFalse(is_valid)

    def test_corrupted_image_rejected(self):
        corrupted = b"\x89PNG\r\n\x1a\n" + b"\x00" * 50
        f = _make_uploaded("corrupt.png", corrupted, "image/png")
        with patch(
            "file_processing.services.image_validation_service.validate_image_mime_type",
            return_value=(True, None),
        ):
            is_valid, err = validate_image(f)
        self.assertFalse(is_valid)

    def test_oversized_image_rejected(self):
        big = b"\x89PNG\r\n\x1a\n" + b"\x00" * (10 * 1024 * 1024 + 1)
        f = _make_uploaded("huge.png", big, "image/png")
        is_valid, err = validate_image(f)
        self.assertFalse(is_valid)
        self.assertIn("10MB", err)

    def test_grayscale_edge_case_passes(self):
        content = _make_image_bytes("PNG", mode="L")
        f = _make_uploaded("gray.png", content, "image/png")
        with patch(
            "file_processing.services.image_validation_service.validate_image_mime_type",
            return_value=(True, None),
        ):
            is_valid, err = validate_image(f)
        self.assertTrue(is_valid)
        self.assertIsNone(err)

    def test_small_image_edge_case_passes(self):
        content = _make_image_bytes("PNG", size=(1, 1))
        f = _make_uploaded("tiny.png", content, "image/png")
        with patch(
            "file_processing.services.image_validation_service.validate_image_mime_type",
            return_value=(True, None),
        ):
            is_valid, err = validate_image(f)
        self.assertTrue(is_valid)
        self.assertIsNone(err)


class TestValidateImageMimeType(SimpleTestCase):
    """validate_image_mime_type()"""

    @patch("file_processing.services.image_validation_service.magic.from_buffer")
    def test_expected_mime_passes_and_resets_pointer(self, mock_from_buffer):
        mock_from_buffer.return_value = "image/png"
        f = _make_uploaded("photo.png", b"x" * 4096, "application/octet-stream")

        is_valid, err = validate_image_mime_type(f, ".png")

        self.assertTrue(is_valid)
        self.assertIsNone(err)
        self.assertEqual(f.tell(), 0)

    @patch("file_processing.services.image_validation_service.magic.from_buffer")
    def test_mime_mismatch_rejected(self, mock_from_buffer):
        mock_from_buffer.return_value = "image/jpeg"
        f = _make_uploaded("photo.png", b"x" * 64, "application/octet-stream")

        is_valid, err = validate_image_mime_type(f, ".png")

        self.assertFalse(is_valid)
        self.assertEqual(err, "File content does not match its extension.")

    @patch(
        "file_processing.services.image_validation_service.magic.from_buffer",
        side_effect=Exception("magic failure"),
    )
    def test_magic_exception_returns_unable_to_determine_file_type(self, _mock_from_buffer):
        f = _make_uploaded("photo.png", b"x" * 64, "application/octet-stream")

        with patch("file_processing.services.image_validation_service.logger.exception") as mock_exception:
            is_valid, err = validate_image_mime_type(f, ".png")

        self.assertFalse(is_valid)
        self.assertEqual(err, "Unable to determine file type.")
        mock_exception.assert_called_once_with("Error validating image MIME type.")
        self.assertEqual(f.tell(), 0)

    @patch(
        "file_processing.services.image_validation_service.magic.from_buffer",
        side_effect=Exception("magic failure"),
    )
    def test_seek_reset_failure_in_finally_is_logged(self, _mock_from_buffer):
        class _SeekResetFailsFile:
            def __init__(self):
                self.seek_call_count = 0

            def seek(self, *_args, **_kwargs):
                self.seek_call_count += 1
                if self.seek_call_count >= 2:
                    raise OSError("seek reset failed")
                return None

            def read(self, *_args, **_kwargs):
                return b"x" * 128

        f = _SeekResetFailsFile()

        with patch("file_processing.services.image_validation_service.logger.exception") as mock_exception:
            is_valid, err = validate_image_mime_type(f, ".png")

        self.assertFalse(is_valid)
        self.assertEqual(err, "Unable to determine file type.")
        self.assertEqual(mock_exception.call_count, 2)
        mock_exception.assert_any_call("Error validating image MIME type.")
        mock_exception.assert_any_call("Error resetting file pointer after MIME validation.")


class TestValidateFileImageIntegration(SimpleTestCase):
    """validate_file() must route image extensions to validate_image()."""

    @patch(
        "file_processing.services.upload_service.validate_image",
        return_value=(True, None),
    )
    def test_png_routed_to_image_validator(self, mock_vi):
        content = _make_image_bytes("PNG")
        f = _make_uploaded("test.png", content, "image/png")
        is_valid, err = validate_file(f)
        self.assertTrue(is_valid)
        mock_vi.assert_called_once()

    @patch(
        "file_processing.services.upload_service.validate_image",
        return_value=(True, None),
    )
    def test_jpg_routed_to_image_validator(self, mock_vi):
        content = _make_image_bytes("JPEG")
        f = _make_uploaded("test.jpg", content, "image/jpeg")
        is_valid, err = validate_file(f)
        self.assertTrue(is_valid)
        mock_vi.assert_called_once()

    @patch(
        "file_processing.services.upload_service.validate_image",
        return_value=(False, "Bad image"),
    )
    def test_image_validation_failure_propagated(self, mock_vi):
        f = _make_uploaded("bad.png", b"x", "image/png")
        is_valid, err = validate_file(f)
        self.assertFalse(is_valid)
        self.assertEqual(err, "Bad image")

    def test_pdf_still_works(self):
        """Existing PDF flow must not break."""
        f = _make_uploaded("doc.pdf", b"%PDF-1.4", "application/pdf")
        with patch(
            "file_processing.services.upload_service.validate_mime_type",
            return_value=(True, None),
        ):
            is_valid, err = validate_file(f)
        self.assertTrue(is_valid)
        self.assertIsNone(err)

    def test_xlsx_still_works(self):
        """Existing Excel flow must not break."""
        from openpyxl import Workbook

        buf = io.BytesIO()
        Workbook().save(buf)
        buf.seek(0)
        f = _make_uploaded(
            "sheet.xlsx",
            buf.read(),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        with patch(
            "file_processing.services.upload_service.validate_mime_type",
            return_value=(True, None),
        ):
            with patch(
                "file_processing.services.upload_service.validate_excel_sheet_count",
                return_value=(True, None),
            ):
                is_valid, err = validate_file(f)
        self.assertTrue(is_valid)
        self.assertIsNone(err)
