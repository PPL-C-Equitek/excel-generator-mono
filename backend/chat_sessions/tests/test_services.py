from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from unittest.mock import patch

from authentication.models import User
from chat_sessions.models import ChatMessage, GeneratedOutput, Session
from chat_sessions.services import (
    _build_fallback_thinking_log,
    _normalize_fallback_lines,
    _select_thinking_log_confidence,
    append_assistant_message,
    append_user_message,
    build_frontend_thinking_log_response,
    build_history_with_summary,
    create_generated_output,
    create_session_for_user,
    delete_session,
    get_generated_output_for_session_user,
    get_default_session_detail_pagination,
    get_paginated_session_detail_for_user,
    get_session_for_user,
    list_sessions_for_user,
    summarize_old_messages,
    SUMMARY_RECENT_MESSAGES_KEEP,
    SUMMARY_REFRESH_THRESHOLD,
    update_session_title,
    get_summary_threshold,
    validate_session_detail_pagination_params,
)


class ChatSessionServiceTest(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="owner-services@example.com",
            name="Owner Services",
            password="secret",
            status="verified",
        )
        self.other_user = User.objects.create_user(
            email="other-services@example.com",
            name="Other Services",
            password="secret",
            status="verified",
        )

    def test_create_session_for_user_creates_session_with_default_title(self):
        session = create_session_for_user(self.owner)

        self.assertEqual(session.owner, self.owner)
        self.assertEqual(session.title, "")
        self.assertTrue(Session.objects.filter(id=session.id).exists())

    def test_list_sessions_for_user_returns_only_owned_sessions(self):
        owned_older = Session.objects.create(
            owner=self.owner,
            title="Owned Older",
        )
        owned_newer = Session.objects.create(
            owner=self.owner,
            title="Owned Newer",
        )
        Session.objects.create(
            owner=self.other_user,
            title="Other User Session",
        )

        sessions = list(list_sessions_for_user(self.owner))

        self.assertEqual([session.id for session in sessions], [owned_newer.id, owned_older.id])

    def test_list_sessions_for_user_applies_limit_and_offset(self):
        owned_oldest = Session.objects.create(
            owner=self.owner,
            title="Owned Oldest",
        )
        owned_middle = Session.objects.create(
            owner=self.owner,
            title="Owned Middle",
        )
        owned_newest = Session.objects.create(
            owner=self.owner,
            title="Owned Newest",
        )

        sessions = list(list_sessions_for_user(self.owner, limit=1, offset=1))

        self.assertEqual([session.id for session in sessions], [owned_middle.id])
        self.assertNotIn(owned_newest.id, [session.id for session in sessions])
        self.assertNotIn(owned_oldest.id, [session.id for session in sessions])

    def test_list_sessions_for_user_rejects_non_positive_limit(self):
        with self.assertRaisesMessage(ValueError, "limit must be greater than 0."):
            list(list_sessions_for_user(self.owner, limit=0, offset=0))

    def test_list_sessions_for_user_rejects_negative_offset(self):
        with self.assertRaisesMessage(ValueError, "offset must be greater than or equal to 0."):
            list(list_sessions_for_user(self.owner, limit=10, offset=-1))

    def test_list_sessions_for_user_rejects_limit_above_maximum(self):
        with self.assertRaisesMessage(ValueError, "limit must be less than or equal to 50."):
            list(list_sessions_for_user(self.owner, limit=51, offset=0))

    def test_list_sessions_for_user_defers_unused_fields_for_list_view(self):
        Session.objects.create(
            owner=self.owner,
            title="Owned Session",
        )

        session = list(list_sessions_for_user(self.owner, limit=10, offset=0))[0]

        self.assertSetEqual(session.get_deferred_fields(), {"owner_id"})

    def test_get_session_for_user_returns_owned_session(self):
        session = Session.objects.create(
            owner=self.owner,
            title="Owned Session",
        )

        result = get_session_for_user(self.owner, session.id)

        self.assertEqual(result, session)

    def test_get_session_for_user_returns_none_for_non_owned_session(self):
        session = Session.objects.create(
            owner=self.other_user,
            title="Other User Session",
        )

        result = get_session_for_user(self.owner, session.id)

        self.assertIsNone(result)

    def test_get_generated_output_for_session_user_returns_owned_output(self):
        session = Session.objects.create(
            owner=self.owner,
            title="Owned Session",
        )
        output = GeneratedOutput.objects.create(
            session=session,
            output_json={"document_info": {}, "summary": {}, "content_data": []},
        )

        result = get_generated_output_for_session_user(
            self.owner,
            session.id,
            output.id,
        )

        self.assertEqual(result, output)

    def test_get_generated_output_for_session_user_returns_none_for_non_owned_session(self):
        session = Session.objects.create(
            owner=self.other_user,
            title="Other User Session",
        )
        output = GeneratedOutput.objects.create(
            session=session,
            output_json={"document_info": {}, "summary": {}, "content_data": []},
        )

        result = get_generated_output_for_session_user(
            self.owner,
            session.id,
            output.id,
        )

        self.assertIsNone(result)

    def test_get_generated_output_for_session_user_returns_none_when_output_belongs_to_other_session(self):
        owned_session = Session.objects.create(
            owner=self.owner,
            title="Owned Session",
        )
        other_owned_session = Session.objects.create(
            owner=self.owner,
            title="Other Owned Session",
        )
        output = GeneratedOutput.objects.create(
            session=other_owned_session,
            output_json={"document_info": {}, "summary": {}, "content_data": []},
        )

        result = get_generated_output_for_session_user(
            self.owner,
            owned_session.id,
            output.id,
        )

        self.assertIsNone(result)

    def test_get_generated_output_for_session_user_returns_none_when_output_missing(self):
        session = Session.objects.create(
            owner=self.owner,
            title="Owned Session",
        )

        result = get_generated_output_for_session_user(
            self.owner,
            session.id,
            "3208d1c1-e26f-4565-a2d8-b756b7f364c7",
        )

        self.assertIsNone(result)

    def test_get_paginated_session_detail_for_user_returns_default_slices(self):
        session = Session.objects.create(
            owner=self.owner,
            title="Owned Session",
        )
        for index in range(21):
            ChatMessage.objects.create(
                session=session,
                role=ChatMessage.ROLE_USER,
                content=f"Message {index}",
                created_at=timezone.now() + timezone.timedelta(minutes=index),
            )
        for index in range(11):
            GeneratedOutput.objects.create(
                session=session,
                output_json={"document_info": {}, "summary": {}, "content_data": [index]},
                created_at=timezone.now() + timezone.timedelta(minutes=index),
            )

        result = get_paginated_session_detail_for_user(self.owner, session.id)

        self.assertEqual(result.id, session.id)
        self.assertEqual(result.messages["count"], 21)
        self.assertEqual(result.messages["limit"], 20)
        self.assertEqual(result.messages["offset"], 0)
        self.assertEqual(len(result.messages["results"]), 20)
        self.assertEqual(result.messages["results"][0].content, "Message 0")
        self.assertEqual(result.generated_outputs["count"], 11)
        self.assertEqual(result.generated_outputs["limit"], 10)
        self.assertEqual(result.generated_outputs["offset"], 0)
        self.assertEqual(len(result.generated_outputs["results"]), 10)

    def test_get_paginated_session_detail_for_user_applies_explicit_offsets(self):
        session = Session.objects.create(
            owner=self.owner,
            title="Owned Session",
        )
        messages = [
            ChatMessage.objects.create(
                session=session,
                role=ChatMessage.ROLE_USER,
                content=f"Message {index}",
                created_at=timezone.now() + timezone.timedelta(minutes=index),
            )
            for index in range(3)
        ]
        outputs = [
            GeneratedOutput.objects.create(
                session=session,
                output_json={"document_info": {}, "summary": {}, "content_data": [index]},
                created_at=timezone.now() + timezone.timedelta(minutes=index),
            )
            for index in range(3)
        ]

        result = get_paginated_session_detail_for_user(
            self.owner,
            session.id,
            messages_limit=1,
            messages_offset=2,
            outputs_limit=1,
            outputs_offset=1,
        )

        self.assertEqual(result.messages["results"], [messages[2]])
        self.assertEqual(result.generated_outputs["results"], [outputs[1]])

    def test_get_paginated_session_detail_for_user_returns_empty_slices_when_offset_exceeds_count(self):
        session = Session.objects.create(
            owner=self.owner,
            title="Owned Session",
        )

        result = get_paginated_session_detail_for_user(
            self.owner,
            session.id,
            messages_limit=20,
            messages_offset=50,
            outputs_limit=10,
            outputs_offset=50,
        )

        self.assertEqual(result.messages["count"], 0)
        self.assertEqual(result.messages["results"], [])
        self.assertEqual(result.generated_outputs["count"], 0)
        self.assertEqual(result.generated_outputs["results"], [])

    def test_get_paginated_session_detail_for_user_returns_none_for_non_owned_session(self):
        session = Session.objects.create(
            owner=self.other_user,
            title="Other User Session",
        )

        result = get_paginated_session_detail_for_user(self.owner, session.id)

        self.assertIsNone(result)

    def test_get_paginated_session_detail_for_user_rejects_invalid_limits(self):
        session = Session.objects.create(
            owner=self.owner,
            title="Owned Session",
        )

        with self.assertRaisesMessage(ValueError, "messages_limit must be greater than 0."):
            get_paginated_session_detail_for_user(self.owner, session.id, messages_limit=0)

        with self.assertRaisesMessage(ValueError, "outputs_limit must be less than or equal to 50."):
            get_paginated_session_detail_for_user(self.owner, session.id, outputs_limit=51)

    def test_get_paginated_session_detail_for_user_rejects_invalid_offsets(self):
        session = Session.objects.create(
            owner=self.owner,
            title="Owned Session",
        )

        with self.assertRaisesMessage(ValueError, "messages_offset must be greater than or equal to 0."):
            get_paginated_session_detail_for_user(self.owner, session.id, messages_offset=-1)

        with self.assertRaisesMessage(ValueError, "outputs_offset must be greater than or equal to 0."):
            get_paginated_session_detail_for_user(self.owner, session.id, outputs_offset=-1)

    def test_get_default_session_detail_pagination_returns_fresh_copy(self):
        first = get_default_session_detail_pagination()
        second = get_default_session_detail_pagination()

        first["messages_limit"] = 99

        self.assertEqual(second["messages_limit"], 20)
        self.assertEqual(second["outputs_limit"], 10)

    def test_validate_session_detail_pagination_params_accepts_valid_values(self):
        pagination = {
            "messages_limit": 20,
            "messages_offset": 0,
            "outputs_limit": 10,
            "outputs_offset": 0,
        }

        validate_session_detail_pagination_params(pagination)

    def test_validate_session_detail_pagination_params_rejects_invalid_values(self):
        with self.assertRaisesMessage(ValueError, "messages_limit must be less than or equal to 50."):
            validate_session_detail_pagination_params(
                {
                    "messages_limit": 51,
                    "messages_offset": 0,
                    "outputs_limit": 10,
                    "outputs_offset": 0,
                }
            )

        with self.assertRaisesMessage(ValueError, "outputs_offset must be greater than or equal to 0."):
            validate_session_detail_pagination_params(
                {
                    "messages_limit": 20,
                    "messages_offset": 0,
                    "outputs_limit": 10,
                    "outputs_offset": -1,
                }
            )

    def test_update_session_title_trims_and_saves_value(self):
        session = Session.objects.create(
            owner=self.owner,
            title="Old Title",
        )

        updated = update_session_title(session, "  New Session Title  ")

        self.assertEqual(updated.title, "New Session Title")
        session.refresh_from_db()
        self.assertEqual(session.title, "New Session Title")

    def test_delete_session_removes_session(self):
        session = Session.objects.create(
            owner=self.owner,
            title="Session To Delete",
        )

        delete_session(session)

        self.assertFalse(Session.objects.filter(id=session.id).exists())


