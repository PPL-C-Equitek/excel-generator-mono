import csv
import json
import shutil
import uuid
from pathlib import Path

from django.core.exceptions import ValidationError
from django.test import override_settings
from django.test import TestCase
from django.conf import settings

from benchmark.services import DatasetLoader


@override_settings(MEDIA_ROOT=settings.BASE_DIR / ".tmp-tests")
class DatasetLoaderTest(TestCase):
    def setUp(self):
        self.loader = DatasetLoader()
        self.schema = {
            "columns": [
                {"name": "question", "type": "string", "required": True},
                {"name": "answer", "type": "string", "required": True},
                {"name": "score", "type": "integer", "required": True},
                {"name": "evaluated_at", "type": "string", "format": "date", "required": False},
            ]
        }

    def test_load_csv_reads_full_dataset_and_validates_values_against_schema(self):
        dataset_path = self._write_csv(
            "dataset.csv",
            rows=[
                {
                    "question": "What is 2 + 2?",
                    "answer": "4",
                    "score": "100",
                    "evaluated_at": "2026-04-21",
                },
                {
                    "question": "Capital of Indonesia?",
                    "answer": "Jakarta",
                    "score": "95",
                    "evaluated_at": "2026-04-22",
                },
            ],
        )

        rows = self.loader.load(dataset_path, self.schema)

        self.assertEqual(
            rows,
            [
                {
                    "question": "What is 2 + 2?",
                    "answer": "4",
                    "score": 100,
                    "evaluated_at": "2026-04-21",
                },
                {
                    "question": "Capital of Indonesia?",
                    "answer": "Jakarta",
                    "score": 95,
                    "evaluated_at": "2026-04-22",
                },
            ],
        )

    def test_load_json_reads_full_dataset_and_validates_values_against_schema(self):
        dataset_path = self._write_json(
            "dataset.json",
            payload=[
                {
                    "question": "Largest planet?",
                    "answer": "Jupiter",
                    "score": 88,
                    "evaluated_at": "2026-04-23",
                },
                {
                    "question": "Fastest land animal?",
                    "answer": "Cheetah",
                    "score": 91,
                    "evaluated_at": "2026-04-24",
                },
            ],
        )

        rows = self.loader.load(dataset_path, self.schema)

        self.assertEqual(
            rows,
            [
                {
                    "question": "Largest planet?",
                    "answer": "Jupiter",
                    "score": 88,
                    "evaluated_at": "2026-04-23",
                },
                {
                    "question": "Fastest land animal?",
                    "answer": "Cheetah",
                    "score": 91,
                    "evaluated_at": "2026-04-24",
                },
            ],
        )

    def test_load_rejects_unsupported_extension_with_invalid_format_message(self):
        dataset_path = self._write_text("dataset.txt", "plain text is not supported")

        with self.assertRaisesMessage(ValidationError, "Format Dataset Tidak Valid"):
            self.loader.load(dataset_path, self.schema)

    def test_load_rejects_dataset_when_required_column_is_missing(self):
        dataset_path = self._write_csv(
            "dataset.csv",
            fieldnames=["question", "answer", "evaluated_at"],
            rows=[
                {
                    "question": "What is 2 + 2?",
                    "answer": "4",
                    "evaluated_at": "2026-04-21",
                }
            ],
        )

        with self.assertRaisesMessage(ValidationError, "Format Dataset Tidak Valid"):
            self.loader.load(dataset_path, self.schema)

    def test_load_rejects_json_object_top_level_instead_of_list(self):
        dataset_path = self._write_json(
            "dataset.json",
            payload={
                "question": "Largest planet?",
                "answer": "Jupiter",
                "score": 88,
            },
        )

        with self.assertRaisesMessage(ValidationError, "Format Dataset Tidak Valid"):
            self.loader.load(dataset_path, self.schema)

    def test_load_rejects_corrupt_json_with_invalid_format_message(self):
        dataset_path = self._write_text(
            "dataset.json",
            '{"question": "Largest planet?", "answer": "Jupiter",',
        )

        with self.assertRaisesMessage(ValidationError, "Format Dataset Tidak Valid"):
            self.loader.load(dataset_path, self.schema)

    def test_load_rejects_corrupt_csv_with_invalid_encoding(self):
        dataset_path = self._write_bytes(
            "dataset.csv",
            b"\xff\xfe\x00\x00question,answer,score,evaluated_at\n",
        )

        with self.assertRaisesMessage(ValidationError, "Format Dataset Tidak Valid"):
            self.loader.load(dataset_path, self.schema)

    def test_load_rejects_malformed_schema_root(self):
        dataset_path = self._write_json(
            "dataset.json",
            payload=[],
        )

        with self.assertRaisesMessage(ValidationError, "Format Dataset Tidak Valid"):
            self.loader.load(dataset_path, None)

    def test_load_rejects_malformed_schema_columns_shape(self):
        dataset_path = self._write_json(
            "dataset.json",
            payload=[],
        )
        malformed_schema = {"columns": [{"required": True}]}

        with self.assertRaisesMessage(ValidationError, "Format Dataset Tidak Valid"):
            self.loader.load(dataset_path, malformed_schema)

    def test_load_skips_empty_and_corrupted_csv_rows_without_crashing(self):
        dataset_path = self._write_csv(
            "dataset.csv",
            rows=[
                {
                    "question": "What is 2 + 2?",
                    "answer": "4",
                    "score": "100",
                    "evaluated_at": "2026-04-21",
                },
                {
                    "question": "",
                    "answer": "",
                    "score": "",
                    "evaluated_at": "",
                },
                {
                    "question": "Broken integer row",
                    "answer": "NaN",
                    "score": "not-a-number",
                    "evaluated_at": "2026-04-21",
                },
                {
                    "question": "Valid row after broken row",
                    "answer": "Still loaded",
                    "score": "77",
                    "evaluated_at": "2026-04-25",
                },
            ],
        )

        rows = self.loader.load(dataset_path, self.schema)

        self.assertEqual(
            rows,
            [
                {
                    "question": "What is 2 + 2?",
                    "answer": "4",
                    "score": 100,
                    "evaluated_at": "2026-04-21",
                },
                {
                    "question": "Valid row after broken row",
                    "answer": "Still loaded",
                    "score": 77,
                    "evaluated_at": "2026-04-25",
                },
            ],
        )

    def test_load_skips_empty_and_corrupted_json_rows_without_crashing(self):
        dataset_path = self._write_json(
            "dataset.json",
            payload=[
                {
                    "question": "Largest ocean?",
                    "answer": "Pacific",
                    "score": 90,
                    "evaluated_at": "2026-04-26",
                },
                {},
                {
                    "question": "Broken date row",
                    "answer": "Invalid",
                    "score": 40,
                    "evaluated_at": "26-04-2026",
                },
                {
                    "question": "Smallest prime number?",
                    "answer": "2",
                    "score": 99,
                    "evaluated_at": "2026-04-27",
                },
            ],
        )

        rows = self.loader.load(dataset_path, self.schema)

        self.assertEqual(
            rows,
            [
                {
                    "question": "Largest ocean?",
                    "answer": "Pacific",
                    "score": 90,
                    "evaluated_at": "2026-04-26",
                },
                {
                    "question": "Smallest prime number?",
                    "answer": "2",
                    "score": 99,
                    "evaluated_at": "2026-04-27",
                },
            ],
        )

    def _write_csv(self, filename, rows, fieldnames=None):
        fieldnames = fieldnames or ["question", "answer", "score", "evaluated_at"]
        path = self._make_temp_path(filename)
        with path.open("w", encoding="utf-8", newline="") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        return path

    def _write_json(self, filename, payload):
        path = self._make_temp_path(filename)
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def _write_text(self, filename, content):
        path = self._make_temp_path(filename)
        path.write_text(content, encoding="utf-8")
        return path

    def _write_bytes(self, filename, content):
        path = self._make_temp_path(filename)
        path.write_bytes(content)
        return path

    def _make_temp_path(self, filename):
        root_dir = Path(settings.BASE_DIR) / ".tmp-tests" / "benchmark"
        root_dir.mkdir(parents=True, exist_ok=True)
        temp_dir = root_dir / f"tmp_{uuid.uuid4().hex}"
        temp_dir.mkdir(parents=True, exist_ok=True)
        self.addCleanup(self._cleanup_dir, temp_dir)
        return temp_dir / filename

    def _cleanup_dir(self, path):
        shutil.rmtree(path, ignore_errors=True)
