from django.core.exceptions import ValidationError
from django.test import TestCase
import uuid

from authentication.models import User
from artifact_history.models import ArtifactHistory


def make_output_json(table_name="Sheet1", value="hello"):
    return {
        "document_info": {
            "source_type": "PDF",
            "filename": "report.pdf",
        },
        "summary": {
            "total_rows": 1,
        },
        "content_data": [
            {
                "table_name": table_name,
                "headers": ["text"],
                "rows": [
                    {"text": value},
                ],
            }
        ],
    }


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
            original_name="report.pdf",
            custom_name=None,
            output_json=make_output_json(),
            status_processing="completed",
            created_at="2026-04-08T10:00:00Z",
        )

        self.assertIsInstance(artifact.id, uuid.UUID)

    def test_custom_name_is_optional(self):
        artifact = ArtifactHistory.objects.create(
            owner=self.owner,
            original_name="report.pdf",
            custom_name=None,
            output_json=make_output_json(),
            status_processing="completed",
            created_at="2026-04-08T10:00:00Z",
        )

        self.assertIsNone(artifact.custom_name)

    def test_invalid_output_json_is_rejected(self):
        artifact = ArtifactHistory(
            owner=self.owner,
            original_name="report.pdf",
            custom_name=None,
            output_json=[],
            status_processing="completed",
            created_at="2026-04-08T10:00:00Z",
        )

        with self.assertRaises(ValidationError):
            artifact.save()

    def test_ordering_returns_newest_records_first(self):
        older = ArtifactHistory.objects.create(
            owner=self.owner,
            original_name="older.pdf",
            custom_name=None,
            output_json=make_output_json("OlderSheet", "old"),
            status_processing="completed",
            created_at="2026-04-08T10:00:00Z",
        )
        newer = ArtifactHistory.objects.create(
            owner=self.owner,
            original_name="newer.pdf",
            custom_name="Quarterly Export",
            output_json=make_output_json("NewerSheet", "new"),
            status_processing="completed",
            created_at="2026-04-08T10:10:00Z",
        )

        records = list(ArtifactHistory.objects.all())

        self.assertEqual(records, [newer, older])