class AppendUserMessageServiceTest(TestCase):
    def setUp(self):
        owner = User.objects.create_user(
            email="append-user@example.com",
            name="Append User",
            password="secret",
            status="verified",
        )
        self.session = Session.objects.create(owner=owner)

    def test_append_user_message_creates_message_with_user_role(self):
        msg = append_user_message(self.session, "Halo")

        self.assertEqual(msg.role, ChatMessage.ROLE_USER)
        self.assertEqual(msg.content, "Halo")
        self.assertEqual(msg.session, self.session)

    def test_append_user_message_persists_to_db(self):
        msg = append_user_message(self.session, "Halo")

        self.assertTrue(ChatMessage.objects.filter(id=msg.id).exists())

    def test_append_user_message_thinking_log_is_empty_by_default(self):
        msg = append_user_message(self.session, "Halo")

        self.assertEqual(msg.thinking_log, "")

    def test_append_user_message_updates_session_last_message_at(self):
        self.assertIsNone(self.session.last_message_at)

        append_user_message(self.session, "Halo")

        self.session.refresh_from_db()
        self.assertIsNotNone(self.session.last_message_at)


class AppendAssistantMessageServiceTest(TestCase):
    def setUp(self):
        owner = User.objects.create_user(
            email="append-assistant@example.com",
            name="Append Assistant",
            password="secret",
            status="verified",
        )
        self.session = Session.objects.create(owner=owner)

    def test_append_assistant_message_creates_message_with_assistant_role(self):
        msg = append_assistant_message(self.session, "Berikut jawabannya.")

        self.assertEqual(msg.role, ChatMessage.ROLE_ASSISTANT)
        self.assertEqual(msg.content, "Berikut jawabannya.")
        self.assertEqual(msg.session, self.session)

    def test_append_assistant_message_persists_to_db(self):
        msg = append_assistant_message(self.session, "Berikut jawabannya.")

        self.assertTrue(ChatMessage.objects.filter(id=msg.id).exists())

    def test_append_assistant_message_stores_thinking_log_when_provided(self):
        msg = append_assistant_message(
            self.session, "Jawaban.", thinking_log="langkah berpikir"
        )

        self.assertEqual(msg.thinking_log, "langkah berpikir")

    def test_append_assistant_message_thinking_log_defaults_to_empty(self):
        msg = append_assistant_message(self.session, "Jawaban.")

        self.assertEqual(msg.thinking_log, "")

    def test_append_assistant_message_updates_session_last_message_at(self):
        self.assertIsNone(self.session.last_message_at)

        append_assistant_message(self.session, "Berikut jawabannya.")

        self.session.refresh_from_db()
        self.assertIsNotNone(self.session.last_message_at)


