from django.test import TestCase
from django.db import IntegrityError
from unittest.mock import patch
import uuid

from authentication.models import User
from artifact_history.models import ArtifactHistory, HistoryExportArtifact
from artifact_history.services import (
    delete_artifact_history,
    get_artifact_history_for_user,
    create_artifact_history,
    create_history_export_artifact,
    get_history_export_artifact,
    list_artifact_history_for_user,
    update_artifact_history_custom_name,
)


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
        self.assertIsNone(record.session_id)
        self.assertTrue(ArtifactHistory.objects.filter(id=record.id).exists())

    def test_create_artifact_history_persists_session_id(self):
        session_id = uuid.uuid4()

        record = create_artifact_history(
            owner=self.owner,
            original_name="report.pdf",
            custom_name=None,
            output_json=make_output_json(),
            status_processing="completed",
            session_id=session_id,
            created_at="2026-04-08T10:00:00Z",
        )

        self.assertEqual(record.session_id, session_id)

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

    def test_get_artifact_history_for_user_returns_owned_record(self):
        record = ArtifactHistory.objects.create(
            owner=self.owner,
            original_name="owner.pdf",
            custom_name=None,
            output_json=make_output_json("OwnerSheet", "owner"),
            status_processing="completed",
            created_at="2026-04-08T10:00:00Z",
        )

        result = get_artifact_history_for_user(self.owner, record.id)

        self.assertEqual(result, record)

    def test_get_artifact_history_for_user_returns_none_for_other_user_record(self):
        record = ArtifactHistory.objects.create(
            owner=self.other_owner,
            original_name="other.pdf",
            custom_name=None,
            output_json=make_output_json("OtherSheet", "other"),
            status_processing="completed",
            created_at="2026-04-08T10:00:00Z",
        )

        result = get_artifact_history_for_user(self.owner, record.id)

        self.assertIsNone(result)

    def test_update_artifact_history_custom_name_trims_and_saves_value(self):
        record = ArtifactHistory.objects.create(
            owner=self.owner,
            original_name="owner.pdf",
            custom_name=None,
            output_json=make_output_json("OwnerSheet", "owner"),
            status_processing="completed",
            created_at="2026-04-08T10:00:00Z",
        )

        updated_record = update_artifact_history_custom_name(
            record,
            "  Quarterly Report  ",
        )

        record.refresh_from_db()
        self.assertEqual(updated_record.custom_name, "Quarterly Report")
        self.assertEqual(record.custom_name, "Quarterly Report")

    def test_delete_artifact_history_removes_record(self):
        record = ArtifactHistory.objects.create(
            owner=self.owner,
            original_name="owner.pdf",
            custom_name=None,
            output_json=make_output_json("OwnerSheet", "owner"),
            status_processing="completed",
            created_at="2026-04-08T10:00:00Z",
        )

        delete_artifact_history(record)

        self.assertFalse(ArtifactHistory.objects.filter(id=record.id).exists())

    def test_list_artifact_history_for_user_rejects_invalid_limit(self):
        with self.assertRaises(ValueError):
            list_artifact_history_for_user(self.owner, limit=0, offset=0)

    def test_list_artifact_history_for_user_rejects_invalid_offset(self):
        with self.assertRaises(ValueError):
            list_artifact_history_for_user(self.owner, limit=10, offset=-1)

    def test_create_artifact_history_uses_default_created_at_when_omitted(self):
        record = create_artifact_history(
            owner=self.owner,
            original_name="report.pdf",
            custom_name=None,
            output_json=make_output_json(),
            status_processing="completed",
        )

        self.assertIsNotNone(record.created_at)


class HistoryExportArtifactServiceTest(TestCase):
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
        self.history = ArtifactHistory.objects.create(
            owner=self.owner,
            original_name="report.pdf",
            custom_name=None,
            output_json=make_output_json(),
            status_processing="completed",
            created_at="2026-04-08T10:00:00Z",
        )

    def test_create_history_export_artifact_persists_owned_cache_record(self):
        artifact = create_history_export_artifact(
            history=self.history,
            owner=self.owner,
            requested_format="xlsx",
            artifact_type="xlsx",
            file_id="xlsx_abc123",
            file_name="export_abc123.xlsx",
            created_at="2026-04-08T10:05:00Z",
        )

        self.assertEqual(artifact.history, self.history)
        self.assertEqual(artifact.owner, self.owner)
        self.assertEqual(artifact.requested_format, "xlsx")

    def test_get_history_export_artifact_returns_owned_cached_artifact(self):
        artifact = create_history_export_artifact(
            history=self.history,
            owner=self.owner,
            requested_format="csv",
            artifact_type="zip",
            file_id="csv_abc123",
            file_name="export_abc123.zip",
            created_at="2026-04-08T10:05:00Z",
        )

        result = get_history_export_artifact(
            history=self.history,
            owner=self.owner,
            requested_format="csv",
        )

        self.assertEqual(result, artifact)

    def test_get_history_export_artifact_returns_none_when_cache_is_missing(self):
        result = get_history_export_artifact(
            history=self.history,
            owner=self.owner,
            requested_format="xlsx",
        )

        self.assertIsNone(result)

    def test_get_history_export_artifact_does_not_return_other_users_cache(self):
        create_history_export_artifact(
            history=self.history,
            owner=self.owner,
            requested_format="xlsx",
            artifact_type="xlsx",
            file_id="xlsx_abc123",
            file_name="export_abc123.xlsx",
            created_at="2026-04-08T10:05:00Z",
        )

        result = get_history_export_artifact(
            history=self.history,
            owner=self.other_owner,
            requested_format="xlsx",
        )

        self.assertIsNone(result)

    def test_create_history_export_artifact_uses_default_created_at_when_omitted(self):
        artifact = create_history_export_artifact(
            history=self.history,
            owner=self.owner,
            requested_format="xlsx",
            artifact_type="xlsx",
            file_id="xlsx_abc123",
            file_name="export_abc123.xlsx",
        )

        self.assertIsNotNone(artifact.created_at)

    @patch("artifact_history.services._create_history_export_artifact_record")
    def test_create_history_export_artifact_returns_existing_record_when_create_hits_unique_race(
        self,
        mock_create,
    ):
        existing_artifact = HistoryExportArtifact.objects.create(
            history=self.history,
            owner=self.owner,
            requested_format="xlsx",
            artifact_type="xlsx",
            file_id="xlsx_existing",
            file_name="export_existing.xlsx",
            created_at="2026-04-08T10:05:00Z",
        )
        mock_create.side_effect = IntegrityError("duplicate key value violates unique constraint")

        artifact = create_history_export_artifact(
            history=self.history,
            owner=self.owner,
            requested_format="xlsx",
            artifact_type="xlsx",
            file_id="xlsx_new",
            file_name="export_new.xlsx",
            created_at="2026-04-08T10:06:00Z",
        )

        self.assertEqual(artifact.id, existing_artifact.id)

    @patch("artifact_history.services._create_history_export_artifact_record")
    def test_create_history_export_artifact_reraises_integrity_error_when_existing_record_is_missing(
        self,
        mock_create,
    ):
        mock_create.side_effect = IntegrityError("duplicate key value violates unique constraint")

        with self.assertRaises(IntegrityError):
            create_history_export_artifact(
                history=self.history,
                owner=self.owner,
                requested_format="xlsx",
                artifact_type="xlsx",
                file_id="xlsx_newtoken",
                file_name="export_newtoken.xlsx",
            )
