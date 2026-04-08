from django.core.exceptions import ValidationError
from django.test import TestCase
import uuid

from authentication.models import User
from artifact_history.models import ArtifactHistory


class ArtifactHistoryModelTest(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="owner@example.com",
            name="Owner",
            password="Test12345",
            status="verified",
        )
        self.other_owner = User.objects.create_user(
            email="other@example.com",
            name="Other",
            password="Test12345",
            status="verified",
        )

    def test_primary_key_defaults_to_uuid(self):
        artifact = ArtifactHistory.objects.create(
            owner=self.owner,
            file_id="csv_abc123",
            original_name="report.pdf",
            custom_name=None,
            file_name="export_abc123.csv",
            file_type="csv",
            status_processing="completed",
            size_bytes=128,
            created_at="2026-04-08T10:00:00Z",
        )

        self.assertIsInstance(artifact.id, uuid.UUID)

    def test_duplicate_file_id_is_rejected(self):
        ArtifactHistory.objects.create(
            owner=self.owner,
            file_id="xlsx_abc123",
            original_name="report.pdf",
            custom_name=None,
            file_name="export_abc123.xlsx",
            file_type="xlsx",
            status_processing="completed",
            size_bytes=256,
            created_at="2026-04-08T10:00:00Z",
        )

        duplicate = ArtifactHistory(
            owner=self.other_owner,
            file_id="xlsx_abc123",
            original_name="other.pdf",
            custom_name=None,
            file_name="export_abc123.xlsx",
            file_type="xlsx",
            status_processing="completed",
            size_bytes=512,
            created_at="2026-04-08T10:05:00Z",
        )

        with self.assertRaises(ValidationError):
            duplicate.save()

    def test_invalid_file_type_is_rejected(self):
        artifact = ArtifactHistory(
            owner=self.owner,
            file_id="bad_abc123",
            original_name="report.pdf",
            custom_name=None,
            file_name="export_abc123.bin",
            file_type="bin",
            status_processing="completed",
            size_bytes=64,
            created_at="2026-04-08T10:00:00Z",
        )

        with self.assertRaises(ValidationError):
            artifact.save()

    def test_ordering_returns_newest_records_first(self):
        older = ArtifactHistory.objects.create(
            owner=self.owner,
            file_id="csv_old123",
            original_name="older.pdf",
            custom_name=None,
            file_name="export_old123.csv",
            file_type="csv",
            status_processing="completed",
            size_bytes=64,
            created_at="2026-04-08T10:00:00Z",
        )
        newer = ArtifactHistory.objects.create(
            owner=self.owner,
            file_id="csv_new123",
            original_name="newer.pdf",
            custom_name="Quarterly Export",
            file_name="export_new123.csv",
            file_type="csv",
            status_processing="completed",
            size_bytes=96,
            created_at="2026-04-08T10:10:00Z",
        )

        records = list(ArtifactHistory.objects.all())

        self.assertEqual(records, [newer, older])