class CreateGeneratedOutputServiceTest(TestCase):
    def setUp(self):
        owner = User.objects.create_user(
            email="gen-output@example.com",
            name="Gen Output",
            password="secret",
            status="verified",
        )
        self.session = Session.objects.create(owner=owner)
        self.valid_output_json = {
            "headers": ["A"],
            "rows": [["1"]],
            "final_answer": "Raw output",
        }
        self.valid_thinking_log = "Checked totals and aligned categories."

    def test_create_generated_output_creates_output_with_correct_data(self):
        output = create_generated_output(
            self.session,
            self.valid_output_json,
            self.valid_thinking_log,
        )

        self.assertEqual(output.output_json, self.valid_output_json)
        self.assertEqual(output.thinking_log, self.valid_thinking_log)
        self.assertEqual(output.session, self.session)

    def test_create_generated_output_persists_to_db(self):
        output = create_generated_output(
            self.session,
            self.valid_output_json,
            self.valid_thinking_log,
        )

        self.assertTrue(GeneratedOutput.objects.filter(id=output.id).exists())

    def test_create_generated_output_updates_session_last_output_at(self):
        self.assertIsNone(self.session.last_output_at)

        create_generated_output(
            self.session,
            self.valid_output_json,
            self.valid_thinking_log,
        )

        self.session.refresh_from_db()
        self.assertIsNotNone(self.session.last_output_at)

    def test_create_generated_output_defaults_thinking_log_to_empty_string(self):
        output = create_generated_output(
            self.session,
            self.valid_output_json,
        )

        self.assertEqual(output.thinking_log, "")

    def test_create_generated_output_supports_legacy_export_payload_as_third_positional_arg(self):
        legacy_export_output_json = {
            "document_info": {"source_type": "Excel"},
            "summary": {"total_tables": 1},
            "content_data": [],
        }

        output = create_generated_output(
            self.session,
            self.valid_output_json,
            legacy_export_output_json,
        )

        self.assertEqual(output.thinking_log, "")
        self.assertEqual(output.export_output_json, legacy_export_output_json)

    def test_create_generated_output_rejects_non_dict_output_json(self):
        with self.assertRaises(ValidationError):
            create_generated_output(
                self.session,
                ["bukan", "dict"],
                self.valid_thinking_log,
            )


