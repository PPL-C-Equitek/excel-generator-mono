from django.test import TestCase

from authentication.models import User
from artifact_history.models import ArtifactHistory
from artifact_history.services import create_artifact_history, list_artifact_history_for_user


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
            original_name="report.pdf",
            custom_name=None,
            output_json=make_output_json(),
            status_processing="completed",
            created_at="2026-04-08T10:00:00Z",
        )

        self.assertEqual(record.owner, self.owner)
        self.assertEqual(record.original_name, "report.pdf")
        self.assertEqual(record.output_json["content_data"][0]["table_name"], "Sheet1")
        self.assertTrue(ArtifactHistory.objects.filter(id=record.id).exists())

    def test_list_artifact_history_for_user_returns_only_owned_records(self):
        owned_record = ArtifactHistory.objects.create(
            owner=self.owner,
            original_name="owner.pdf",
            custom_name=None,
            output_json=make_output_json("OwnerSheet", "owner"),
            status_processing="completed",
            created_at="2026-04-08T10:00:00Z",
        )
        ArtifactHistory.objects.create(
            owner=self.other_owner,
            original_name="other.pdf",
            custom_name=None,
            output_json=make_output_json("OtherSheet", "other"),
            status_processing="completed",
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
