from django.test import TestCase

from authentication.models import User
from artifact_history.models import ArtifactHistory
from artifact_history.services import create_artifact_history, list_artifact_history_for_user


class ArtifactHistoryServiceTest(TestCase):
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

    def test_create_artifact_history_persists_owned_record(self):
        record = create_artifact_history(
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

        self.assertEqual(record.owner, self.owner)
        self.assertEqual(record.file_id, "csv_abc123")
        self.assertTrue(ArtifactHistory.objects.filter(id=record.id).exists())

    def test_list_artifact_history_for_user_returns_only_owned_records(self):
        owned_record = ArtifactHistory.objects.create(
            owner=self.owner,
            file_id="xlsx_owner123",
            original_name="owner.pdf",
            custom_name=None,
            file_name="export_owner123.xlsx",
            file_type="xlsx",
            status_processing="completed",
            size_bytes=256,
            created_at="2026-04-08T10:00:00Z",
        )
        ArtifactHistory.objects.create(
            owner=self.other_owner,
            file_id="xlsx_other123",
            original_name="other.pdf",
            custom_name=None,
            file_name="export_other123.xlsx",
            file_type="xlsx",
            status_processing="completed",
            size_bytes=512,
            created_at="2026-04-08T10:05:00Z",
        )

        results = list_artifact_history_for_user(self.owner, limit=10, offset=0)

        self.assertEqual(list(results), [owned_record])

    def test_list_artifact_history_for_user_returns_empty_result_for_user_with_no_history(self):
        results = list_artifact_history_for_user(self.owner, limit=10, offset=0)

        self.assertEqual(list(results), [])

    def test_list_artifact_history_for_user_rejects_invalid_limit(self):
        with self.assertRaises(ValueError):
            list_artifact_history_for_user(self.owner, limit=0, offset=0)