class SummarizeOldMessagesServiceTest(SimpleTestCase):
    
    def _make_messages(self, n):
        roles = ["user", "assistant"]
        return [{"role": roles[i % 2], "content": f"message {i}"} for i in range(n)]

    @patch("chat_sessions.services.generate_chat_response")
    def test_returns_empty_string_for_empty_message_list(self, mock_llm):
        result = summarize_old_messages([])

        self.assertEqual(result, "")
        mock_llm.assert_not_called()

    @patch("chat_sessions.services.generate_chat_response")
    def test_calls_llm_and_returns_summary_text(self, mock_llm):
        mock_llm.return_value = "User asked about X and assistant explained Y."
        messages = self._make_messages(4)

        result = summarize_old_messages(messages)

        self.assertEqual(result, "User asked about X and assistant explained Y.")
        mock_llm.assert_called_once()

    @patch("chat_sessions.services.generate_chat_response")
    def test_prompt_includes_all_message_content(self, mock_llm):
        mock_llm.return_value = "summary"
        messages = [
            {"role": "user", "content": "Hello there"},
            {"role": "assistant", "content": "Hi! How can I help?"},
        ]

        summarize_old_messages(messages)

        call_args = mock_llm.call_args[0][0]
        combined = " ".join(m["content"] for m in call_args)
        self.assertIn("Hello there", combined)
        self.assertIn("Hi! How can I help?", combined)

    @patch("chat_sessions.services.generate_chat_response")
    def test_prompt_is_sent_as_user_role(self, mock_llm):
        mock_llm.return_value = "summary"

        summarize_old_messages(self._make_messages(2))

        call_args = mock_llm.call_args[0][0]
        self.assertEqual(len(call_args), 1)
        self.assertEqual(call_args[0]["role"], "user")


