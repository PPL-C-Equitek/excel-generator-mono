import io
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
            def seek(self, *_args, **_kwargs):
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


class TestValidateImageIntegrity(SimpleTestCase):
    """validate_image_integrity() — uses Pillow to detect corruption."""

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