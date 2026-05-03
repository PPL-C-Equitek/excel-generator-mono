from django.core.exceptions import ValidationError
from django.test import TestCase
import uuid

from authentication.models import User
from artifact_history.models import ArtifactHistory, HistoryExportArtifact


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

        self.assertEqual(artifact.custom_name, "")

    def test_session_id_defaults_to_none(self):
        artifact = ArtifactHistory.objects.create(
            owner=self.owner,
            original_name="report.pdf",
            custom_name=None,
            output_json=make_output_json(),
            status_processing="completed",
            created_at="2026-04-08T10:00:00Z",
        )

        self.assertIsNone(artifact.session_id)

    def test_session_id_is_persisted_when_provided(self):
        session_id = uuid.uuid4()

        artifact = ArtifactHistory.objects.create(
            owner=self.owner,
            original_name="report.pdf",
            custom_name=None,
            session_id=session_id,
            output_json=make_output_json(),
            status_processing="completed",
            created_at="2026-04-08T10:00:00Z",
        )

        self.assertEqual(artifact.session_id, session_id)

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


class HistoryExportArtifactModelTest(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="owner@example.com",
            name="Owner",
            password="Test12345",
            status="verified",
        )
        self.history = ArtifactHistory.objects.create(
            owner=self.owner,
            original_name="report.pdf",
            custom_name=None,
            output_json=make_output_json(),
            status_processing="completed",
            created_at="2026-04-08T10:00:00Z",
        )

    def test_can_create_xlsx_cached_artifact(self):
        artifact = HistoryExportArtifact.objects.create(
            history=self.history,
            owner=self.owner,
            requested_format="xlsx",
            artifact_type="xlsx",
            file_id="xlsx_abc123",
            file_name="export_abc123.xlsx",
            created_at="2026-04-08T10:05:00Z",
        )

        self.assertEqual(artifact.requested_format, "xlsx")
        self.assertEqual(artifact.artifact_type, "xlsx")

    def test_can_create_csv_request_with_zip_artifact(self):
        artifact = HistoryExportArtifact.objects.create(
            history=self.history,
            owner=self.owner,
            requested_format="csv",
            artifact_type="zip",
            file_id="csv_abc123",
            file_name="export_abc123.zip",
            created_at="2026-04-08T10:05:00Z",
        )

        self.assertEqual(artifact.requested_format, "csv")
        self.assertEqual(artifact.artifact_type, "zip")

    def test_invalid_requested_format_is_rejected(self):
        artifact = HistoryExportArtifact(
            history=self.history,
            owner=self.owner,
            requested_format="pdf",
            artifact_type="xlsx",
            file_id="xlsx_abc123",
            file_name="export_abc123.xlsx",
            created_at="2026-04-08T10:05:00Z",
        )

        with self.assertRaises(ValidationError):
            artifact.save()

    def test_invalid_artifact_type_is_rejected(self):
        artifact = HistoryExportArtifact(
            history=self.history,
            owner=self.owner,
            requested_format="xlsx",
            artifact_type="pdf",
            file_id="xlsx_abc123",
            file_name="export_abc123.xlsx",
            created_at="2026-04-08T10:05:00Z",
        )

        with self.assertRaises(ValidationError):
            artifact.save()

    def test_owner_must_match_the_related_history_owner(self):
        other_owner = User.objects.create_user(
            email="other@example.com",
            name="Other",
            password="Test12345",
            status="verified",
        )
        artifact = HistoryExportArtifact(
            history=self.history,
            owner=other_owner,
            requested_format="xlsx",
            artifact_type="xlsx",
            file_id="xlsx_abc123",
            file_name="export_abc123.xlsx",
            created_at="2026-04-08T10:05:00Z",
        )

        with self.assertRaises(ValidationError):
            artifact.save()