class BuildFrontendThinkingLogResponseTest(SimpleTestCase):
    def test_reuses_existing_valid_thinking_log_unchanged(self):
        payload = {
            "result": {"ok": True},
            "reasoning": {
                "final_answer": "Normalized output prepared.",
                "reasoning_steps": ["Mapped headers", "Validated totals"],
                "thinking_log": [
                    "Detected headers: ID, Barang, Harga, Discount, Total.",
                    "Grouped remaining values into rows of five columns.",
                    "Validated row consistency.",
                    "Confidence: High",
                ],
            },
        }

        response = build_frontend_thinking_log_response(payload)

        self.assertEqual(
            response,
            {
                "thinking_log": [
                    "Detected headers: ID, Barang, Harga, Discount, Total.",
                    "Grouped remaining values into rows of five columns.",
                    "Validated row consistency.",
                    "Confidence: High",
                ]
            },
        )

    def test_generates_fallback_when_existing_thinking_log_contains_blocked_pattern(self):
        payload = {
            "reasoning": {
                "final_answer": "Extraction result prepared.",
                "reasoning_steps": [
                    "Detected headers",
                    "Grouped rows",
                ],
                "thinking_log": [
                    "I considered multiple options before choosing this format.",
                ],
            }
        }

        response = build_frontend_thinking_log_response(payload)

        self.assertEqual(
            response,
            {
                "thinking_log": [
                    "Identified available response reasoning fields.",
                    "Summarized key transformation steps from response data.",
                    "Aligned summary details with the final answer content.",
                    "Validated thinking log consistency for frontend parsing.",
                    "Prepared parser-safe thinking log output.",
                    "Confidence: High",
                ]
            },
        )

    def test_returns_fail_safe_when_reasoning_fields_are_missing(self):
        response = build_frontend_thinking_log_response({"result": {"items": []}})

        self.assertEqual(
            response,
            {
                "thinking_log": [
                    "Processed available response data.",
                    "Unable to extract detailed reasoning.",
                    "Prepared safest structured output.",
                    "Confidence: Low",
                ]
            },
        )

    def test_returns_fail_safe_when_payload_is_non_dict(self):
        response = build_frontend_thinking_log_response(["not", "a", "dict"])

        self.assertEqual(
            response,
            {
                "thinking_log": [
                    "Processed available response data.",
                    "Unable to extract detailed reasoning.",
                    "Prepared safest structured output.",
                    "Confidence: Low",
                ]
            },
        )

    def test_generates_fallback_when_existing_thinking_log_contains_non_string_item(self):
        payload = {
            "reasoning": {
                "final_answer": "Extraction result prepared.",
                "reasoning_steps": ["Detected headers"],
                "thinking_log": [123],
            }
        }

        response = build_frontend_thinking_log_response(payload)

        self.assertEqual(response["thinking_log"][-1], "Confidence: High")

    def test_generates_fallback_when_existing_thinking_log_contains_blank_item(self):
        payload = {
            "reasoning": {
                "final_answer": "Extraction result prepared.",
                "reasoning_steps": ["Detected headers"],
                "thinking_log": ["   \n\t  "],
            }
        }

        response = build_frontend_thinking_log_response(payload)

        self.assertEqual(response["thinking_log"][-1], "Confidence: High")

    def test_fallback_includes_only_final_answer_path_and_sets_medium_confidence(self):
        payload = {
            "reasoning": {
                "final_answer": "Only final answer is available.",
                "reasoning_steps": [],
            }
        }

        response = build_frontend_thinking_log_response(payload)

        self.assertEqual(
            response,
            {
                "thinking_log": [
                    "Identified available response reasoning fields.",
                    "Aligned summary details with the final answer content.",
                    "Validated thinking log consistency for frontend parsing.",
                    "Prepared parser-safe thinking log output.",
                    "Confidence: Medium",
                ]
            },
        )

    def test_fallback_normalizes_blank_reasoning_steps_and_sets_medium_confidence(self):
        payload = {
            "reasoning": {
                "final_answer": None,
                "reasoning_steps": ["", "  ", "Mapped rows"],
            }
        }

        response = build_frontend_thinking_log_response(payload)

        self.assertEqual(
            response,
            {
                "thinking_log": [
                    "Identified available response reasoning fields.",
                    "Summarized key transformation steps from response data.",
                    "Validated thinking log consistency for frontend parsing.",
                    "Prepared parser-safe thinking log output.",
                    "Confidence: Medium",
                ]
            },
        )

    def test_private_helpers_cover_unreachable_branches(self):
        self.assertEqual(
            _build_fallback_thinking_log("not-a-dict"),
            [
                "Processed available response data.",
                "Unable to extract detailed reasoning.",
                "Prepared safest structured output.",
                "Confidence: Low",
            ],
        )
        self.assertEqual(_select_thinking_log_confidence([], ""), "Low")
        self.assertEqual(
            _normalize_fallback_lines(
                [
                    "line-a",
                    "line-a",
                    "   ",
                    "line-b",
                ],
                "Low",
            ),
            ["line-a", "line-b", "Confidence: Low"],
        )


