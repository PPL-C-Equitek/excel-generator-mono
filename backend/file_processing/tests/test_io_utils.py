import io
import os
import tempfile

from django.test import TestCase

from file_processing.utils.io_utils import iter_lines, seek_to_start, validate_path

def _make_tmp(content: str, encoding: str = "utf-8") -> str:
    fd, path = tempfile.mkstemp(suffix=".txt")
    with os.fdopen(fd, "w", encoding=encoding) as fh:
        fh.write(content)
    return path

class ValidatePathTests(TestCase):
    def test_valid_path_returns_absolute_path(self):
        path = _make_tmp("hello")
        try:
            result = validate_path(path)
            self.assertEqual(result, os.path.abspath(path))
        finally:
            os.remove(path)

    def test_traversal_single_dotdot_raises_value_error(self):
        with self.assertRaises(ValueError) as ctx:
            validate_path("../../../etc/passwd")
        self.assertIn("Path Traversal", str(ctx.exception))

    def test_traversal_message_is_user_friendly(self):
        with self.assertRaises(ValueError) as ctx:
            validate_path("../../secret")
        self.assertNotIn("Traceback", str(ctx.exception))
        self.assertNotIn("raise", str(ctx.exception))

    def test_nonexistent_path_raises_file_not_found(self):
        abs_path = os.path.abspath("nonexistent_io_utils_test_xyz.txt")
        with self.assertRaises(FileNotFoundError):
            validate_path(abs_path)

    def test_error_message_contains_path(self):
        abs_path = os.path.abspath("missing_file_io_utils.txt")
        with self.assertRaises(FileNotFoundError) as ctx:
            validate_path(abs_path)
        self.assertIn(abs_path, str(ctx.exception))

class SeekToStartTests(TestCase):
    def test_seekable_bytes_io_is_rewound_to_zero(self):
        buf = io.BytesIO(b"content")
        buf.seek(5)
        seek_to_start(buf)
        self.assertEqual(buf.tell(), 0)

    def test_seekable_string_io_is_rewound_to_zero(self):
        buf = io.StringIO("hello world")
        buf.seek(6)
        seek_to_start(buf)
        self.assertEqual(buf.tell(), 0)

    def test_no_seek_method_raises_nothing(self):
        class NoSeek:
            pass
        seek_to_start(NoSeek())

    def test_os_error_on_seek_is_suppressed(self):
        class OSErrorSeek:
            def seek(self, _):
                raise OSError("cannot seek")
        seek_to_start(OSErrorSeek())

    def test_attribute_error_on_seek_is_suppressed(self):
        class AttrErrorSeek:
            def seek(self, _):
                raise AttributeError
        seek_to_start(AttrErrorSeek())

class IterLinesTests(TestCase):
    def test_path_string_yields_correct_lines(self):
        path = _make_tmp("Baris 1\nBaris 2\nBaris 3")
        try:
            result = list(iter_lines(path))
            self.assertEqual(result, ["Baris 1", "Baris 2", "Baris 3"])
        finally:
            os.remove(path)

    def test_bytes_io_yields_decoded_strings(self):
        buf = io.BytesIO("Satu\nDua".encode("utf-8"))
        result = list(iter_lines(buf))
        self.assertIsInstance(result[0], str)
        self.assertEqual(result, ["Satu", "Dua"])

    def test_string_io_yields_strings(self):
        buf = io.StringIO("Hello\nWorld")
        result = list(iter_lines(buf))
        self.assertEqual(result, ["Hello", "World"])

    def test_crlf_endings_are_stripped(self):
        buf = io.BytesIO(b"Line1\r\nLine2\r\n")
        result = list(iter_lines(buf))
        for line in result:
            self.assertNotIn("\r", line)
            self.assertNotIn("\n", line)

    def test_lf_only_endings_are_stripped(self):
        buf = io.BytesIO(b"A\nB\nC\n")
        result = list(iter_lines(buf))
        self.assertEqual(result, ["A", "B", "C"])

    def test_path_traversal_raises_value_error(self):
        with self.assertRaises(ValueError):
            list(iter_lines("../../../etc/passwd"))

    def test_nonexistent_path_raises_file_not_found(self):
        abs_path = os.path.abspath("nonexistent_iter_lines_xyz.txt")
        with self.assertRaises(FileNotFoundError):
            list(iter_lines(abs_path))

    def test_seek_os_error_is_handled_gracefully(self):
        class OSErrorSeek:
            def seek(self, _):
                raise OSError
            def __iter__(self):
                yield b"content\n"
        result = list(iter_lines(OSErrorSeek()))
        self.assertEqual(result, ["content"])

    def test_blank_lines_yielded_as_empty_strings(self):
        buf = io.StringIO("A\n\nB")
        result = list(iter_lines(buf))
        self.assertEqual(result, ["A", "", "B"])

    def test_unicode_content_preserved(self):
        path = _make_tmp("áéíóú\n한국어\n日本語")
        try:
            result = list(iter_lines(path))
            self.assertEqual(result[0], "áéíóú")
            self.assertEqual(result[1], "한국어")
            self.assertEqual(result[2], "日本語")
        finally:
            os.remove(path)

    def test_all_output_lines_are_strings(self):
        buf = io.BytesIO(b"one\ntwo\nthree")
        result = list(iter_lines(buf))
        self.assertTrue(all(isinstance(line, str) for line in result))

    def test_custom_encoding_is_respected(self):
        content = "café\nnaïve".encode("latin-1")
        buf = io.BytesIO(content)
        result = list(iter_lines(buf, encoding="latin-1"))
        self.assertEqual(result[0], "café")
        self.assertEqual(result[1], "naïve")

    def test_empty_stream_yields_nothing(self):
        buf = io.BytesIO(b"")
        result = list(iter_lines(buf))
        self.assertEqual(result, [])
