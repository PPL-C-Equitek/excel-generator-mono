"""Tests for llm repository helpers."""

from django.test import TestCase

from authentication.models import User
from chat_sessions.models import GeneratedOutput, Session
from llm.repositories import (
    get_generated_output_for_user_by_id,
    get_thinking_log_queryset_for_user,
)


class ThinkingLogRepositoryTest(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="repo-owner@example.com",
            name="Repo Owner",
            password="secret",
            status="verified",
        )
        self.other_user = User.objects.create_user(
            email="repo-other@example.com",
            name="Repo Other",
            password="secret",
            status="verified",
        )
        self.owner_session = Session.objects.create(owner=self.owner, title="Owner")
        self.other_session = Session.objects.create(owner=self.other_user, title="Other")

    def _create_output(self, *, session, thinking_log: str):
        return GeneratedOutput.objects.create(
            session=session,
            output_json={"content_data": []},
            thinking_log=thinking_log,
        )

    def test_get_thinking_log_queryset_for_user_returns_owned_non_empty_records_only(self):
        owned_record = self._create_output(
            session=self.owner_session,
            thinking_log="Owned thinking log.",
        )
        self._create_output(session=self.owner_session, thinking_log="")
        self._create_output(session=self.other_session, thinking_log="Other thinking log.")

        queryset = get_thinking_log_queryset_for_user(self.owner)

        self.assertEqual(queryset.count(), 1)
        self.assertEqual(list(queryset), [owned_record])

    def test_get_generated_output_for_user_by_id_returns_owned_record(self):
        output = self._create_output(
            session=self.owner_session,
            thinking_log="Owned thinking log.",
        )

        result = get_generated_output_for_user_by_id(self.owner, output.id)

        self.assertEqual(result, output)

    def test_get_generated_output_for_user_by_id_returns_none_for_foreign_record(self):
        foreign_output = self._create_output(
            session=self.other_session,
            thinking_log="Foreign thinking log.",
        )

        result = get_generated_output_for_user_by_id(self.owner, foreign_output.id)

        self.assertIsNone(result)
