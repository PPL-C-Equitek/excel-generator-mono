import io

from django.test import SimpleTestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from file_processing.utils.image_validators import (
    validate_image_extension,
    validate_image_size,
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