class BuildHistoryWithSummaryServiceTest(TestCase):

    def setUp(self):
        owner = User.objects.create_user(
            email="summary-svc@example.com",
            name="Summary User",
            password="secret",
            status="verified",
        )
        self.session = Session.objects.create(owner=owner)

    def _make_history(self, n):
        roles = ["user", "assistant"]
        return [{"role": roles[i % 2], "content": f"msg {i}"} for i in range(n)]


    def test_returns_history_unchanged_when_at_or_below_threshold(self):
        history = self._make_history(get_summary_threshold())

        result = build_history_with_summary(self.session, history)

        self.assertEqual(result, history)


    def test_does_not_call_llm_when_history_is_short(self):
        history = self._make_history(get_summary_threshold() - 1)

        with patch("chat_sessions.services.summarize_old_messages") as mock_sum:
            build_history_with_summary(self.session, history)
            mock_sum.assert_not_called()


    @patch("chat_sessions.services.summarize_old_messages")
    def test_calls_summarize_when_history_exceeds_threshold_and_no_summary_cached(
        self, mock_sum
    ):
        mock_sum.return_value = "First summary."
        history = self._make_history(get_summary_threshold() + 1)

        build_history_with_summary(self.session, history)

        mock_sum.assert_called_once()

    @patch("chat_sessions.services.summarize_old_messages")
    def test_persists_summary_to_session_on_first_creation(self, mock_sum):
        mock_sum.return_value = "Persisted summary."
        history = self._make_history(get_summary_threshold() + 1)

        build_history_with_summary(self.session, history)

        self.session.refresh_from_db()
        self.assertEqual(self.session.history_summary, "Persisted summary.")

    @patch("chat_sessions.services.summarize_old_messages")
    def test_result_starts_with_summary_system_message(self, mock_sum):
        mock_sum.return_value = "My summary."
        history = self._make_history(get_summary_threshold() + 1)

        result = build_history_with_summary(self.session, history)

        self.assertEqual(result[0]["role"], "system")
        self.assertIn("My summary.", result[0]["content"])

    @patch("chat_sessions.services.summarize_old_messages")
    def test_result_contains_recent_messages_verbatim(self, mock_sum):
        mock_sum.return_value = "summary"
        history = self._make_history(get_summary_threshold() + 5)

        result = build_history_with_summary(self.session, history)

        self.assertEqual(len(result), 1 + SUMMARY_RECENT_MESSAGES_KEEP)
        self.assertEqual(result[1:], history[-SUMMARY_RECENT_MESSAGES_KEEP:])


    @patch("chat_sessions.services.summarize_old_messages")
    def test_reuses_cached_summary_without_calling_llm_again(self, mock_sum):
        self.session.history_summary = "Cached summary."
        self.session.save(update_fields=["history_summary"])
        old_count = get_summary_threshold() + 1 - SUMMARY_RECENT_MESSAGES_KEEP
        self.session.history_summary_watermark = old_count
        self.session.save(update_fields=["history_summary", "history_summary_watermark"])
        history = self._make_history(get_summary_threshold() + 1)

        result = build_history_with_summary(self.session, history)

        mock_sum.assert_not_called()
        self.assertIn("Cached summary.", result[0]["content"])


    @patch("chat_sessions.services.summarize_old_messages")
    def test_refreshes_summary_when_new_old_messages_exceed_refresh_threshold(
        self, mock_sum
    ):
        mock_sum.return_value = "Refreshed summary."
        self.session.history_summary = "Old summary."
        history = self._make_history(get_summary_threshold() + SUMMARY_REFRESH_THRESHOLD + 1)
        old_count = len(history) - SUMMARY_RECENT_MESSAGES_KEEP
        self.session.history_summary_watermark = old_count - SUMMARY_REFRESH_THRESHOLD
        self.session.save(update_fields=["history_summary", "history_summary_watermark"])

        result = build_history_with_summary(self.session, history)

        mock_sum.assert_called_once()
        self.assertIn("Refreshed summary.", result[0]["content"])

    @patch("chat_sessions.services.summarize_old_messages")
    def test_persists_refreshed_summary_to_db(self, mock_sum):
        mock_sum.return_value = "New rolled summary."
        self.session.history_summary = "Old summary."
        history = self._make_history(get_summary_threshold() + SUMMARY_REFRESH_THRESHOLD + 1)
        old_count = len(history) - SUMMARY_RECENT_MESSAGES_KEEP
        self.session.history_summary_watermark = old_count - SUMMARY_REFRESH_THRESHOLD
        self.session.save(update_fields=["history_summary", "history_summary_watermark"])

        build_history_with_summary(self.session, history)

        self.session.refresh_from_db()
        self.assertEqual(self.session.history_summary, "New rolled summary.")

    @patch("chat_sessions.services.summarize_old_messages")
    def test_does_not_refresh_when_new_messages_below_refresh_threshold(
        self, mock_sum
    ):
        self.session.history_summary = "Still valid summary."
        self.session.save(update_fields=["history_summary"])
        history = self._make_history(get_summary_threshold() + 1)
        old_count = len(history) - SUMMARY_RECENT_MESSAGES_KEEP
        self.session.history_summary_watermark = old_count - 1
        self.session.save(update_fields=["history_summary", "history_summary_watermark"])

        build_history_with_summary(self.session, history)

        mock_sum.assert_not_called()
