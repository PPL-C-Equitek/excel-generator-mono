from types import SimpleNamespace

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework.response import Response
from unittest.mock import Mock, patch
from uuid import uuid4

from artifact_history.models import ArtifactHistory
from authentication.models import User
from chat_sessions.models import ChatMessage, GeneratedOutput, Session
from llm.services.generation_service import CustomSchemaNotFoundError
from llm.services.openai_client import OpenAITextGenerationProvider
from llm.services.openai_client import (
    OpenAIConfigurationError,
    OpenAIServiceError,
    OpenAIUpstreamError,
)
from llm.views import (
    LLM_GENERATE_RATE_LIMIT_PER_MINUTE,
    _LlmGenerateWorkflow,
    _build_llm_generate_idempotency_cache_key,
    _build_llm_generate_idempotency_response,
    _build_llm_generate_response_payload,
    _compute_llm_generate_idempotency_request_hash,
    _execute_llm_generate_flow,
    _extract_llm_generate_idempotency_key,
    _run_llm_generate_with_idempotency,
    _generate_reply_and_title_for_new_session,
    _estimate_payload_size_bytes,
    _build_generate_bootstrap_message,
    _build_generate_success_response,
    _build_refinement_config,
    _extract_follow_up_prompt,
    _generate_output_json,
    _generate_optional_reasoning,
    _generate_send_message_reply_and_title,
    _hydrate_previous_output_from_target,
    _invalid_thinking_log_identifier_response,
    _invalid_thinking_log_pagination_response,
    _is_persistable_authenticated_user,
    _llm_generate_rate_limit_key,
    _llm_generate_error_response,
    _parse_send_message_json_result,
    _parse_thinking_log_identifier,
    _parse_thinking_log_page_size,
    _parse_thinking_log_positive_int,
    _persist_generate_output_for_authenticated_user,
    _resolve_cached_llm_generate_idempotency_response,
    _resolve_generate_session,
    _resolve_generate_source_message,
    _resolve_llm_generate_rate_limit_per_minute,
    _resolve_llm_generate_idempotency_ttl_seconds,
    _resolve_message_target_output,
    _resolve_send_message_session_context,
    _run_basic_generation,
    _schedule_artifact_history_creation,
    _sanitize_output_json,
    _thinking_log_not_found_response,
    build_llm_generation_service,
    build_llm_reasoning_service,
    get_authenticated_user_id,
)
from llm.services.chat_context_service import (
    _build_compact_file_context,
    _build_table_context_lines,
    _inject_file_context_if_available,
)
from llm.serializers import MAX_MESSAGE_LENGTH

class LlmGenerateEndpointTest(SimpleTestCase):
    _raw_api_client_class = APIClient

    def setUp(self):
        super().setUp()
        cache.clear()
        self._api_client_patch = patch(
            "llm.tests.test_views.APIClient",
            side_effect=self._build_verified_client,
        )
        self._api_client_patch.start()

    def tearDown(self):
        self._api_client_patch.stop()
        super().tearDown()

    def _build_verified_user(self, *, user_id=None, status="verified"):
        return SimpleNamespace(
            id=user_id or uuid4(),
            is_authenticated=True,
            status=status,
        )

    def _build_verified_client(self, *args, user=None, **kwargs):
        client = self._raw_api_client_class(*args, **kwargs)
        client.force_authenticate(user=user or self._build_verified_user())
        return client

    def _build_unauthenticated_client(self):
        return self._raw_api_client_class()

    def test_build_llm_generation_service_returns_default_dependencies(self):
        service = build_llm_generation_service()

        self.assertEqual(service.__class__.__name__, "LlmGenerationService")
        self.assertEqual(service.json_generator.__class__.__name__, "JsonGenerationService")
        self.assertIsInstance(service.json_generator.text_provider, OpenAITextGenerationProvider)
        self.assertEqual(
            service.schema_prompt_source.__class__.__name__,
            "DjangoCustomSchemaPromptSource",
        )
        self.assertIsNone(service.schema_prompt_source.owner_id)

    def test_build_llm_generation_service_uses_authenticated_user_id_for_schema_source(self):
        owner_id = uuid4()

        service = build_llm_generation_service(
            SimpleNamespace(id=owner_id, is_authenticated=True)
        )

        self.assertEqual(service.schema_prompt_source.owner_id, owner_id)

    def test_get_authenticated_user_id_returns_none_for_anonymous_user(self):
        result = get_authenticated_user_id(SimpleNamespace(is_authenticated=False))

        self.assertIsNone(result)

    def test_is_persistable_authenticated_user_partitions(self):
        model_like_user = SimpleNamespace(is_authenticated=True, pk=uuid4(), _meta=object())

        self.assertTrue(_is_persistable_authenticated_user(model_like_user))
        self.assertFalse(_is_persistable_authenticated_user(SimpleNamespace(is_authenticated=False, pk=uuid4(), _meta=object())))
        self.assertFalse(_is_persistable_authenticated_user(SimpleNamespace(is_authenticated=True, pk=None, _meta=object())))
        self.assertFalse(_is_persistable_authenticated_user(SimpleNamespace(is_authenticated=True, pk=uuid4())))

    @override_settings(LLM_GENERATE_RATE_LIMIT_PER_MINUTE="not-a-number")
    def test_resolve_llm_generate_rate_limit_uses_default_for_invalid_config(self):
        self.assertEqual(_resolve_llm_generate_rate_limit_per_minute(default=17), 17)

    @override_settings(LLM_GENERATE_IDEMPOTENCY_TTL_SECONDS="not-a-number")
    def test_resolve_llm_generate_idempotency_ttl_uses_default_for_invalid_config(self):
        self.assertEqual(_resolve_llm_generate_idempotency_ttl_seconds(default=31), 31)

    @override_settings(LLM_GENERATE_IDEMPOTENCY_TTL_SECONDS="45")
    def test_resolve_llm_generate_idempotency_ttl_uses_positive_config(self):
        self.assertEqual(_resolve_llm_generate_idempotency_ttl_seconds(default=31), 45)

    def test_llm_generate_rate_limit_key_partitions(self):
        user_id = uuid4()

        self.assertEqual(
            _llm_generate_rate_limit_key(
                SimpleNamespace(
                    user=SimpleNamespace(is_authenticated=True, id=user_id),
                    META={},
                )
            ),
            f"user:{user_id}",
        )
        self.assertEqual(
            _llm_generate_rate_limit_key(
                SimpleNamespace(
                    user=SimpleNamespace(is_authenticated=False, id=None),
                    META={"HTTP_X_FORWARDED_FOR": "203.0.113.10, 198.51.100.9"},
                )
            ),
            "ip:203.0.113.10",
        )
        self.assertEqual(
            _llm_generate_rate_limit_key(
                SimpleNamespace(
                    user=SimpleNamespace(is_authenticated=False, id=None),
                    META={"REMOTE_ADDR": "198.51.100.7"},
                )
            ),
            "ip:198.51.100.7",
        )

    def test_extract_llm_generate_idempotency_key_partitions(self):
        self.assertEqual(
            _extract_llm_generate_idempotency_key(
                SimpleNamespace(
                    headers={"Idempotency-Key": "  header-key  "},
                    META={"HTTP_IDEMPOTENCY_KEY": "meta-key"},
                )
            ),
            "header-key",
        )
        self.assertEqual(
            _extract_llm_generate_idempotency_key(
                SimpleNamespace(headers={}, META={"HTTP_IDEMPOTENCY_KEY": " meta-key "})
            ),
            "meta-key",
        )
        self.assertIsNone(
            _extract_llm_generate_idempotency_key(
                SimpleNamespace(headers={}, META={"HTTP_IDEMPOTENCY_KEY": "   "})
            )
        )
        self.assertIsNone(
            _extract_llm_generate_idempotency_key(
                SimpleNamespace(headers={"Idempotency-Key": 123}, META={})
            )
        )

    def test_resolve_cached_llm_generate_idempotency_response_partitions(self):
        request_hash = "hash-a"

        self.assertIsNone(_resolve_cached_llm_generate_idempotency_response(None, request_hash))
        self.assertIsNone(
            _resolve_cached_llm_generate_idempotency_response(
                {"state": "unknown", "request_hash": request_hash},
                request_hash,
            )
        )
        self.assertIsNone(
            _resolve_cached_llm_generate_idempotency_response(
                {"state": "completed", "request_hash": request_hash, "status_code": "200"},
                request_hash,
            )
        )

        reused_response = _resolve_cached_llm_generate_idempotency_response(
            {"request_hash": "hash-b"},
            request_hash,
        )
        self.assertEqual(reused_response.status_code, 409)
        self.assertEqual(reused_response.data["code"], "llm_generate_idempotency_key_reused")

        in_progress_response = _resolve_cached_llm_generate_idempotency_response(
            {"state": "in_progress", "request_hash": request_hash},
            request_hash,
        )
        self.assertEqual(in_progress_response.status_code, 409)
        self.assertEqual(in_progress_response.data["code"], "llm_generate_idempotency_in_progress")

        completed_response = _resolve_cached_llm_generate_idempotency_response(
            {
                "state": "completed",
                "request_hash": request_hash,
                "status_code": 201,
                "data": {"ok": True},
            },
            request_hash,
        )
        self.assertEqual(completed_response.status_code, 201)
        self.assertEqual(completed_response.data, {"ok": True})
        self.assertEqual(completed_response["X-Idempotency-Replayed"], "true")

    def test_build_llm_generate_idempotency_response_uses_custom_status(self):
        response = _build_llm_generate_idempotency_response(
            "Busy",
            "busy",
            status_code=425,
        )

        self.assertEqual(response.status_code, 425)
        self.assertEqual(response.data, {"detail": "Busy", "code": "busy"})

    def test_run_llm_generate_with_idempotency_without_key_executes_workflow(self):
        execute_workflow = Mock(return_value=Response({"ok": True}, status=200))
        response = _run_llm_generate_with_idempotency(
            request=SimpleNamespace(
                user=self._build_verified_user(user_id=uuid4()),
                headers={},
                META={},
            ),
            validated_data={"input_json": {"sheet": "Sheet1"}},
            execute_workflow=execute_workflow,
        )

        self.assertEqual(response.status_code, 200)
        execute_workflow.assert_called_once()

    def test_run_llm_generate_with_idempotency_deletes_lock_on_server_error(self):
        request = SimpleNamespace(
            user=self._build_verified_user(user_id=uuid4()),
            headers={"Idempotency-Key": "abc-123"},
            META={},
        )
        response = _run_llm_generate_with_idempotency(
            request=request,
            validated_data={"input_json": {"sheet": "Sheet1"}},
            execute_workflow=Mock(return_value=Response({"detail": "fail"}, status=503)),
        )

        self.assertEqual(response.status_code, 503)
        cache_key = _build_llm_generate_idempotency_cache_key(request.user, "abc-123")
        self.assertIsNone(cache.get(cache_key))

    def test_run_llm_generate_with_idempotency_returns_conflict_when_lock_missing_and_cache_empty(self):
        request = SimpleNamespace(
            user=self._build_verified_user(user_id=uuid4()),
            headers={"Idempotency-Key": "abc-123"},
            META={},
        )
        with patch("llm.views.cache.add", return_value=False), patch(
            "llm.views.cache.get",
            return_value=None,
        ):
            response = _run_llm_generate_with_idempotency(
                request=request,
                validated_data={"input_json": {"sheet": "Sheet1"}},
                execute_workflow=Mock(return_value=Response({"ok": True}, status=200)),
            )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], "llm_generate_idempotency_in_progress")

    def test_run_llm_generate_with_idempotency_replays_cache_when_lock_missing(self):
        request = SimpleNamespace(
            user=self._build_verified_user(user_id=uuid4()),
            headers={"Idempotency-Key": "abc-123"},
            META={},
        )
        validated_data = {"input_json": {"sheet": "Sheet1"}}
        request_hash = _compute_llm_generate_idempotency_request_hash(validated_data)
        execute_workflow = Mock(return_value=Response({"ok": False}, status=200))

        with patch("llm.views.cache.add", return_value=False), patch(
            "llm.views.cache.get",
            return_value={
                "state": "completed",
                "request_hash": request_hash,
                "status_code": 200,
                "data": {"ok": True},
            },
        ):
            response = _run_llm_generate_with_idempotency(
                request=request,
                validated_data=validated_data,
                execute_workflow=execute_workflow,
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {"ok": True})
        execute_workflow.assert_not_called()

    def test_run_llm_generate_with_idempotency_deletes_lock_when_workflow_raises(self):
        request = SimpleNamespace(
            user=self._build_verified_user(user_id=uuid4()),
            headers={"Idempotency-Key": "abc-123"},
            META={},
        )
        execute_workflow = Mock(side_effect=RuntimeError("boom"))

        with self.assertRaises(RuntimeError):
            _run_llm_generate_with_idempotency(
                request=request,
                validated_data={"input_json": {"sheet": "Sheet1"}},
                execute_workflow=execute_workflow,
            )

        cache_key = _build_llm_generate_idempotency_cache_key(request.user, "abc-123")
        self.assertIsNone(cache.get(cache_key))

    def test_parse_send_message_json_result_handles_markdown_fences(self):
        self.assertEqual(
            _parse_send_message_json_result('```json\n{"reply":"Hi","title":"T"}\n```'),
            {"reply": "Hi", "title": "T"},
        )
        self.assertEqual(
            _parse_send_message_json_result('```\n{"reply":"Hi","title":"T"}\n```'),
            {"reply": "Hi", "title": "T"},
        )

    @patch("llm.views.generate_chat_response")
    def test_generate_reply_and_title_parses_valid_json_response(self, mock_generate):
        mock_generate.return_value = '{"reply":"Hi","title":"Quick Title"}'

        reply, title = _generate_reply_and_title_for_new_session([], "Hello")

        self.assertEqual(reply, "Hi")
        self.assertEqual(title, "Quick Title")

    @patch("llm.views.generate_session_title_from_message", return_value="Fallback Title")
    @patch("llm.views.generate_chat_response")
    def test_generate_reply_and_title_uses_default_reply_when_fallback_blank(
        self,
        mock_generate,
        _mock_title,
    ):
        mock_generate.return_value = "   "

        reply, title = _generate_reply_and_title_for_new_session([], "Hello")

        self.assertEqual(reply, "Sorry, I couldn't generate a response.")
        self.assertEqual(title, "Fallback Title")

    def test_resolve_send_message_session_context_partitions(self):
        self.assertEqual(_resolve_send_message_session_context(object(), None), (None, []))

        with patch("llm.views.get_session_for_user", return_value=None):
            self.assertEqual(
                _resolve_send_message_session_context(object(), "missing-session"),
                (None, None),
            )

        session = SimpleNamespace(messages=Mock())
        with patch("llm.views.get_session_for_user", return_value=session), patch(
            "llm.views._build_session_message_history",
            return_value=[{"role": "user", "content": "Hi"}],
        ):
            self.assertEqual(
                _resolve_send_message_session_context(object(), "session-1"),
                (session, [{"role": "user", "content": "Hi"}]),
            )

    @patch("llm.views.generate_chat_response", return_value="Reply")
    @patch("llm.views._inject_file_context_if_available")
    @patch("llm.views.build_history_with_summary")
    def test_generate_send_message_reply_and_title_for_existing_session(
        self,
        mock_build_history,
        mock_inject_context,
        mock_generate,
    ):
        session = SimpleNamespace(id="session-1")
        mock_build_history.return_value = [{"role": "user", "content": "Hi"}]
        mock_inject_context.return_value = [{"role": "user", "content": "Hi"}]

        reply, title = _generate_send_message_reply_and_title(
            session,
            [{"role": "user", "content": "Hi"}],
            "Hi",
        )

        self.assertEqual((reply, title), ("Reply", "New Chat"))
        mock_build_history.assert_called_once()
        mock_inject_context.assert_called_once()
        mock_generate.assert_called_once()

    @patch("llm.views._generate_reply_and_title_for_new_session", return_value=("Reply", "Title"))
    @patch("llm.views._inject_file_context_if_available")
    def test_generate_send_message_reply_and_title_for_new_session(
        self,
        mock_inject_context,
        mock_generate_reply_title,
    ):
        mock_inject_context.return_value = [{"role": "user", "content": "Hi"}]

        reply, title = _generate_send_message_reply_and_title(
            None,
            [{"role": "user", "content": "Hi"}],
            "Hi",
        )

        self.assertEqual((reply, title), ("Reply", "Title"))
        mock_generate_reply_title.assert_called_once()

    @patch("llm.views.generate_conversion_reasoning_response")
    @patch("llm.views.build_llm_reasoning_service")
    def test_generate_optional_reasoning_success_and_skip_partitions(
        self,
        mock_build_service,
        mock_generate_reasoning,
    ):
        mock_generate_reasoning.return_value = {"thinking_log": "ok"}

        self.assertIsNone(_generate_optional_reasoning(False, {}, {}))
        self.assertEqual(
            _generate_optional_reasoning(True, {"filename": "report.pdf"}, {"rows": []}),
            {"thinking_log": "ok"},
        )
        mock_build_service.assert_called_once()
        mock_generate_reasoning.assert_called_once()

    @patch("llm.views.logger")
    @patch("llm.views.generate_conversion_reasoning_response")
    @patch("llm.views.build_llm_reasoning_service")
    def test_generate_optional_reasoning_swallows_expected_and_unexpected_errors(
        self,
        _mock_build_service,
        mock_generate_reasoning,
        mock_logger,
    ):
        for exception, expected_message in (
            (OpenAIServiceError("bad"), "Automatic reasoning failed while handling llm_generate request."),
            (RuntimeError("boom"), "Unexpected error while generating automatic reasoning."),
        ):
            with self.subTest(exception=exception.__class__.__name__):
                mock_generate_reasoning.side_effect = exception
                self.assertIsNone(_generate_optional_reasoning(True, {}, {}))
                mock_logger.exception.assert_called_with(expected_message)

    def test_generate_output_json_returns_generated_output_when_successful(self):
        generation_service = Mock()
        generation_service.generate.return_value = {"result": "ok"}

        output_json, error_response = _generate_output_json(
            llm_generation_service=generation_service,
            input_json={"sheet": "Sheet1"},
            custom_schema_id=None,
            chat_context={"chat": "ctx"},
        )

        self.assertEqual(output_json, {"result": "ok"})
        self.assertIsNone(error_response)
        generation_service.generate.assert_called_once_with(
            input_json={"sheet": "Sheet1"},
            custom_schema_id=None,
            chat_context={"chat": "ctx"},
        )

    def test_generate_output_json_maps_known_provider_errors(self):
        cases = [
            (CustomSchemaNotFoundError(), 404),
            (OpenAIConfigurationError("misconfigured"), 503),
            (OpenAIUpstreamError("upstream", status_code=429), 429),
            (OpenAIServiceError("service error"), 502),
        ]

        for exception, expected_status in cases:
            with self.subTest(expected_status=expected_status):
                generation_service = Mock()
                generation_service.generate.side_effect = exception

                output_json, error_response = _generate_output_json(
                    llm_generation_service=generation_service,
                    input_json={"sheet": "Sheet1"},
                    custom_schema_id=None,
                )

                self.assertIsNone(output_json)
                self.assertIsInstance(error_response, Response)
                self.assertEqual(error_response.status_code, expected_status)

    def test_generate_output_json_returns_validation_error_for_invalid_input_payload(self):
        generation_service = Mock()
        generation_service.generate.side_effect = ValueError("bad payload")

        output_json, error_response = _generate_output_json(
            llm_generation_service=generation_service,
            input_json={"sheet": "Sheet1"},
            custom_schema_id=None,
        )

        self.assertIsNone(output_json)
        self.assertIsInstance(error_response, Response)
        self.assertEqual(error_response.status_code, 400)
        self.assertIn("input_json", error_response.data["errors"])

    def test_generate_output_json_returns_500_for_unexpected_exception(self):
        generation_service = Mock()
        generation_service.generate.side_effect = RuntimeError("unexpected")

        output_json, error_response = _generate_output_json(
            llm_generation_service=generation_service,
            input_json={"sheet": "Sheet1"},
            custom_schema_id=None,
        )

        self.assertIsNone(output_json)
        self.assertIsInstance(error_response, Response)
        self.assertEqual(error_response.status_code, 500)

    def test_thinking_log_response_and_parser_helpers(self):
        self.assertEqual(_thinking_log_not_found_response().status_code, 404)
        self.assertEqual(_invalid_thinking_log_pagination_response().status_code, 400)
        self.assertEqual(
            _invalid_thinking_log_identifier_response("session_id").data["errors"],
            {"session_id": ["Invalid thinking log identifier."]},
        )
        self.assertEqual(_parse_thinking_log_positive_int(None, default=2), 2)
        self.assertEqual(_parse_thinking_log_positive_int("3", default=2), 3)
        with self.assertRaises(ValueError):
            _parse_thinking_log_positive_int("0", default=2)
        self.assertEqual(_parse_thinking_log_page_size("5"), 5)
        with self.assertRaises(ValueError):
            _parse_thinking_log_page_size("101")

        output_id = uuid4()
        self.assertEqual(_parse_thinking_log_identifier(str(output_id), "request_id"), output_id)
        self.assertIsNone(_parse_thinking_log_identifier("   ", "request_id"))
        with self.assertRaises(ValueError):
            _parse_thinking_log_identifier("not-a-uuid", "request_id")

    def test_resolve_generate_session_partitions(self):
        user = self._build_verified_user(user_id=uuid4())
        self.assertEqual(_resolve_generate_session(user, None), (None, None))
        self.assertEqual(
            _resolve_generate_session(SimpleNamespace(is_authenticated=False), uuid4()),
            (None, None),
        )

        with patch("llm.views.get_session_for_user", return_value=None):
            session, error_response = _resolve_generate_session(user, uuid4())
            self.assertIsNone(session)
            self.assertEqual(error_response.status_code, 404)

        owned_session = SimpleNamespace(id=uuid4())
        with patch("llm.views.get_session_for_user", return_value=owned_session):
            self.assertEqual(
                _resolve_generate_session(user, owned_session.id),
                (owned_session, None),
            )

    def test_resolve_message_target_output_partitions(self):
        user = self._build_verified_user(user_id=uuid4())
        self.assertEqual(_resolve_message_target_output(user, None, None), (None, None))

        with patch("llm.views.get_generated_output_for_user", return_value=None):
            target_output, error_response = _resolve_message_target_output(user, None, uuid4())
            self.assertIsNone(target_output)
            self.assertEqual(error_response.status_code, 404)

        requested_session = SimpleNamespace(id=uuid4())
        target_output = SimpleNamespace(id=uuid4(), session_id=uuid4())
        with patch("llm.views.get_generated_output_for_user", return_value=target_output):
            resolved_output, error_response = _resolve_message_target_output(
                user,
                requested_session,
                target_output.id,
            )
            self.assertIsNone(resolved_output)
            self.assertEqual(error_response.status_code, 400)

        target_output = SimpleNamespace(id=uuid4(), session_id=requested_session.id)
        with patch("llm.views.get_generated_output_for_user", return_value=target_output):
            self.assertEqual(
                _resolve_message_target_output(user, requested_session, target_output.id),
                (target_output, None),
            )

    def test_resolve_generate_source_message_partitions(self):
        user = self._build_verified_user(user_id=uuid4())
        session = SimpleNamespace(id=uuid4())
        self.assertEqual(_resolve_generate_source_message(user, session, None), (None, session, None))

        with patch("llm.views.get_chat_message_for_user", return_value=None):
            source_message, resolved_session, error_response = _resolve_generate_source_message(
                user,
                session,
                uuid4(),
            )
            self.assertIsNone(source_message)
            self.assertEqual(resolved_session, session)
            self.assertEqual(error_response.status_code, 404)

        source_message = SimpleNamespace(id=uuid4(), session_id=uuid4(), session=SimpleNamespace(id=uuid4()))
        with patch("llm.views.get_chat_message_for_user", return_value=source_message):
            resolved_message, resolved_session, error_response = _resolve_generate_source_message(
                user,
                session,
                source_message.id,
            )
            self.assertIsNone(resolved_message)
            self.assertEqual(resolved_session, session)
            self.assertEqual(error_response.status_code, 400)

        source_message = SimpleNamespace(id=uuid4(), session_id=session.id, session=session)
        with patch("llm.views.get_chat_message_for_user", return_value=source_message):
            self.assertEqual(
                _resolve_generate_source_message(user, session, source_message.id),
                (source_message, session, None),
            )

    def test_persist_generate_output_returns_none_for_non_persistable_user(self):
        self.assertEqual(
            _persist_generate_output_for_authenticated_user(
                SimpleNamespace(is_authenticated=True, pk=None),
                None,
                {},
                "",
                None,
                {},
            ),
            (None, None, None, None),
        )

    @patch("llm.views.LlmGenerateResponseSerializer")
    def test_build_generate_success_response_returns_502_when_serializer_invalid(
        self,
        mock_serializer_class,
    ):
        mock_serializer = mock_serializer_class.return_value
        mock_serializer.is_valid.return_value = False

        response = _build_generate_success_response(
            {"output_json": {"ok": True}, "reasoning": None},
            None,
            None,
            None,
        )

        self.assertEqual(response.status_code, 502)

    def test_build_refinement_config_maps_payload(self):
        config = _build_refinement_config(
            {"max_iterations": "2", "early_exit_on_valid": False}
        )

        self.assertTrue(config.enabled)
        self.assertEqual(config.max_iterations, 2)
        self.assertFalse(config.early_exit_on_valid)

    @patch("llm.views._generate_optional_reasoning", return_value={"thinking_log": "ok"})
    def test_run_basic_generation_returns_sanitized_output(self, mock_generate_reasoning):
        generation_service = Mock()
        generation_service.generate.return_value = {
            "headers": ["A"],
            "final_answer": "remove",
        }

        result = _run_basic_generation(
            generation_service,
            {"sheet": "Sheet1"},
            custom_schema_id="schema-1",
            include_reasoning=True,
            chat_context="context",
        )

        self.assertEqual(result["output_json"], {"headers": ["A"]})
        self.assertEqual(result["reasoning_response"], {"thinking_log": "ok"})
        generation_service.generate.assert_called_once_with(
            input_json={"sheet": "Sheet1"},
            custom_schema_id="schema-1",
            chat_context="context",
        )
        mock_generate_reasoning.assert_called_once()

    @patch("llm.views.logger")
    def test_llm_generate_error_response_partitions(self, mock_logger):
        cases = (
            (CustomSchemaNotFoundError(), 404),
            (OpenAIConfigurationError("missing"), 503),
            (OpenAIUpstreamError("rate", status_code=429), 429),
            (OpenAIServiceError("bad"), 502),
            (ValueError("bad input"), 400),
            (RuntimeError("boom"), 500),
        )

        for exception, expected_status in cases:
            with self.subTest(exception=exception.__class__.__name__):
                self.assertEqual(
                    _llm_generate_error_response(exception).status_code,
                    expected_status,
                )
        self.assertTrue(mock_logger.exception.called)

    def test_build_llm_generate_response_payload_partitions(self):
        self.assertEqual(
            _build_llm_generate_response_payload(
                {
                    "refinement_enabled": False,
                    "output_json": {"ok": True},
                    "reasoning_response": None,
                }
            ),
            {"output_json": {"ok": True}, "reasoning": None},
        )

        result = _build_llm_generate_response_payload(
            {
                "refinement_enabled": True,
                "output_json": {"ok": True},
                "reasoning_response": {"thinking_log": "ok"},
                "validated_json": {"ok": True},
                "raw_json": {"raw": True},
                "validation_log": {"verdict": "valid"},
                "refinement_meta": {"iterations_run": 1},
            }
        )
        self.assertEqual(result["validated_json"], {"ok": True})
        self.assertNotIn("raw_json", result)

    @override_settings(LLM_EXPOSE_VALIDATION_LOG=True)
    def test_build_llm_generate_response_payload_exposes_debug_fields_when_enabled(self):
        result = _build_llm_generate_response_payload(
            {
                "refinement_enabled": True,
                "output_json": {"ok": True},
                "reasoning_response": None,
                "validated_json": {"ok": True},
                "raw_json": {"raw": True},
                "validation_log": {"verdict": "valid"},
                "refinement_meta": {"iterations_run": 1},
            }
        )

        self.assertEqual(result["raw_json"], {"raw": True})
        self.assertEqual(result["validation_log"], {"verdict": "valid"})
        self.assertEqual(result["refinement_meta"], {"iterations_run": 1})

    @patch("llm.views._run_refinement_generation", return_value={"refinement_enabled": True})
    @patch("llm.views.build_llm_generation_service")
    def test_execute_llm_generate_flow_uses_refinement_path(
        self,
        mock_build_service,
        mock_run_refinement,
    ):
        result = _execute_llm_generate_flow(
            {
                "input_json": {"sheet": "Sheet1"},
                "include_reasoning": False,
                "refinement": {"enabled": True},
            },
            user=self._build_verified_user(),
            chat_context="context",
        )

        self.assertEqual(result, {"refinement_enabled": True})
        mock_run_refinement.assert_called_once()
        mock_build_service.assert_called_once()

    @patch("llm.views._run_basic_generation", side_effect=OpenAIServiceError("bad"))
    @patch("llm.views.build_llm_generation_service")
    def test_execute_llm_generate_flow_maps_generation_errors(
        self,
        _mock_build_service,
        _mock_run_basic_generation,
    ):
        response = _execute_llm_generate_flow(
            {"input_json": {"sheet": "Sheet1"}, "refinement": {"enabled": False}},
            user=self._build_verified_user(),
        )

        self.assertEqual(response.status_code, 502)

    @patch("llm.views.extract_original_name", return_value="")
    def test_build_generate_bootstrap_message_returns_title_when_filename_missing(self, _mock_extract_original_name):
        result = _build_generate_bootstrap_message({}, "Custom title")

        self.assertEqual(result, "Custom title")

    @patch("llm.views.extract_original_name", return_value="")
    def test_build_generate_bootstrap_message_returns_default_when_filename_and_title_missing(self, _mock_extract_original_name):
        result = _build_generate_bootstrap_message({}, "")

        self.assertEqual(result, "Uploaded file for conversion")

    def test_build_generate_bootstrap_message_falls_back_to_title_without_filename(self):
        result = _build_generate_bootstrap_message({}, "Convert generated-output")

        self.assertEqual(result, "Convert generated-output")

    def test_build_generate_bootstrap_message_uses_generic_fallback_when_blank(self):
        result = _build_generate_bootstrap_message({}, "")

        self.assertEqual(result, "Uploaded file for conversion")

    def test_build_generate_bootstrap_message_handles_non_object_input(self):
        result = _build_generate_bootstrap_message([], "Convert generated-output")

        self.assertEqual(result, "Convert generated-output")

    @patch("llm.views.generate_session_title_from_message")
    @patch("llm.views.generate_chat_response")
    def test_generate_reply_and_title_fallback_reuses_first_response_when_json_parse_fails(
        self,
        mock_generate,
        mock_generate_title,
    ):
        mock_generate.return_value = "Balasan aman"
        mock_generate_title.return_value = "New Chat"

        reply, title = _generate_reply_and_title_for_new_session(
            history=[{"role": "user", "content": "Halo"}],
            message="Halo",
        )

        self.assertEqual(reply, "Balasan aman")
        self.assertEqual(title, "New Chat")
        mock_generate.assert_called_once()
        mock_generate_title.assert_called_once_with("Halo")

    def test_run_llm_generate_with_idempotency_replays_cached_success_response(self):
        request = SimpleNamespace(
            user=self._build_verified_user(user_id=uuid4()),
            headers={"Idempotency-Key": "abc-123"},
            META={"HTTP_IDEMPOTENCY_KEY": "abc-123"},
        )
        validated_data = {"input_json": {"sheet": "Sheet1"}, "include_reasoning": False}
        execute_workflow = Mock(
            return_value=Response(
                {"output_json": {"status": "ok"}, "reasoning": None},
                status=200,
            )
        )

        first_response = _run_llm_generate_with_idempotency(
            request=request,
            validated_data=validated_data,
            execute_workflow=execute_workflow,
        )
        second_response = _run_llm_generate_with_idempotency(
            request=request,
            validated_data=validated_data,
            execute_workflow=execute_workflow,
        )

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(second_response.data["output_json"], {"status": "ok"})
        self.assertEqual(execute_workflow.call_count, 1)

    def test_run_llm_generate_with_idempotency_rejects_same_key_for_different_payload(self):
        request = SimpleNamespace(
            user=self._build_verified_user(user_id=uuid4()),
            headers={"Idempotency-Key": "abc-123"},
            META={"HTTP_IDEMPOTENCY_KEY": "abc-123"},
        )
        execute_workflow = Mock(
            return_value=Response(
                {"output_json": {"status": "ok"}, "reasoning": None},
                status=200,
            )
        )

        first_response = _run_llm_generate_with_idempotency(
            request=request,
            validated_data={"input_json": {"sheet": "Sheet1"}, "include_reasoning": False},
            execute_workflow=execute_workflow,
        )
        conflict_response = _run_llm_generate_with_idempotency(
            request=request,
            validated_data={"input_json": {"sheet": "Sheet2"}, "include_reasoning": False},
            execute_workflow=execute_workflow,
        )

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(conflict_response.status_code, 409)
        self.assertEqual(
            conflict_response.data["code"],
            "llm_generate_idempotency_key_reused",
        )
        self.assertEqual(execute_workflow.call_count, 1)

    def test_run_llm_generate_with_idempotency_returns_in_progress_conflict(self):
        request = SimpleNamespace(
            user=self._build_verified_user(user_id=uuid4()),
            headers={"Idempotency-Key": "abc-123"},
            META={"HTTP_IDEMPOTENCY_KEY": "abc-123"},
        )
        validated_data = {"input_json": {"sheet": "Sheet1"}, "include_reasoning": False}
        request_hash = _compute_llm_generate_idempotency_request_hash(validated_data)
        cache_key = _build_llm_generate_idempotency_cache_key(
            request.user,
            "abc-123",
        )
        cache.set(
            cache_key,
            {"state": "in_progress", "request_hash": request_hash},
            timeout=60,
        )
        execute_workflow = Mock(
            return_value=Response(
                {"output_json": {"status": "ok"}, "reasoning": None},
                status=200,
            )
        )

        conflict_response = _run_llm_generate_with_idempotency(
            request=request,
            validated_data=validated_data,
            execute_workflow=execute_workflow,
        )

        self.assertEqual(conflict_response.status_code, 409)
        self.assertEqual(
            conflict_response.data["code"],
            "llm_generate_idempotency_in_progress",
        )
        execute_workflow.assert_not_called()

    def test_build_table_context_lines_skips_headers_when_empty_and_includes_row_samples(self):
        lines = _build_table_context_lines(
            {
                "table_name": "SheetA",
                "headers": [],
                "rows": [
                    {"unit": "ICU", "value": 100, "meta": "x"},
                    ["ignored-non-dict-row"],
                ],
            }
        )

        self.assertEqual(lines[0], "Table 'SheetA': 0 columns, 2 rows")
        self.assertTrue(any(line.startswith("  Row 1: ") for line in lines))
        self.assertFalse(any(line.startswith("  Headers: ") for line in lines))

    def test_build_compact_file_context_handles_non_object_sections_and_non_dict_tables(self):
        context = _build_compact_file_context(
            {
                "document_info": "invalid-doc-info",
                "summary": {},
                "content_data": [
                    "non-dict-table-entry",
                    {
                        "table_name": "Summary",
                        "headers": ["unit"],
                        "rows": [{"unit": "ER"}],
                    },
                ],
            }
        )

        self.assertIn("[CONVERTED_FILE_CONTEXT]", context)
        self.assertIn("Table 'Summary': 1 columns, 1 rows", context)
        self.assertNotIn("File:", context)
        self.assertNotIn("Summary:", context)

    def test_build_compact_file_context_handles_non_list_content_data(self):
        context = _build_compact_file_context(
            {
                "document_info": {"filename": "report.xlsx", "source_type": "Excel"},
                "summary": {"total_tables": 1},
                "content_data": "not-a-list",
            }
        )

        self.assertIn("File: report.xlsx (Excel)", context)
        self.assertIn("Summary: total_tables=1", context)
        self.assertNotIn("Table '", context)

    def test_inject_file_context_returns_history_when_export_payload_cannot_be_built(self):
        history = [{"role": "user", "content": "Halo"}]
        last_output = SimpleNamespace(export_output_json={}, output_json={})
        session = SimpleNamespace(
            generated_outputs=SimpleNamespace(
                order_by=lambda *_args, **_kwargs: SimpleNamespace(first=lambda: last_output)
            )
        )

        result = _inject_file_context_if_available(session, history)

        self.assertEqual(result, history)
        self.assertIs(result, history)

    def test_extract_follow_up_prompt_isp_partitions(self):
        scenarios = (
            {
                "name": "non_object_payload",
                "payload": ["not-an-object"],
                "expected": "",
            },
            {
                "name": "missing_user_prompt",
                "payload": {"filename": "invoice.pdf"},
                "expected": "",
            },
            {
                "name": "non_string_user_prompt",
                "payload": {"user_prompt": 123},
                "expected": "",
            },
            {
                "name": "whitespace_user_prompt",
                "payload": {"user_prompt": "   "},
                "expected": "",
            },
            {
                "name": "trimmed_user_prompt",
                "payload": {"user_prompt": "  refine output  "},
                "expected": "refine output",
            },
        )

        for scenario in scenarios:
            with self.subTest(scenario=scenario["name"]):
                self.assertEqual(
                    _extract_follow_up_prompt(scenario["payload"]),
                    scenario["expected"],
                )

    def test_hydrate_previous_output_from_target_does_not_override_existing_previous_output(self):
        existing_previous_output = {"content_data": [{"rows": [{"status": "paid"}]}]}
        input_json = {
            "filename": "invoice.pdf",
            "previous_output": existing_previous_output,
        }
        target_output = SimpleNamespace(output_json={"content_data": [{"rows": [{"status": "all"}]}]})

        hydrated = _hydrate_previous_output_from_target(input_json, target_output)

        self.assertIs(hydrated, input_json)
        self.assertEqual(hydrated["previous_output"], existing_previous_output)

    def test_hydrate_previous_output_from_target_handles_non_dict_or_missing_target(self):
        list_payload = ["not-a-dict"]
        target_output = SimpleNamespace(output_json={"rows": [["A"]]})

        hydrated_list_payload = _hydrate_previous_output_from_target(list_payload, target_output)
        self.assertIs(hydrated_list_payload, list_payload)

        dict_payload = {"filename": "invoice.pdf"}
        hydrated_without_target = _hydrate_previous_output_from_target(dict_payload, None)
        self.assertIs(hydrated_without_target, dict_payload)

    def test_estimate_payload_size_bytes_returns_zero_for_non_serializable_payload(self):
        class _NonSerializable:
            pass

        self.assertEqual(_estimate_payload_size_bytes(_NonSerializable()), 0)

    @patch("llm.views.create_artifact_history")
    @patch("llm.views.transaction.on_commit")
    def test_schedule_artifact_history_creation_registers_on_commit_callback(
        self,
        mock_on_commit,
        mock_create_artifact_history,
    ):
        request_user = self._build_verified_user(user_id=uuid4())
        callbacks = []
        mock_on_commit.side_effect = callbacks.append

        _schedule_artifact_history_creation(
            user=request_user,
            input_json={"filename": "invoice.pdf"},
            output_json={"headers": ["A"], "rows": [["1"]]},
            session_id=uuid4(),
        )

        mock_on_commit.assert_called_once()
        mock_create_artifact_history.assert_not_called()
        self.assertEqual(len(callbacks), 1)

        callbacks[0]()

        mock_create_artifact_history.assert_called_once()

    @patch("llm.views.logger")
    @patch("llm.views.create_artifact_history")
    @patch("llm.views.transaction.on_commit")
    def test_schedule_artifact_history_creation_swallows_callback_errors(
        self,
        mock_on_commit,
        mock_create_artifact_history,
        mock_logger,
    ):
        request_user = self._build_verified_user(user_id=uuid4())
        callbacks = []
        mock_on_commit.side_effect = callbacks.append
        mock_create_artifact_history.side_effect = RuntimeError("history failure")

        _schedule_artifact_history_creation(
            user=request_user,
            input_json={"filename": "invoice.pdf"},
            output_json={"headers": ["A"], "rows": [["1"]]},
            session_id=uuid4(),
        )

        self.assertEqual(len(callbacks), 1)
        callbacks[0]()

        mock_logger.exception.assert_called_once_with(
            "Unexpected error while creating artifact history after llm_generate persistence."
        )

    def test_hydrate_previous_output_keeps_existing_previous_output(self):
        existing_previous_output = {"content_data": [{"rows": [{"status": "paid"}]}]}
        payload = {
            "filename": "invoice.pdf",
            "previous_output": existing_previous_output,
            "user_prompt": "Refine paid rows only",
        }
        target_output = SimpleNamespace(output_json={"content_data": [{"rows": [{"status": "all"}]}]})

        hydrated_payload = _hydrate_previous_output_from_target(payload, target_output)

        self.assertIs(hydrated_payload, payload)
        self.assertEqual(hydrated_payload["previous_output"], existing_previous_output)

    @patch("llm.views._build_chat_context_from_session")
    @patch("llm.views._resolve_message_target_output")
    @patch("llm.views._resolve_generate_source_message")
    @patch("llm.views._resolve_generate_session")
    def test_workflow_resolve_context_uses_target_output_session_when_session_not_provided(
        self,
        mock_resolve_generate_session,
        mock_resolve_generate_source_message,
        mock_resolve_message_target_output,
        mock_build_chat_context_from_session,
    ):
        request = SimpleNamespace(user=SimpleNamespace(is_authenticated=False))
        target_session = SimpleNamespace(id=uuid4())
        target_output = SimpleNamespace(
            id=uuid4(),
            session=target_session,
            output_json={"content_data": [{"rows": [{"status": "all"}]}]},
        )
        validated_data = {
            "input_json": {
                "filename": "invoice.pdf",
                "user_prompt": "Hanya tampilkan status paid.",
            },
            "target_output_id": str(target_output.id),
        }
        mock_resolve_generate_session.return_value = (None, None)
        mock_resolve_generate_source_message.return_value = (None, None, None)
        mock_resolve_message_target_output.return_value = (target_output, None)
        mock_build_chat_context_from_session.return_value = "USER: refine status paid only"

        workflow = _LlmGenerateWorkflow(request, validated_data)
        error_response = workflow._resolve_context()

        self.assertIsNone(error_response)
        self.assertIs(workflow.runtime.session, target_session)
        self.assertEqual(
            workflow.runtime.input_json["previous_output"],
            target_output.output_json,
        )
        self.assertEqual(workflow.runtime.chat_context, "USER: refine status paid only")

    def test_sanitize_output_json_removes_reasoning_meta_keys_from_object(self):
        sanitized = _sanitize_output_json(
            {
                "headers": ["A", "B"],
                "rows": [["1", "2"]],
                "final_answer": "should be removed",
                "reasoning_steps": ["should be removed"],
                "thinking_log": "should be removed",
            }
        )

        self.assertEqual(
            sanitized,
            {
                "headers": ["A", "B"],
                "rows": [["1", "2"]],
            },
        )

    def test_sanitize_output_json_keeps_non_object_payload_unchanged(self):
        payload = [{"row": 1}]
        sanitized = _sanitize_output_json(payload)

        self.assertEqual(sanitized, payload)

    @patch("llm.views.build_llm_generation_service")
    def test_llm_generate_returns_200(self, mock_build_service):
        mock_service = mock_build_service.return_value
        mock_service.generate.return_value = {"status": "ok"}
        client = APIClient()

        payload = {
            "input_json": {"sheet": "Sheet1"},
            "refinement": {"enabled": False},
        }
        response = client.post("/llm/generate/", payload, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["output_json"], {"status": "ok"})
        self.assertIsNone(response.data["output_id"])
        self.assertEqual(mock_build_service.call_count, 1)
        self.assertTrue(mock_build_service.call_args[0][0].is_authenticated)
        mock_service.generate.assert_called_once_with(
            input_json={"sheet": "Sheet1"},
            custom_schema_id=None,
            chat_context=None,
        )

    @patch("llm.views.build_llm_generation_service")
    def test_llm_generate_returns_401_for_unauthenticated_user(self, mock_build_service):
        client = self._build_unauthenticated_client()

        response = client.post(
            "/llm/generate/",
            {
                "input_json": {"sheet": "Sheet1"},
                "refinement": {"enabled": False},
            },
            format="json",
        )

        self.assertEqual(response.status_code, 401)
        mock_build_service.assert_not_called()

    @patch("llm.views.build_llm_generation_service")
    def test_llm_generate_returns_403_for_unverified_user(self, mock_build_service):
        client = self._build_verified_client(
            user=self._build_verified_user(status="pending")
        )

        response = client.post(
            "/llm/generate/",
            {
                "input_json": {"sheet": "Sheet1"},
                "refinement": {"enabled": False},
            },
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        mock_build_service.assert_not_called()

    @patch("llm.views.build_llm_generation_service")
    def test_llm_generate_returns_429_when_rate_limit_exceeded(self, mock_build_service):
        mock_service = mock_build_service.return_value
        mock_service.generate.return_value = {"status": "ok"}
        client = self._build_verified_client(
            user=self._build_verified_user(user_id=uuid4())
        )
        payload = {
            "input_json": {"sheet": "Sheet1"},
            "refinement": {"enabled": False},
        }

        for _ in range(LLM_GENERATE_RATE_LIMIT_PER_MINUTE):
            response = client.post("/llm/generate/", payload, format="json")
            self.assertEqual(response.status_code, 200)

        blocked_response = client.post("/llm/generate/", payload, format="json")

        self.assertEqual(blocked_response.status_code, 429)
        self.assertEqual(
            blocked_response.data["detail"],
            "Too many llm_generate requests. Please try again later.",
        )
        self.assertEqual(
            blocked_response.data["code"],
            "llm_generate_rate_limited",
        )
        self.assertEqual(
            blocked_response["X-RateLimit-Limit"],
            str(LLM_GENERATE_RATE_LIMIT_PER_MINUTE),
        )
        self.assertEqual(blocked_response["X-RateLimit-Remaining"], "0")
        self.assertIn("Retry-After", blocked_response)
        self.assertEqual(
            mock_service.generate.call_count,
            LLM_GENERATE_RATE_LIMIT_PER_MINUTE,
        )

    @patch("llm.views.build_llm_reasoning_service")
    @patch("llm.views.build_llm_generation_service")
    def test_llm_generate_calls_reasoning_by_default(
        self,
        mock_build_generation_service,
        mock_build_reasoning_service,
    ):
        mock_generation_service = mock_build_generation_service.return_value
        mock_generation_service.generate.return_value = {"status": "ok"}
        mock_reasoning_service = mock_build_reasoning_service.return_value
        mock_reasoning_service.generate.return_value = {
            "final_answer": "Conversion looks consistent.",
            "reasoning_steps": ["Mapped source fields to normalized headers."],
            "thinking_log": "Checked mapping, ambiguity, and output consistency.",
        }
        client = APIClient()

        response = client.post(
            "/llm/generate/",
            {
                "input_json": {"sheet": "Sheet1"},
                "refinement": {"enabled": False},
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["output_json"], {"status": "ok"})
        self.assertEqual(response.data["reasoning"]["final_answer"], "Conversion looks consistent.")
        mock_reasoning_service.generate.assert_called_once()

    @patch("llm.views.logger")
    @patch("llm.views.build_llm_generation_service")
    def test_llm_generate_logs_phase_telemetry_for_successful_response(
        self,
        mock_build_generation_service,
        mock_logger,
    ):
        mock_generation_service = mock_build_generation_service.return_value
        mock_generation_service.generate.return_value = {"status": "ok"}
        client = APIClient()

        response = client.post(
            "/llm/generate/",
            {"input_json": {"sheet": "Sheet1"}, "include_reasoning": False},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        mock_logger.info.assert_called_once()

        (
            template,
            status,
            total_ms,
            generation_ms,
            reasoning_ms,
            input_size_bytes,
            output_size_bytes,
            include_reasoning,
            session_id,
            chat_id,
            output_id,
            target_output_id,
        ) = mock_logger.info.call_args[0]

        self.assertEqual(
            template,
            "llm_generate telemetry: status=%s total_ms=%s generation_ms=%s reasoning_ms=%s input_size_bytes=%s output_size_bytes=%s include_reasoning=%s session_id=%s chat_id=%s output_id=%s target_output_id=%s",
        )
        self.assertEqual(status, "success")
        self.assertIsInstance(total_ms, int)
        self.assertIsInstance(generation_ms, int)
        self.assertIsInstance(reasoning_ms, int)
        self.assertIsInstance(input_size_bytes, int)
        self.assertIsInstance(output_size_bytes, int)
        self.assertFalse(include_reasoning)
        self.assertIsNone(session_id)
        self.assertIsNone(chat_id)
        self.assertIsNone(output_id)
        self.assertIsNone(target_output_id)

    @patch("llm.views._generate_optional_reasoning")
    @patch("llm.views.build_llm_generation_service")
    def test_llm_generate_calls_generation_and_reasoning_once_in_non_refinement_path(
        self,
        mock_build_generation_service,
        mock_generate_optional_reasoning,
    ):
        mock_generation_service = mock_build_generation_service.return_value
        mock_generation_service.generate.return_value = {"status": "ok"}
        mock_generate_optional_reasoning.return_value = {
            "final_answer": "ok",
            "reasoning_steps": ["once"],
            "thinking_log": "once",
        }
        client = APIClient()

        response = client.post(
            "/llm/generate/",
            {
                "input_json": {"sheet": "Sheet1"},
                "refinement": {"enabled": False},
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        mock_generation_service.generate.assert_called_once_with(
            input_json={"sheet": "Sheet1"},
            custom_schema_id=None,
            chat_context=None,
        )
        mock_generate_optional_reasoning.assert_called_once_with(
            include_reasoning=True,
            input_json={"sheet": "Sheet1"},
            output_json={"status": "ok"},
        )

    @patch("llm.views.build_llm_generation_service")
    def test_llm_generate_strips_reasoning_keys_from_output_json(self, mock_build_service):
        mock_service = mock_build_service.return_value
        mock_service.generate.return_value = {
            "headers": ["A", "B"],
            "rows": [["1", "2"]],
            "final_answer": "remove me",
            "reasoning_steps": ["remove me"],
            "thinking_log": "remove me",
        }
        client = APIClient()

        response = client.post(
            "/llm/generate/",
            {"input_json": {"sheet": "Sheet1"}, "include_reasoning": False},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["output_json"],
            {
                "headers": ["A", "B"],
                "rows": [["1", "2"]],
            },
        )

    @patch("llm.views.build_llm_reasoning_service")
    @patch("llm.views.build_llm_generation_service")
    def test_llm_generate_skips_reasoning_when_include_reasoning_false(
        self,
        mock_build_generation_service,
        mock_build_reasoning_service,
    ):
        mock_generation_service = mock_build_generation_service.return_value
        mock_generation_service.generate.return_value = {"status": "ok"}
        client = APIClient()

        response = client.post(
            "/llm/generate/",
            {
                "input_json": {"sheet": "Sheet1"},
                "include_reasoning": False,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["output_json"], {"status": "ok"})
        self.assertIsNone(response.data["reasoning"])
        mock_build_reasoning_service.assert_not_called()

    @patch("llm.views.logger")
    @patch("llm.views.generate_conversion_reasoning_response")
    @patch("llm.views.build_llm_reasoning_service")
    @patch("llm.views.build_llm_generation_service")
    def test_llm_generate_sets_reasoning_none_when_unexpected_auto_reasoning_error_occurs(
        self,
        mock_build_generation_service,
        mock_build_reasoning_service,
        mock_generate_conversion_reasoning,
        mock_logger,
    ):
        mock_generation_service = mock_build_generation_service.return_value
        mock_generation_service.generate.return_value = {"status": "ok"}
        mock_generate_conversion_reasoning.side_effect = RuntimeError("unexpected")
        client = APIClient()

        response = client.post(
            "/llm/generate/",
            {
                "input_json": {"sheet": "Sheet1"},
                "refinement": {"enabled": False},
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["output_json"], {"status": "ok"})
        self.assertIsNone(response.data["reasoning"])
        mock_build_reasoning_service.assert_called_once()
        mock_generate_conversion_reasoning.assert_called_once()
        mock_logger.exception.assert_called_once_with(
            "Unexpected error while generating automatic reasoning."
        )

    @patch("llm.views.logger")
    @patch("llm.views.generate_conversion_reasoning_response")
    @patch("llm.views.build_llm_reasoning_service")
    @patch("llm.views.build_llm_generation_service")
    def test_llm_generate_sets_reasoning_none_when_expected_auto_reasoning_error_occurs(
        self,
        mock_build_generation_service,
        mock_build_reasoning_service,
        mock_generate_conversion_reasoning,
        mock_logger,
    ):
        mock_generation_service = mock_build_generation_service.return_value
        mock_generation_service.generate.return_value = {"status": "ok"}
        mock_generate_conversion_reasoning.side_effect = OpenAIServiceError(
            "invalid reasoning payload"
        )
        client = APIClient()

        response = client.post(
            "/llm/generate/",
            {
                "input_json": {"sheet": "Sheet1"},
                "refinement": {"enabled": False},
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["output_json"], {"status": "ok"})
        self.assertIsNone(response.data["reasoning"])
        mock_build_reasoning_service.assert_called_once()
        mock_generate_conversion_reasoning.assert_called_once()
        mock_logger.exception.assert_called_once_with(
            "Automatic reasoning failed while handling llm_generate request."
        )

    @patch("llm.views.build_llm_generation_service")
    def test_llm_generate_passes_selected_schema_id_to_generation_service(
        self, mock_build_service
    ):
        mock_service = mock_build_service.return_value
        mock_service.generate.return_value = {"status": "ok"}
        client = APIClient()
        schema_id = uuid4()

        response = client.post(
            "/llm/generate/",
            {
                "input_json": {"sheet": "Sheet1"},
                "custom_schema_id": str(schema_id),
                "refinement": {"enabled": False},
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(mock_build_service.call_count, 1)
        self.assertTrue(mock_build_service.call_args[0][0].is_authenticated)
        mock_service.generate.assert_called_once_with(
            input_json={"sheet": "Sheet1"},
            custom_schema_id=schema_id,
            chat_context=None,
        )

    @patch("llm.views.build_llm_generation_service")
    def test_llm_generate_returns_404_when_selected_schema_missing(
        self, mock_build_service
    ):
        client = APIClient()
        schema_id = uuid4()
        mock_service = mock_build_service.return_value
        mock_service.generate.side_effect = CustomSchemaNotFoundError(
            "Custom schema not found."
        )

        response = client.post(
            "/llm/generate/",
            {
                "input_json": {"sheet": "Sheet1"},
                "custom_schema_id": str(schema_id),
                "refinement": {"enabled": False},
            },
            format="json",
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["detail"], "Custom schema not found.")
        self.assertEqual(mock_build_service.call_count, 1)
        self.assertTrue(mock_build_service.call_args[0][0].is_authenticated)
        mock_service.generate.assert_called_once_with(
            input_json={"sheet": "Sheet1"},
            custom_schema_id=schema_id,
            chat_context=None,
        )

    def test_llm_generate_rejects_missing_input_json(self):
        client = APIClient()
        response = client.post("/llm/generate/", {}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "Invalid request payload.")
        self.assertIn("errors", response.data)

    def test_llm_generate_rejects_non_object_or_array_input_json(self):
        client = APIClient()
        response = client.post("/llm/generate/", {"input_json": "not-json-object"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "Invalid request payload.")
        self.assertIn("errors", response.data)

    def test_llm_generate_rejects_invalid_custom_schema_id(self):
        client = APIClient()
        response = client.post(
            "/llm/generate/",
            {"input_json": {"sheet": "Sheet1"}, "custom_schema_id": "not-a-uuid"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "Invalid request payload.")
        self.assertIn("errors", response.data)

    def test_llm_generate_rejects_refinement_max_iterations_above_cap(self):
        client = APIClient()
        response = client.post(
            "/llm/generate/",
            {
                "input_json": {"sheet": "Sheet1"},
                "refinement": {"enabled": True, "max_iterations": 4},
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "Invalid request payload.")
        self.assertIn("errors", response.data)

    @patch("llm.views.RefinementOrchestrator")
    @patch("llm.views._generate_optional_reasoning")
    @patch("llm.views.build_llm_generation_service")
    def test_llm_generate_with_refinement_returns_extended_fields(
        self,
        mock_build_generation_service,
        mock_generate_optional_reasoning,
        mock_refinement_orchestrator_class,
    ):
        mock_build_generation_service.return_value = SimpleNamespace()
        mock_generate_optional_reasoning.return_value = {
            "final_answer": "should not be used",
            "reasoning_steps": ["unused"],
            "thinking_log": "unused",
        }
        mock_refinement_orchestrator = mock_refinement_orchestrator_class.return_value
        mock_refinement_orchestrator.run.return_value = {
            "raw_json": {"status": "raw"},
            "validated_json": {
                "document_info": {"source_type": "Excel", "filename": "sample.xlsx"},
                "summary": {"total_tables": 1},
                "content_data": [
                    {
                        "table_name": "Sheet1",
                        "headers": ["name"],
                        "rows": [{"name": "A"}],
                    }
                ],
            },
            "output_json": {
                "document_info": {"source_type": "Excel", "filename": "sample.xlsx"},
                "summary": {"total_tables": 1},
                "content_data": [
                    {
                        "table_name": "Sheet1",
                        "headers": ["name"],
                        "rows": [{"name": "A"}],
                    }
                ],
            },
            "validation_log": {
                "iteration": 2,
                "verdict": "valid",
                "errors": [],
                "warnings": [],
                "summary": "Output passed strict export schema validation.",
            },
            "reasoning": {
                "final_answer": "Refinement completed.",
                "reasoning_steps": ["Fixed required keys."],
                "thinking_log": "Iterative repair completed.",
            },
            "refinement_meta": {
                "iterations_run": 2,
                "max_iterations": 3,
                "early_exit_triggered": True,
                "final_status": "valid",
            },
        }
        client = APIClient()

        response = client.post(
            "/llm/generate/",
            {
                "input_json": {"sheet": "Sheet1"},
                "refinement": {
                    "enabled": True,
                    "max_iterations": 3,
                    "early_exit_on_valid": True,
                },
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["output_json"], response.data["validated_json"])
        self.assertNotIn("raw_json", response.data)
        self.assertNotIn("validation_log", response.data)
        self.assertNotIn("refinement_meta", response.data)
        self.assertEqual(response.data["reasoning"]["final_answer"], "Refinement completed.")
        mock_generate_optional_reasoning.assert_not_called()

    @patch("llm.views._build_chat_context_from_session")
    @patch("llm.views._resolve_generate_source_message")
    @patch("llm.views.RefinementOrchestrator")
    @patch("llm.views.build_llm_generation_service")
    def test_llm_generate_passes_chat_context_to_refinement_orchestrator(
        self,
        mock_build_generation_service,
        mock_refinement_orchestrator_class,
        mock_resolve_generate_source_message,
        mock_build_chat_context_from_session,
    ):
        mock_build_generation_service.return_value = SimpleNamespace()
        mock_refinement_orchestrator = mock_refinement_orchestrator_class.return_value
        mock_resolve_generate_source_message.return_value = (
            SimpleNamespace(target_output=None),
            SimpleNamespace(),
            None,
        )
        mock_build_chat_context_from_session.return_value = "USER: Gunakan Bahasa Indonesia"
        mock_refinement_orchestrator.run.return_value = {
            "raw_json": {"status": "raw"},
            "validated_json": {"status": "validated"},
            "output_json": {"status": "validated"},
            "validation_log": {
                "iteration": 1,
                "verdict": "valid",
                "errors": [],
                "warnings": [],
                "summary": "Output passed strict export schema validation.",
            },
            "reasoning": None,
            "refinement_meta": {
                "iterations_run": 1,
                "max_iterations": 3,
                "early_exit_triggered": True,
                "final_status": "valid",
            },
        }
        client = APIClient()

        response = client.post(
            "/llm/generate/",
            {
                "input_json": {"sheet": "Sheet1"},
                "chat_id": str(uuid4()),
                "refinement": {"enabled": True},
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        mock_refinement_orchestrator.run.assert_called_once()
        self.assertEqual(
            mock_refinement_orchestrator.run.call_args.kwargs["chat_context"],
            "USER: Gunakan Bahasa Indonesia",
        )

    @override_settings(LLM_EXPOSE_VALIDATION_LOG=False)
    @patch("llm.views.RefinementOrchestrator")
    @patch("llm.views.build_llm_generation_service")
    def test_llm_generate_with_refinement_hides_debug_refinement_fields_when_flag_disabled(
        self,
        mock_build_generation_service,
        mock_refinement_orchestrator_class,
    ):
        mock_build_generation_service.return_value = SimpleNamespace()
        mock_refinement_orchestrator = mock_refinement_orchestrator_class.return_value
        mock_refinement_orchestrator.run.return_value = {
            "raw_json": {"status": "raw"},
            "validated_json": {"status": "validated"},
            "output_json": {"status": "validated"},
            "validation_log": {
                "iteration": 1,
                "verdict": "valid",
                "errors": [],
                "warnings": [],
                "summary": "Output passed strict export schema validation.",
            },
            "reasoning": None,
            "refinement_meta": {
                "iterations_run": 1,
                "max_iterations": 3,
                "early_exit_triggered": True,
                "final_status": "valid",
            },
        }
        client = APIClient()

        response = client.post(
            "/llm/generate/",
            {"input_json": {"sheet": "Sheet1"}, "refinement": {"enabled": True}},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["output_json"], {"status": "validated"})
        self.assertEqual(response.data["validated_json"], {"status": "validated"})
        self.assertNotIn("raw_json", response.data)
        self.assertNotIn("validation_log", response.data)
        self.assertNotIn("refinement_meta", response.data)

    @override_settings(LLM_EXPOSE_VALIDATION_LOG=True)
    @patch("llm.views.RefinementOrchestrator")
    @patch("llm.views.build_llm_generation_service")
    def test_llm_generate_with_refinement_exposes_validation_log_when_enabled(
        self,
        mock_build_generation_service,
        mock_refinement_orchestrator_class,
    ):
        mock_build_generation_service.return_value = SimpleNamespace()
        mock_refinement_orchestrator = mock_refinement_orchestrator_class.return_value
        mock_refinement_orchestrator.run.return_value = {
            "raw_json": {"status": "raw"},
            "validated_json": {
                "document_info": {"source_type": "Excel", "filename": "sample.xlsx"},
                "summary": {"total_tables": 1},
                "content_data": [
                    {
                        "table_name": "Sheet1",
                        "headers": ["name"],
                        "rows": [{"name": "A"}],
                    }
                ],
            },
            "output_json": {
                "document_info": {"source_type": "Excel", "filename": "sample.xlsx"},
                "summary": {"total_tables": 1},
                "content_data": [
                    {
                        "table_name": "Sheet1",
                        "headers": ["name"],
                        "rows": [{"name": "A"}],
                    }
                ],
            },
            "validation_log": {
                "iteration": 2,
                "verdict": "valid",
                "errors": [],
                "warnings": [],
                "summary": "Output passed strict export schema validation.",
            },
            "reasoning": {
                "final_answer": "Refinement completed.",
                "reasoning_steps": ["Fixed required keys."],
                "thinking_log": "Iterative repair completed.",
            },
            "refinement_meta": {
                "iterations_run": 2,
                "max_iterations": 3,
                "early_exit_triggered": True,
                "final_status": "valid",
            },
        }
        client = APIClient()

        response = client.post(
            "/llm/generate/",
            {
                "input_json": {"sheet": "Sheet1"},
                "refinement": {
                    "enabled": True,
                    "max_iterations": 3,
                    "early_exit_on_valid": True,
                },
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["raw_json"], {"status": "raw"})
        self.assertEqual(response.data["validation_log"]["verdict"], "valid")
        self.assertEqual(response.data["refinement_meta"]["final_status"], "valid")

    # Positive
    @override_settings(LLM_EXPOSE_VALIDATION_LOG=True)
    @patch("llm.views.RefinementOrchestrator")
    @patch("llm.views.build_llm_generation_service")
    def test_positive_llm_generate_exposes_debug_refinement_fields_when_flag_enabled(
        self,
        mock_build_generation_service,
        mock_refinement_orchestrator_class,
    ):
        mock_build_generation_service.return_value = SimpleNamespace()
        mock_refinement_orchestrator = mock_refinement_orchestrator_class.return_value
        mock_refinement_orchestrator.run.return_value = {
            "raw_json": {"status": "raw"},
            "validated_json": {"status": "validated"},
            "output_json": {"status": "validated"},
            "validation_log": {
                "iteration": 1,
                "verdict": "valid",
                "errors": [],
                "warnings": [],
                "summary": "Output passed strict export schema validation.",
            },
            "reasoning": {
                "final_answer": "ok",
                "reasoning_steps": ["step"],
                "thinking_log": "log",
            },
            "refinement_meta": {
                "iterations_run": 1,
                "max_iterations": 3,
                "early_exit_triggered": True,
                "final_status": "valid",
            },
        }
        client = APIClient()

        response = client.post(
            "/llm/generate/",
            {"input_json": {"sheet": "Sheet1"}, "refinement": {"enabled": True}},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("raw_json", response.data)
        self.assertIn("validation_log", response.data)
        self.assertIn("refinement_meta", response.data)

    # Negative
    def test_negative_llm_generate_rejects_invalid_refinement_shape(self):
        client = APIClient()
        response = client.post(
            "/llm/generate/",
            {
                "input_json": {"sheet": "Sheet1"},
                "refinement": {"max_iterations": "bad-value"},
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "Invalid request payload.")
        self.assertIn("errors", response.data)

    # Edge
    @patch("llm.views.build_llm_generation_service")
    def test_edge_llm_generate_uses_non_refinement_path_when_refinement_explicitly_disabled(
        self,
        mock_build_service,
    ):
        mock_service = mock_build_service.return_value
        mock_service.generate.return_value = {"status": "ok"}
        client = APIClient()

        response = client.post(
            "/llm/generate/",
            {
                "input_json": {"sheet": "Sheet1"},
                "include_reasoning": False,
                "refinement": {"enabled": False},
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["output_json"], {"status": "ok"})
        self.assertNotIn("validated_json", response.data)
        self.assertNotIn("raw_json", response.data)

    def test_llm_generate_rejects_client_model_field(self):
        client = APIClient()
        response = client.post(
            "/llm/generate/",
            {"input_json": {"ok": True}, "model": "gpt-4.1-mini"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "Invalid request payload.")
        self.assertIn("errors", response.data)

    @patch("llm.views.build_llm_generation_service")
    def test_llm_generate_returns_503_for_service_error(self, mock_build_service):
        mock_service = mock_build_service.return_value
        mock_service.generate.side_effect = OpenAIConfigurationError(
            "OPENAI_API_KEY is not configured."
        )
        client = APIClient()

        response = client.post(
            "/llm/generate/",
            {
                "input_json": {"hello": "world"},
                "refinement": {"enabled": False},
            },
            format="json",
        )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data["detail"], "Service unavailable. Please try again later.")

    @patch("llm.views.build_llm_generation_service")
    def test_llm_generate_returns_502_for_invalid_json_response(self, mock_build_service):
        mock_service = mock_build_service.return_value
        mock_service.generate.side_effect = OpenAIServiceError(
            "OpenAI response is not valid JSON."
        )
        client = APIClient()

        response = client.post(
            "/llm/generate/",
            {
                "input_json": {"hello": "world"},
                "refinement": {"enabled": False},
            },
            format="json",
        )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.data["detail"], "Failed to generate response from LLM provider.")

    @patch("llm.views.logger")
    @patch("llm.views.build_llm_generation_service")
    def test_llm_generate_returns_502_for_upstream_auth_error(self, mock_build_service, mock_logger):
        mock_service = mock_build_service.return_value
        mock_service.generate.side_effect = OpenAIUpstreamError(
            "LLM authentication failed.",
            status_code=502,
        )
        client = APIClient()

        response = client.post(
            "/llm/generate/",
            {
                "input_json": {"hello": "world"},
                "refinement": {"enabled": False},
            },
            format="json",
        )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.data["detail"], "Failed to generate response from LLM provider.")
        mock_logger.exception.assert_called_once_with("Upstream LLM provider error while handling llm_generate request.")

    @patch("llm.views.logger")
    @patch("llm.views.build_llm_generation_service")
    def test_llm_generate_returns_429_for_upstream_rate_limit(self, mock_build_service, mock_logger):
        mock_service = mock_build_service.return_value
        mock_service.generate.side_effect = OpenAIUpstreamError(
            "LLM rate limit exceeded.",
            status_code=429,
        )
        client = APIClient()

        response = client.post(
            "/llm/generate/",
            {
                "input_json": {"hello": "world"},
                "refinement": {"enabled": False},
            },
            format="json",
        )

        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.data["detail"], "Failed to generate response from LLM provider.")
        mock_logger.exception.assert_called_once_with("Upstream LLM provider error while handling llm_generate request.")

    @patch("llm.views.logger")
    @patch("llm.views.build_llm_generation_service")
    def test_llm_generate_returns_504_for_upstream_timeout(self, mock_build_service, mock_logger):
        mock_service = mock_build_service.return_value
        mock_service.generate.side_effect = OpenAIUpstreamError(
            "LLM request timed out.",
            status_code=504,
        )
        client = APIClient()

        response = client.post("/llm/generate/", {"input_json": {"hello": "world"}}, format="json")

        self.assertEqual(response.status_code, 504)
        self.assertEqual(response.data["detail"], "Failed to generate response from LLM provider.")
        mock_logger.exception.assert_called_once_with("Upstream LLM provider error while handling llm_generate request.")

    @patch("llm.views.logger")
    @patch("llm.views.build_llm_generation_service")
    def test_llm_generate_logs_upstream_error_without_exposing_exception(self, mock_build_service, mock_logger):
        mock_service = mock_build_service.return_value
        mock_service.generate.side_effect = OpenAIUpstreamError(
            "raw upstream details",
            status_code=502,
        )
        client = APIClient()

        response = client.post("/llm/generate/", {"input_json": {"hello": "world"}}, format="json")

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.data["detail"], "Failed to generate response from LLM provider.")
        self.assertNotIn("raw upstream details", response.data["detail"])
        mock_logger.exception.assert_called_once_with(
            "Upstream LLM provider error while handling llm_generate request."
        )

    @patch("llm.views.logger")
    @patch("llm.views.build_llm_generation_service")
    def test_llm_generate_returns_500_for_unexpected_error(self, mock_build_service, mock_logger):
        mock_service = mock_build_service.return_value
        mock_service.generate.side_effect = RuntimeError("upstream error")
        client = APIClient()

        response = client.post("/llm/generate/", {"input_json": {"hello": "world"}}, format="json")

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.data["detail"], "Internal server error.")
        mock_logger.exception.assert_called_once()

    @patch("llm.views.build_llm_reasoning_service")
    @patch("llm.views.LlmGenerateResponseSerializer")
    @patch("llm.views.build_llm_generation_service")
    def test_llm_generate_returns_502_when_response_serializer_invalid(
        self,
        mock_build_service,
        mock_response_serializer_class,
        mock_build_reasoning_service,
    ):
        mock_service = mock_build_service.return_value
        mock_service.generate.return_value = {"status": "ok"}
        mock_reasoning_service = mock_build_reasoning_service.return_value
        mock_reasoning_service.generate.return_value = {
            "final_answer": "Answer",
            "reasoning_steps": ["Step one"],
            "thinking_log": "Summary",
        }
        mock_response_serializer = mock_response_serializer_class.return_value
        mock_response_serializer.is_valid.return_value = False
        client = APIClient()

        response = client.post(
            "/llm/generate/",
            {
                "input_json": {"hello": "world"},
                "refinement": {"enabled": False},
            },
            format="json",
        )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.data["detail"], "Failed to generate response from LLM provider.")
        mock_response_serializer_class.assert_called_once_with(
            data={
                "output_json": {"status": "ok"},
                "session_id": None,
                "chat_id": None,
                "output_id": None,
                "reasoning": {
                    "final_answer": "Answer",
                    "reasoning_steps": ["Step one"],
                    "thinking_log": "Summary",
                },
            }
        )

    @patch("llm.views.logger")
    @patch("llm.views.build_llm_generation_service")
    def test_llm_generate_returns_400_for_value_error(self, mock_build_service, mock_logger):
        mock_service = mock_build_service.return_value
        mock_service.generate.side_effect = ValueError(
            "input_json must be an object or array."
        )
        client = APIClient()

        response = client.post("/llm/generate/", {"input_json": {"hello": "world"}}, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "Invalid request payload.")
        self.assertEqual(response.data["errors"]["input_json"], ["Invalid input_json payload."])
        mock_logger.exception.assert_called_once_with("Invalid input_json payload.")

    def test_llm_generate_rejects_non_json_content_type(self):
        client = APIClient()
        response = client.post("/llm/generate/", data="plain text", content_type="text/plain")
        self.assertEqual(response.status_code, 415)
        self.assertEqual(response.data["detail"], "Content-Type must be application/json.")

    def test_llm_generate_rejects_get(self):
        client = APIClient()
        response = client.get("/llm/generate/")
        self.assertEqual(response.status_code, 405)

    # @patch("llm.views.generate_json")
    # def test_llm_generate_rate_limited_5_per_minute(self, mock_generate_json):
    #     mock_generate_json.return_value = {"status": "ok"}
    #     client = APIClient()
    #     payload = {"input_json": {"hello": "world"}}

    #     for _ in range(5):
    #         response = client.post("/llm/generate/", payload, format="json", REMOTE_ADDR="127.0.0.99")
    #         self.assertEqual(response.status_code, 200)

    #     blocked = client.post("/llm/generate/", payload, format="json", REMOTE_ADDR="127.0.0.99")
    #     self.assertEqual(blocked.status_code, 429)
    #     self.assertIn("detail", blocked.data)
    #     self.assertEqual(blocked["X-RateLimit-Limit"], "5")


class LlmReasoningEndpointTest(SimpleTestCase):
    # Positive
    def test_build_llm_reasoning_service_returns_default_dependencies(self):
        service = build_llm_reasoning_service()

        self.assertEqual(service.__class__.__name__, "LlmReasoningService")
        self.assertIsInstance(service.text_provider, OpenAITextGenerationProvider)

    # Positive
    @patch("llm.views.build_llm_reasoning_service")
    def test_llm_reasoning_returns_200_for_authenticated_user(self, mock_build_service):
        mock_service = mock_build_service.return_value
        mock_service.generate.return_value = {
            "final_answer": "Total payment is Rp1.250.000.",
            "reasoning_steps": [
                "Identify the total amount.",
                "Confirm it is the final payable total.",
            ],
            "thinking_log": "The invoice total was identified and summarized.",
        }
        client = APIClient()
        client.force_authenticate(user=SimpleNamespace(is_authenticated=True, id="user-1"))

        response = client.post(
            "/llm/reasoning/",
            {"prompt": "Summarize this invoice"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["final_answer"], "Total payment is Rp1.250.000.")
        self.assertEqual(
            response.data["reasoning_steps"],
            [
                "Identify the total amount.",
                "Confirm it is the final payable total.",
            ],
        )
        self.assertEqual(
            response.data["thinking_log"],
            "The invoice total was identified and summarized.",
        )
        mock_service.generate.assert_called_once_with(prompt="Summarize this invoice")

    # Negative
    @patch("llm.views.build_llm_reasoning_service")
    def test_llm_reasoning_requires_authentication(self, mock_build_service):
        client = APIClient()

        response = client.post(
            "/llm/reasoning/",
            {"prompt": "Summarize this invoice"},
            format="json",
        )

        self.assertEqual(response.status_code, 401)
        mock_build_service.assert_not_called()

    # Negative
    @patch("llm.views.build_llm_reasoning_service")
    def test_llm_reasoning_rejects_invalid_token(self, mock_build_service):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer invalid.token")

        response = client.post(
            "/llm/reasoning/",
            {"prompt": "Summarize this invoice"},
            format="json",
        )

        self.assertEqual(response.status_code, 401)
        mock_build_service.assert_not_called()

    # Edge
    @patch("llm.views.build_llm_reasoning_service")
    def test_llm_reasoning_rejects_blank_prompt_without_calling_service(
        self, mock_build_service
    ):
        client = APIClient()
        client.force_authenticate(user=SimpleNamespace(is_authenticated=True, id="user-1"))

        response = client.post(
            "/llm/reasoning/",
            {"prompt": "   "},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "Invalid request payload.")
        self.assertIn("errors", response.data)
        mock_build_service.assert_not_called()

    # Negative
    @patch("llm.views.LlmReasoningResponseSerializer")
    @patch("llm.views.build_llm_reasoning_service")
    def test_llm_reasoning_returns_502_when_response_serializer_invalid(
        self, mock_build_service, mock_response_serializer_class
    ):
        mock_service = mock_build_service.return_value
        mock_service.generate.return_value = {
            "final_answer": "Answer",
            "reasoning_steps": ["Step one"],
            "thinking_log": "Summary",
        }
        mock_response_serializer = mock_response_serializer_class.return_value
        mock_response_serializer.is_valid.return_value = False
        client = APIClient()
        client.force_authenticate(user=SimpleNamespace(is_authenticated=True, id="user-1"))

        response = client.post(
            "/llm/reasoning/",
            {"prompt": "Summarize this invoice"},
            format="json",
        )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.data["detail"], "Failed to generate response from LLM provider.")

    # Negative
    @patch("llm.views.logger")
    @patch("llm.views.build_llm_reasoning_service")
    def test_llm_reasoning_returns_400_for_value_error(self, mock_build_service, mock_logger):
        mock_service = mock_build_service.return_value
        mock_service.generate.side_effect = ValueError("prompt must be a non-empty string.")
        client = APIClient()
        client.force_authenticate(user=SimpleNamespace(is_authenticated=True, id="user-1"))

        response = client.post(
            "/llm/reasoning/",
            {"prompt": "Summarize this invoice"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "Invalid request payload.")
        self.assertEqual(response.data["errors"]["prompt"], ["Invalid prompt payload."])
        mock_logger.exception.assert_called_once_with("Invalid prompt payload.")

    # Negative
    @patch("llm.views.build_llm_reasoning_service")
    def test_llm_reasoning_returns_503_for_configuration_error(self, mock_build_service):
        mock_service = mock_build_service.return_value
        mock_service.generate.side_effect = OpenAIConfigurationError("OPENAI_API_KEY is not configured.")
        client = APIClient()
        client.force_authenticate(user=SimpleNamespace(is_authenticated=True, id="user-1"))

        response = client.post(
            "/llm/reasoning/",
            {"prompt": "Summarize this invoice"},
            format="json",
        )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data["detail"], "Service unavailable. Please try again later.")

    # Negative
    @patch("llm.views.build_llm_reasoning_service")
    def test_llm_reasoning_returns_502_for_provider_failure(self, mock_build_service):
        mock_service = mock_build_service.return_value
        mock_service.generate.side_effect = OpenAIServiceError("invalid response")
        client = APIClient()
        client.force_authenticate(user=SimpleNamespace(is_authenticated=True, id="user-1"))

        response = client.post(
            "/llm/reasoning/",
            {"prompt": "Summarize this invoice"},
            format="json",
        )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.data["detail"], "Failed to generate response from LLM provider.")

    # Negative
    @patch("llm.views.logger")
    @patch("llm.views.build_llm_reasoning_service")
    def test_llm_reasoning_returns_upstream_status_code(self, mock_build_service, mock_logger):
        mock_service = mock_build_service.return_value
        mock_service.generate.side_effect = OpenAIUpstreamError(
            "LLM rate limit exceeded.",
            status_code=429,
        )
        client = APIClient()
        client.force_authenticate(user=SimpleNamespace(is_authenticated=True, id="user-1"))

        response = client.post(
            "/llm/reasoning/",
            {"prompt": "Summarize this invoice"},
            format="json",
        )

        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.data["detail"], "Failed to generate response from LLM provider.")
        mock_logger.exception.assert_called_once_with(
            "Upstream LLM provider error while handling llm_reasoning request."
        )

    # Edge
    @patch("llm.views.logger")
    @patch("llm.views.build_llm_reasoning_service")
    def test_llm_reasoning_returns_500_for_unexpected_error(self, mock_build_service, mock_logger):
        mock_service = mock_build_service.return_value
        mock_service.generate.side_effect = RuntimeError("unexpected")
        client = APIClient()
        client.force_authenticate(user=SimpleNamespace(is_authenticated=True, id="user-1"))

        response = client.post(
            "/llm/reasoning/",
            {"prompt": "Summarize this invoice"},
            format="json",
        )

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.data["detail"], "Internal server error.")
        mock_logger.exception.assert_called_once_with(
            "Unexpected error while handling llm_reasoning request."
        )

    # Negative
    def test_llm_reasoning_rejects_non_json_content_type(self):
        client = APIClient()
        client.force_authenticate(user=SimpleNamespace(is_authenticated=True, id="user-1"))

        response = client.post(
            "/llm/reasoning/",
            data="plain text",
            content_type="text/plain",
        )

        self.assertEqual(response.status_code, 415)
        self.assertEqual(response.data["detail"], "Content-Type must be application/json.")


class LlmGenerateSessionIntegrationTest(TestCase):
    def setUp(self):
        self._default_reasoning_patch = patch(
            "llm.views._generate_optional_reasoning",
            return_value=None,
        )
        self._default_reasoning_patch.start()
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="session-generate@example.com",
            name="Session Generate User",
            password="secret",
            status="verified",
        )
        self.output_json = {
            "document_info": {"filename": "invoice.pdf"},
            "summary": {"table_count": 1},
            "content_data": [{"table_name": "Sheet1", "headers": ["A"], "rows": [["1"]]}],
        }

    def tearDown(self):
        self._default_reasoning_patch.stop()
        super().tearDown()

    @patch("llm.views.build_llm_generation_service")
    def test_llm_generate_creates_session_and_generated_output_for_authenticated_user(
        self, mock_build_service
    ):
        mock_service = mock_build_service.return_value
        raw_output_json = {
            "headers": ["unit", "value"],
            "rows": [["ICU", 1000]],
            "final_answer": "Raw output for FE",
        }
        mock_service.generate.return_value = raw_output_json
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/llm/generate/",
            {
                "input_json": {
                    "filename": "invoice.pdf",
                    "extracted": "raw upload text",
                },
                "refinement": {"enabled": False},
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("session_id", response.data)
        self.assertIn("chat_id", response.data)
        self.assertIn("output_id", response.data)
        self.assertEqual(Session.objects.count(), 1)
        session = Session.objects.get(owner=self.user)
        self.assertEqual(str(session.id), response.data["session_id"])
        self.assertEqual(ChatMessage.objects.count(), 1)
        bootstrap_message = ChatMessage.objects.get(session=session)
        self.assertEqual(bootstrap_message.role, ChatMessage.ROLE_USER)
        self.assertEqual(str(bootstrap_message.id), response.data["chat_id"])
        self.assertIn("invoice.pdf", bootstrap_message.content)
        self.assertEqual(GeneratedOutput.objects.count(), 1)
        generated_output = GeneratedOutput.objects.get(session=session)
        self.assertEqual(str(generated_output.id), response.data["output_id"])
        self.assertEqual(generated_output.source_message_id, bootstrap_message.id)
        self.assertIsNone(generated_output.parent_output_id)
        self.assertEqual(
            generated_output.output_json,
            {
                "headers": ["unit", "value"],
                "rows": [["ICU", 1000]],
            },
        )
        self.assertIsInstance(generated_output.thinking_log, str)
        self.assertEqual(
            generated_output.export_output_json,
            {
                "document_info": {
                    "source_type": "PDF",
                    "filename": "invoice.pdf",
                },
                "summary": {
                    "total_tables": 1,
                    "total_rows": 1,
                    "total_columns": 2,
                },
                "content_data": [
                    {
                        "table_name": "Sheet1",
                        "headers": ["unit", "value"],
                        "rows": [{"unit": "ICU", "value": 1000}],
                    }
                ],
            },
        )
        self.assertEqual(ArtifactHistory.objects.count(), 1)

    @patch("llm.views._generate_optional_reasoning")
    @patch("llm.views.build_llm_generation_service")
    def test_llm_generate_persists_thinking_log_from_reasoning_response(
        self,
        mock_build_service,
        mock_generate_reasoning,
    ):
        mock_service = mock_build_service.return_value
        mock_service.generate.return_value = {
            "headers": ["unit", "value"],
            "rows": [["ICU", 1000]],
        }
        mock_generate_reasoning.return_value = {
            "final_answer": "Done.",
            "reasoning_steps": ["Mapped rows."],
            "thinking_log": "Normalized columns and preserved totals.",
        }
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/llm/generate/",
            {
                "input_json": {
                    "filename": "invoice.pdf",
                    "extracted": "raw upload text",
                },
                "refinement": {"enabled": False},
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        generated_output = GeneratedOutput.objects.get()
        self.assertEqual(
            generated_output.thinking_log,
            "Normalized columns and preserved totals.",
        )
        self.assertEqual(generated_output.reasoning, mock_generate_reasoning.return_value)

    @patch("llm.views._generate_optional_reasoning")
    @patch("llm.views.build_llm_generation_service")
    def test_llm_generate_defaults_thinking_log_to_empty_when_reasoning_missing(
        self,
        mock_build_service,
        mock_generate_reasoning,
    ):
        mock_service = mock_build_service.return_value
        mock_service.generate.return_value = {
            "headers": ["unit", "value"],
            "rows": [["ICU", 1000]],
        }
        mock_generate_reasoning.return_value = None
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/llm/generate/",
            {
                "input_json": {
                    "filename": "invoice.pdf",
                    "extracted": "raw upload text",
                },
                "refinement": {"enabled": False},
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        generated_output = GeneratedOutput.objects.get()
        self.assertEqual(generated_output.thinking_log, "")
        self.assertEqual(generated_output.reasoning, {})

    @patch("llm.views._build_generate_success_response")
    @patch("llm.views._generate_optional_reasoning")
    @patch("llm.views.build_llm_generation_service")
    def test_llm_generate_defaults_thinking_log_to_empty_when_reasoning_log_is_not_string(
        self,
        mock_build_service,
        mock_generate_reasoning,
        mock_build_success_response,
    ):
        mock_service = mock_build_service.return_value
        mock_service.generate.return_value = {
            "headers": ["unit", "value"],
            "rows": [["ICU", 1000]],
        }
        mock_generate_reasoning.return_value = {
            "final_answer": "Done.",
            "thinking_log": ["not", "a", "string"],
        }
        mock_build_success_response.return_value = Response({"status": "ok"})
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/llm/generate/",
            {
                "input_json": {
                    "filename": "invoice.pdf",
                    "extracted": "raw upload text",
                },
                "refinement": {"enabled": False},
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        generated_output = GeneratedOutput.objects.get()
        self.assertEqual(generated_output.thinking_log, "")
        self.assertEqual(
            generated_output.reasoning,
            mock_generate_reasoning.return_value,
        )

    @patch("llm.views.build_llm_generation_service")
    def test_llm_generate_links_output_to_source_chat_and_parent_output(self, mock_build_service):
        mock_service = mock_build_service.return_value
        mock_service.generate.return_value = {
            "headers": ["unit", "value"],
            "rows": [["ICU", 1000]],
        }
        session = Session.objects.create(owner=self.user, title="Refine Session")
        parent_output = GeneratedOutput.objects.create(
            session=session,
            output_json={"content_data": []},
        )
        source_message = ChatMessage.objects.create(
            session=session,
            role=ChatMessage.ROLE_USER,
            content="Refine output sebelumnya.",
            target_output=parent_output,
        )
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/llm/generate/",
            {
                "input_json": {
                    "filename": "invoice.pdf",
                    "extracted": "raw upload text",
                },
                "chat_id": str(source_message.id),
                "refinement": {"enabled": False},
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        generated_output = GeneratedOutput.objects.exclude(id=parent_output.id).get()
        self.assertEqual(generated_output.session, session)
        self.assertEqual(generated_output.source_message, source_message)
        self.assertEqual(generated_output.parent_output, parent_output)

    @patch("llm.views.build_llm_generation_service")
    def test_llm_generate_returns_404_for_unknown_chat_id(self, mock_build_service):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/llm/generate/",
            {
                "input_json": {
                    "filename": "invoice.pdf",
                    "extracted": "raw upload text",
                },
                "chat_id": str(uuid4()),
                "refinement": {"enabled": False},
            },
            format="json",
        )

        self.assertEqual(response.status_code, 404)
        mock_build_service.assert_not_called()

    @patch("llm.views.build_llm_generation_service")
    def test_llm_generate_returns_400_when_chat_id_session_mismatches_request_session(self, mock_build_service):
        session = Session.objects.create(owner=self.user, title="Requested Session")
        other_session = Session.objects.create(owner=self.user, title="Source Session")
        source_message = ChatMessage.objects.create(
            session=other_session,
            role=ChatMessage.ROLE_USER,
            content="Refine output sebelumnya.",
        )
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/llm/generate/",
            {
                "input_json": {
                    "filename": "invoice.pdf",
                    "extracted": "raw upload text",
                },
                "session_id": str(session.id),
                "chat_id": str(source_message.id),
                "refinement": {"enabled": False},
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data["errors"]["chat_id"],
            ["chat_id must belong to the same session."],
        )
        mock_build_service.assert_not_called()

    @patch("llm.views.build_llm_generation_service")
    def test_llm_generate_does_not_create_session_or_generated_output_when_generation_fails(
        self, mock_build_service
    ):
        mock_service = mock_build_service.return_value
        mock_service.generate.side_effect = RuntimeError("upstream error")
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/llm/generate/",
            {
                "input_json": {"filename": "invoice.pdf", "extracted": "raw upload text"},
                "refinement": {"enabled": False},
            },
            format="json",
        )

        self.assertEqual(response.status_code, 500)
        self.assertFalse(Session.objects.exists())
        self.assertFalse(GeneratedOutput.objects.exists())
        self.assertFalse(ArtifactHistory.objects.exists())

    @patch("llm.views.build_llm_generation_service")
    def test_llm_generate_persists_sanitized_output_json_without_reasoning_keys(
        self,
        mock_build_service,
    ):
        mock_service = mock_build_service.return_value
        mock_service.generate.return_value = {
            "document_info": {"filename": "invoice.pdf"},
            "headers": ["A", "B"],
            "rows": [["1", "2"]],
            "final_answer": "remove me",
            "reasoning_steps": ["remove me"],
            "thinking_log": "remove me",
        }
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/llm/generate/",
            {
                "input_json": {
                    "filename": "invoice.pdf",
                    "extracted": "raw upload text",
                },
                "include_reasoning": False,
                "refinement": {"enabled": False},
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(ArtifactHistory.objects.count(), 1)
        history = ArtifactHistory.objects.get()
        self.assertNotIn("final_answer", history.output_json)
        self.assertNotIn("reasoning_steps", history.output_json)
        self.assertNotIn("thinking_log", history.output_json)
        self.assertEqual(
            history.output_json,
            {
                "document_info": {"filename": "invoice.pdf"},
                "headers": ["A", "B"],
                "rows": [["1", "2"]],
            },
        )

    @patch("llm.views.build_llm_generation_service")
    def test_llm_generate_reuses_existing_owned_session_when_session_id_is_provided(
        self, mock_build_service
    ):
        mock_service = mock_build_service.return_value
        raw_output_json = {
            "headers": ["unit", "value"],
            "rows": [["ICU", 1000]],
            "reasoning_steps": ["remove me from persisted raw payload"],
        }
        mock_service.generate.return_value = raw_output_json
        session = Session.objects.create(owner=self.user, title="Existing Session")
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/llm/generate/",
            {
                "input_json": {"filename": "invoice.pdf", "extracted": "raw upload text"},
                "session_id": str(session.id),
                "refinement": {"enabled": False},
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["session_id"], str(session.id))
        self.assertEqual(Session.objects.count(), 1)
        self.assertEqual(GeneratedOutput.objects.count(), 1)
        generated_output = GeneratedOutput.objects.get()
        self.assertEqual(generated_output.session, session)
        self.assertEqual(response.data["output_id"], str(generated_output.id))
        self.assertEqual(
            generated_output.output_json,
            {
                "headers": ["unit", "value"],
                "rows": [["ICU", 1000]],
            },
        )
        self.assertEqual(
            generated_output.export_output_json["content_data"][0]["rows"],
            [{"unit": "ICU", "value": 1000}],
        )
        self.assertTrue(ArtifactHistory.objects.exists())

    @patch("llm.views.build_llm_generation_service")
    def test_llm_generate_appends_follow_up_user_prompt_to_existing_session(
        self, mock_build_service
    ):
        mock_service = mock_build_service.return_value
        mock_service.generate.return_value = {
            "headers": ["unit", "value"],
            "rows": [["ICU", 1000]],
        }
        session = Session.objects.create(owner=self.user, title="Existing Session")
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/llm/generate/",
            {
                "session_id": str(session.id),
                "input_json": {
                    "filename": "invoice.pdf",
                    "user_prompt": "Lanjutkan untuk sheet berikutnya.",
                },
                "include_reasoning": False,
                "refinement": {"enabled": False},
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["session_id"], str(session.id))
        self.assertIsNotNone(response.data["chat_id"])
        self.assertEqual(Session.objects.count(), 1)

        user_messages = list(
            ChatMessage.objects.filter(session=session, role=ChatMessage.ROLE_USER).order_by("created_at")
        )
        self.assertEqual(len(user_messages), 1)
        self.assertEqual(user_messages[0].content, "Lanjutkan untuk sheet berikutnya.")
        self.assertEqual(str(user_messages[0].id), response.data["chat_id"])

        generated_output = GeneratedOutput.objects.get(session=session)
        self.assertEqual(generated_output.source_message_id, user_messages[0].id)

    @patch("llm.views.build_llm_generation_service")
    def test_llm_generate_hydrates_previous_output_from_target_output_id(
        self, mock_build_service
    ):
        mock_service = mock_build_service.return_value
        mock_service.generate.return_value = {
            "headers": ["unit", "value"],
            "rows": [["ICU", 1000]],
        }
        session = Session.objects.create(owner=self.user, title="Existing Session")
        parent_output = GeneratedOutput.objects.create(
            session=session,
            output_json={"content_data": [{"rows": [{"status": "all"}]}]},
        )
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/llm/generate/",
            {
                "session_id": str(session.id),
                "target_output_id": str(parent_output.id),
                "input_json": {
                    "filename": "invoice.pdf",
                    "user_prompt": "Hanya tampilkan status paid.",
                },
                "include_reasoning": False,
                "refinement": {"enabled": False},
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        mock_service.generate.assert_called_once_with(
            input_json={
                "filename": "invoice.pdf",
                "user_prompt": "Hanya tampilkan status paid.",
                "previous_output": parent_output.output_json,
            },
            custom_schema_id=None,
            chat_context=None,
        )

        user_messages = list(
            ChatMessage.objects.filter(session=session, role=ChatMessage.ROLE_USER).order_by("created_at")
        )
        self.assertEqual(len(user_messages), 1)
        self.assertEqual(user_messages[0].target_output_id, parent_output.id)

        generated_output = GeneratedOutput.objects.exclude(id=parent_output.id).get()
        self.assertEqual(generated_output.parent_output_id, parent_output.id)

    @patch("llm.views.build_llm_generation_service")
    def test_llm_generate_resolves_session_from_target_output_when_session_id_missing(
        self, mock_build_service
    ):
        mock_service = mock_build_service.return_value
        mock_service.generate.return_value = {
            "headers": ["unit", "value"],
            "rows": [["ICU", 1000]],
        }
        session = Session.objects.create(owner=self.user, title="Existing Session")
        parent_output = GeneratedOutput.objects.create(
            session=session,
            output_json={"content_data": [{"rows": [{"status": "all"}]}]},
        )
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/llm/generate/",
            {
                "target_output_id": str(parent_output.id),
                "input_json": {
                    "filename": "invoice.pdf",
                    "user_prompt": "Hanya tampilkan status paid.",
                },
                "include_reasoning": False,
                "refinement": {"enabled": False},
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["session_id"], str(session.id))
        mock_service.generate.assert_called_once_with(
            input_json={
                "filename": "invoice.pdf",
                "user_prompt": "Hanya tampilkan status paid.",
                "previous_output": parent_output.output_json,
            },
            custom_schema_id=None,
            chat_context=None,
        )

        user_messages = list(
            ChatMessage.objects.filter(session=session, role=ChatMessage.ROLE_USER).order_by("created_at")
        )
        self.assertEqual(len(user_messages), 1)
        self.assertEqual(user_messages[0].target_output_id, parent_output.id)

        generated_output = GeneratedOutput.objects.exclude(id=parent_output.id).get()
        self.assertEqual(generated_output.parent_output_id, parent_output.id)

    @patch("llm.views.build_llm_generation_service")
    def test_llm_generate_returns_400_when_target_output_id_session_mismatches_request_session(
        self, mock_build_service
    ):
        requested_session = Session.objects.create(owner=self.user, title="Requested Session")
        other_session = Session.objects.create(owner=self.user, title="Other Session")
        parent_output = GeneratedOutput.objects.create(
            session=other_session,
            output_json={"content_data": [{"rows": [{"status": "all"}]}]},
        )
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/llm/generate/",
            {
                "session_id": str(requested_session.id),
                "target_output_id": str(parent_output.id),
                "input_json": {"filename": "invoice.pdf", "user_prompt": "Refine"},
                "include_reasoning": False,
                "refinement": {"enabled": False},
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data["errors"]["target_output_id"],
            ["target_output_id must belong to the same session."],
        )
        mock_build_service.assert_not_called()

    @patch("llm.views.build_llm_generation_service")
    def test_llm_generate_does_not_append_follow_up_when_user_prompt_blank(
        self, mock_build_service
    ):
        mock_service = mock_build_service.return_value
        mock_service.generate.return_value = {
            "headers": ["unit", "value"],
            "rows": [["ICU", 1000]],
        }
        session = Session.objects.create(owner=self.user, title="Existing Session")
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/llm/generate/",
            {
                "session_id": str(session.id),
                "input_json": {
                    "filename": "invoice.pdf",
                    "user_prompt": "   ",
                },
                "include_reasoning": False,
                "refinement": {"enabled": False},
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["session_id"], str(session.id))
        self.assertIsNone(response.data["chat_id"])
        self.assertEqual(
            ChatMessage.objects.filter(session=session, role=ChatMessage.ROLE_USER).count(),
            0,
        )

    @patch("llm.views.build_llm_generation_service")
    def test_llm_generate_updates_session_last_output_at(self, mock_build_service):
        mock_service = mock_build_service.return_value
        mock_service.generate.return_value = self.output_json
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/llm/generate/",
            {
                "input_json": {"filename": "invoice.pdf", "extracted": "raw upload text"},
                "refinement": {"enabled": False},
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        session = Session.objects.get(owner=self.user)
        self.assertIsNotNone(session.last_output_at)

    @patch("llm.views.build_llm_generation_service")
    def test_llm_generate_creates_multiple_outputs_for_same_session(self, mock_build_service):
        mock_service = mock_build_service.return_value
        mock_service.generate.return_value = self.output_json
        session = Session.objects.create(owner=self.user, title="Existing Session")
        self.client.force_authenticate(user=self.user)

        first_response = self.client.post(
            "/llm/generate/",
            {
                "input_json": {"filename": "invoice.pdf", "extracted": "raw upload text"},
                "session_id": str(session.id),
                "refinement": {"enabled": False},
            },
            format="json",
        )
        second_response = self.client.post(
            "/llm/generate/",
            {
                "input_json": {"filename": "invoice-2.pdf", "extracted": "raw upload text 2"},
                "session_id": str(session.id),
                "refinement": {"enabled": False},
            },
            format="json",
        )

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(GeneratedOutput.objects.filter(session=session).count(), 2)

    @patch("llm.views.create_generated_output")
    @patch("llm.views.build_llm_generation_service")
    def test_llm_generate_returns_500_and_rolls_back_when_output_persistence_fails(
        self, mock_build_service, mock_create_generated_output
    ):
        mock_service = mock_build_service.return_value
        mock_service.generate.return_value = self.output_json
        mock_create_generated_output.side_effect = RuntimeError("db write failed")
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/llm/generate/",
            {
                "input_json": {"filename": "invoice.pdf", "extracted": "raw upload text"},
                "refinement": {"enabled": False},
            },
            format="json",
        )

        self.assertEqual(response.status_code, 500)
        self.assertFalse(Session.objects.exists())
        self.assertFalse(GeneratedOutput.objects.exists())

    @patch("llm.views.build_llm_generation_service")
    def test_llm_generate_returns_404_for_unknown_owned_session_id(self, mock_build_service):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/llm/generate/",
            {
                "input_json": {"filename": "invoice.pdf", "extracted": "raw upload text"},
                "session_id": str(uuid4()),
                "refinement": {"enabled": False},
            },
            format="json",
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["detail"], "Session not found.")
        mock_build_service.assert_not_called()
        self.assertFalse(Session.objects.exists())
        self.assertFalse(GeneratedOutput.objects.exists())

    @patch("llm.views.build_llm_generation_service")
    def test_llm_generate_returns_404_for_session_owned_by_other_user(self, mock_build_service):
        other_user = User.objects.create_user(
            email="other-session-owner@example.com",
            name="Other Owner",
            password="secret",
            status="verified",
        )
        foreign_session = Session.objects.create(owner=other_user, title="Foreign Session")
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/llm/generate/",
            {
                "input_json": {"filename": "invoice.pdf", "extracted": "raw upload text"},
                "session_id": str(foreign_session.id),
                "refinement": {"enabled": False},
            },
            format="json",
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["detail"], "Session not found.")
        mock_build_service.assert_not_called()
        self.assertEqual(Session.objects.count(), 1)
        self.assertFalse(GeneratedOutput.objects.exists())

class ThinkingLogEndpointTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.verified_user = User.objects.create_user(
            email="thinking-log-owner@example.com",
            name="Thinking Log Owner",
            password="secret",
            status="verified",
        )
        self.unverified_user = User.objects.create_user(
            email="thinking-log-unverified@example.com",
            name="Thinking Log Unverified",
            password="secret",
            status="unverified",
        )
        self.other_user = User.objects.create_user(
            email="thinking-log-other@example.com",
            name="Thinking Log Other",
            password="secret",
            status="verified",
        )

    def _create_generated_output(self, owner, *, session=None, thinking_log, source_message=None):
        session = session or Session.objects.create(owner=owner, title="Thinking Log Session")
        return GeneratedOutput.objects.create(
            session=session,
            source_message=source_message,
            output_json={"source": "thinking-log-test"},
            thinking_log=thinking_log,
            created_at=timezone.now(),
        )

    def test_thinking_log_list_returns_filtered_records_for_owner(self):
        owned_session = Session.objects.create(owner=self.verified_user, title="Owned Session")
        other_session = Session.objects.create(owner=self.other_user, title="Other Session")

        owned_match = self._create_generated_output(
            self.verified_user,
            session=owned_session,
            thinking_log="Mapped invoice total to total_amount.",
        )
        owned_match_2 = self._create_generated_output(
            self.verified_user,
            session=owned_session,
            thinking_log="Normalized decimal separator handling.",
        )
        self._create_generated_output(
            self.verified_user,
            session=Session.objects.create(owner=self.verified_user, title="Owned Session 2"),
            thinking_log="Validated header consistency.",
        )
        self._create_generated_output(
            self.other_user,
            session=other_session,
            thinking_log="Other user log.",
        )

        self.client.force_authenticate(user=self.verified_user)
        response = self.client.get(f"/llm/thinking-logs/{owned_session.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 2)
        self.assertEqual(response.data["page"], 1)
        self.assertEqual(response.data["page_size"], 10)
        self.assertEqual(len(response.data["results"]), 2)
        result_ids = {item["id"] for item in response.data["results"]}
        self.assertSetEqual(result_ids, {str(owned_match.id), str(owned_match_2.id)})
        self.assertTrue(all(item["session_id"] == str(owned_session.id) for item in response.data["results"]))
        self.assertTrue(all(item["chat_id"] is None for item in response.data["results"]))
        self.assertTrue(all("request_id" not in item for item in response.data["results"]))
        self.assertTrue(all(item["reasoning"] == [] for item in response.data["results"]))

    def test_thinking_log_list_filters_by_chat_id_without_session_filter(self):
        matched_session = Session.objects.create(owner=self.verified_user, title="Matched Session")
        source_message = ChatMessage.objects.create(
            session=matched_session,
            role=ChatMessage.ROLE_USER,
            content="Refine this output.",
        )
        matched = self._create_generated_output(
            self.verified_user,
            session=matched_session,
            thinking_log="Request filtered record.",
            source_message=source_message,
        )
        self._create_generated_output(
            self.verified_user,
            session=Session.objects.create(owner=self.verified_user, title="Other Owned Session"),
            thinking_log="Non matching request.",
        )
        self._create_generated_output(
            self.other_user,
            session=Session.objects.create(owner=self.other_user, title="Other User Session"),
            thinking_log="Other owner record.",
        )

        self.client.force_authenticate(user=self.verified_user)
        response = self.client.get(f"/llm/thinking-logs/?chat_id={source_message.id}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["id"], str(matched.id))
        self.assertEqual(response.data["results"][0]["chat_id"], str(source_message.id))

    def test_thinking_log_list_filters_by_request_id_for_backward_compatibility(self):
        matched_session = Session.objects.create(owner=self.verified_user, title="Matched Session")
        matched = self._create_generated_output(
            self.verified_user,
            session=matched_session,
            thinking_log="Request ID filtered record.",
        )
        self._create_generated_output(
            self.verified_user,
            session=Session.objects.create(owner=self.verified_user, title="Other Owned Session"),
            thinking_log="Non matching request.",
        )
        self._create_generated_output(
            self.other_user,
            session=Session.objects.create(owner=self.other_user, title="Other User Session"),
            thinking_log="Other owner record.",
        )

        self.client.force_authenticate(user=self.verified_user)
        response = self.client.get(f"/llm/thinking-logs/?request_id={matched.id}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["id"], str(matched.id))

    def test_thinking_log_list_without_filters_returns_all_owned_records(self):
        owned_session_1 = Session.objects.create(owner=self.verified_user, title="Owned A")
        owned_session_2 = Session.objects.create(owner=self.verified_user, title="Owned B")
        other_session = Session.objects.create(owner=self.other_user, title="Other C")

        self._create_generated_output(
            self.verified_user,
            session=owned_session_1,
            thinking_log="Owned record A.",
        )
        self._create_generated_output(
            self.verified_user,
            session=owned_session_2,
            thinking_log="Owned record B.",
        )
        self._create_generated_output(
            self.other_user,
            session=other_session,
            thinking_log="Other owner record.",
        )

        self.client.force_authenticate(user=self.verified_user)
        response = self.client.get("/llm/thinking-logs/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 2)
        self.assertEqual(len(response.data["results"]), 2)

    def test_thinking_log_detail_returns_record_for_owner(self):
        session = Session.objects.create(owner=self.verified_user, title="Detail Session")
        record = self._create_generated_output(
            self.verified_user,
            session=session,
            thinking_log="Normalization notes for numeric columns.",
        )

        self.client.force_authenticate(user=self.verified_user)
        response = self.client.get(f"/llm/thinking-logs/output/{record.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], str(record.id))
        self.assertEqual(response.data["session_id"], str(session.id))
        self.assertIsNone(response.data["chat_id"])
        self.assertNotIn("request_id", response.data)
        self.assertEqual(
            response.data["thinking_log"],
            "Normalization notes for numeric columns.",
        )

    def test_thinking_log_detail_returns_404_when_not_found(self):
        self.client.force_authenticate(user=self.verified_user)

        response = self.client.get("/llm/thinking-logs/output/00000000-0000-0000-0000-000000000000/")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data, {"detail": "Thinking log not found."})

    def test_thinking_log_detail_blocks_access_to_other_user_record(self):
        foreign_session = Session.objects.create(owner=self.other_user, title="Foreign Session")
        foreign_record = self._create_generated_output(
            self.other_user,
            session=foreign_session,
            thinking_log="Foreign record.",
        )
        self.client.force_authenticate(user=self.verified_user)

        response = self.client.get(f"/llm/thinking-logs/output/{foreign_record.id}/")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data, {"detail": "Thinking log not found."})

    def test_thinking_log_detail_returns_404_for_empty_thinking_log_record(self):
        session = Session.objects.create(owner=self.verified_user, title="Empty Log Session")
        empty_log_record = self._create_generated_output(
            self.verified_user,
            session=session,
            thinking_log="",
        )

        self.client.force_authenticate(user=self.verified_user)
        response = self.client.get(f"/llm/thinking-logs/output/{empty_log_record.id}/")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data, {"detail": "Thinking log not found."})

    def test_thinking_log_list_supports_large_dataset_pagination(self):
        bulk_session = Session.objects.create(owner=self.verified_user, title="Bulk Session")
        for index in range(25):
            self._create_generated_output(
                self.verified_user,
                session=bulk_session,
                thinking_log=f"Summary item {index}",
            )

        self.client.force_authenticate(user=self.verified_user)
        response = self.client.get(f"/llm/thinking-logs/?session_id={bulk_session.id}&page=2&page_size=10")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 25)
        self.assertEqual(response.data["page"], 2)
        self.assertEqual(response.data["page_size"], 10)
        self.assertEqual(len(response.data["results"]), 10)

    def test_thinking_log_list_requires_authentication(self):
        response = self.client.get("/llm/thinking-logs/")

        self.assertEqual(response.status_code, 401)

    def test_thinking_log_list_returns_403_for_authenticated_unverified_user(self):
        self.client.force_authenticate(user=self.unverified_user)

        response = self.client.get("/llm/thinking-logs/")

        self.assertEqual(response.status_code, 403)

    def test_thinking_log_list_error_schema_is_consistent_for_invalid_pagination(self):
        self.client.force_authenticate(user=self.verified_user)

        response = self.client.get("/llm/thinking-logs/?page=0&page_size=10")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "Invalid request payload.")
        self.assertEqual(
            response.data["errors"],
            {"pagination": ["Invalid thinking log pagination request."]},
        )

    def test_thinking_log_session_list_error_schema_is_consistent_for_invalid_pagination(self):
        session = Session.objects.create(owner=self.verified_user, title="Owned Session")
        self.client.force_authenticate(user=self.verified_user)

        response = self.client.get(f"/llm/thinking-logs/{session.id}/?page=0&page_size=10")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "Invalid request payload.")
        self.assertEqual(
            response.data["errors"],
            {"pagination": ["Invalid thinking log pagination request."]},
        )

    def test_thinking_log_list_rejects_page_size_above_maximum(self):
        self.client.force_authenticate(user=self.verified_user)

        response = self.client.get("/llm/thinking-logs/?page_size=101")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "Invalid request payload.")
        self.assertEqual(
            response.data["errors"],
            {"pagination": ["Invalid thinking log pagination request."]},
        )

    def test_thinking_log_list_rejects_invalid_chat_id(self):
        self.client.force_authenticate(user=self.verified_user)

        response = self.client.get("/llm/thinking-logs/?chat_id=not-a-uuid")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "Invalid request payload.")
        self.assertEqual(
            response.data["errors"],
            {"chat_id": ["Invalid thinking log identifier."]},
        )

    def test_thinking_log_list_rejects_invalid_request_id(self):
        self.client.force_authenticate(user=self.verified_user)

        response = self.client.get("/llm/thinking-logs/?request_id=not-a-uuid")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "Invalid request payload.")
        self.assertEqual(
            response.data["errors"],
            {"request_id": ["Invalid thinking log identifier."]},
        )

class SendMessagePositiveTest(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="send-msg-pos@example.com",
            name="Send Message User",
            password="secret",
            status="verified",
        )

    @patch("llm.views.generate_chat_response")
    def test_send_message_returns_200_with_reply_and_session_id(self, mock_generate):
        mock_generate.return_value = "Halo! Ada yang bisa saya bantu?"
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/llm/send-message/",
            {"message": "Halo"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["reply"], "Halo! Ada yang bisa saya bantu?")
        self.assertIn("session_id", response.data)
        self.assertIn("chat_id", response.data)
        self.assertIsNotNone(response.data["session_id"])
        self.assertIsNotNone(response.data["chat_id"])

    @patch("llm.views.generate_chat_response")
    def test_send_message_creates_new_session_when_no_session_id_given(self, mock_generate):
        mock_generate.return_value = "ok"
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/llm/send-message/",
            {"message": "Halo"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        session_id = response.data["session_id"]
        self.assertTrue(Session.objects.filter(id=session_id, owner=self.user).exists())

    @patch("llm.views.generate_chat_response")
    def test_send_message_continues_existing_session(self, mock_generate):
        mock_generate.return_value = "Balasan lanjutan."
        session = Session.objects.create(owner=self.user)
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/llm/send-message/",
            {"session_id": str(session.id), "message": "Pesan lanjutan"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(str(response.data["session_id"]), str(session.id))

    @patch("llm.views.generate_chat_response")
    def test_send_message_persists_user_and_assistant_messages(self, mock_generate):
        mock_generate.return_value = "Balasan dari AI."
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/llm/send-message/",
            {"message": "Halo dari user"},
            format="json",
        )

        session_id = response.data["session_id"]
        chat_id = response.data["chat_id"]
        messages = list(
            ChatMessage.objects.filter(session_id=session_id).order_by("created_at")
        )
        self.assertEqual(len(messages), 2)
        self.assertEqual(str(messages[0].id), str(chat_id))
        self.assertEqual(messages[0].role, ChatMessage.ROLE_USER)
        self.assertEqual(messages[0].content, "Halo dari user")
        self.assertEqual(messages[1].role, ChatMessage.ROLE_ASSISTANT)
        self.assertEqual(messages[1].content, "Balasan dari AI.")

    @patch("llm.views.generate_chat_response")
    def test_send_message_attaches_target_output_to_user_message(self, mock_generate):
        mock_generate.return_value = "Balasan refine."
        session = Session.objects.create(owner=self.user)
        target_output = GeneratedOutput.objects.create(
            session=session,
            output_json={"content_data": []},
        )
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/llm/send-message/",
            {
                "session_id": str(session.id),
                "target_output_id": str(target_output.id),
                "message": "Refine output ini",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        user_message = ChatMessage.objects.get(id=response.data["chat_id"])
        self.assertEqual(user_message.target_output, target_output)

    @patch("llm.views.generate_chat_response")
    def test_send_message_uses_target_output_session_when_session_id_missing(self, mock_generate):
        mock_generate.return_value = "Balasan refine."
        session = Session.objects.create(owner=self.user)
        target_output = GeneratedOutput.objects.create(
            session=session,
            output_json={"content_data": []},
        )
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/llm/send-message/",
            {
                "target_output_id": str(target_output.id),
                "message": "Refine output ini",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(str(response.data["session_id"]), str(session.id))

    @patch("llm.views.generate_chat_response")
    def test_send_message_returns_404_for_unknown_target_output_id(self, mock_generate):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/llm/send-message/",
            {
                "target_output_id": str(uuid4()),
                "message": "Refine output ini",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 404)
        mock_generate.assert_not_called()

    @patch("llm.views.generate_chat_response")
    def test_send_message_returns_400_for_target_output_from_other_session(self, mock_generate):
        session = Session.objects.create(owner=self.user)
        other_session = Session.objects.create(owner=self.user)
        target_output = GeneratedOutput.objects.create(
            session=other_session,
            output_json={"content_data": []},
        )
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/llm/send-message/",
            {
                "session_id": str(session.id),
                "target_output_id": str(target_output.id),
                "message": "Refine output ini",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data["errors"]["target_output_id"],
            ["target_output_id must belong to the same session."],
        )
        mock_generate.assert_not_called()

    @patch("llm.views.generate_chat_response")
    def test_send_message_passes_full_history_to_llm(self, mock_generate):
        mock_generate.return_value = "Balasan baru."
        session = Session.objects.create(owner=self.user)
        ChatMessage.objects.create(
            session=session, role=ChatMessage.ROLE_USER, content="Pesan pertama"
        )
        ChatMessage.objects.create(
            session=session, role=ChatMessage.ROLE_ASSISTANT, content="Balasan pertama"
        )
        self.client.force_authenticate(user=self.user)

        self.client.post(
            "/llm/send-message/",
            {"session_id": str(session.id), "message": "Pesan kedua"},
            format="json",
        )

        mock_generate.assert_called_once_with([
            {"role": "user", "content": "Pesan pertama"},
            {"role": "assistant", "content": "Balasan pertama"},
            {"role": "user", "content": "Pesan kedua"},
        ])

    @patch("llm.views.SendMessageResponseSerializer")
    @patch("llm.views.generate_chat_response")
    def test_send_message_returns_502_when_response_serializer_invalid(
        self, mock_generate, mock_serializer_class
    ):
        mock_generate.return_value = "reply text"
        mock_serializer_class.return_value.is_valid.return_value = False
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/llm/send-message/",
            {"message": "Halo"},
            format="json",
        )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.data["detail"], "Failed to generate response from LLM provider.")


class SendMessageNegativeTest(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="send-msg-neg@example.com",
            name="Negative Test User",
            password="secret",
            status="verified",
        )

    def test_send_message_requires_authentication(self):
        response = self.client.post(
            "/llm/send-message/",
            {"message": "Halo"},
            format="json",
        )

        self.assertEqual(response.status_code, 401)

    @patch("llm.views.generate_chat_response")
    def test_send_message_returns_404_for_unknown_session_id(self, mock_generate):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/llm/send-message/",
            {"session_id": str(uuid4()), "message": "Halo"},
            format="json",
        )

        self.assertEqual(response.status_code, 404)
        mock_generate.assert_not_called()

    @patch("llm.views.generate_chat_response")
    def test_send_message_returns_404_for_session_owned_by_other_user(self, mock_generate):
        other_user = User.objects.create_user(
            email="other-user@example.com",
            name="Other User",
            password="secret",
            status="verified",
        )
        other_session = Session.objects.create(owner=other_user)
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/llm/send-message/",
            {"session_id": str(other_session.id), "message": "Halo"},
            format="json",
        )

        self.assertEqual(response.status_code, 404)
        mock_generate.assert_not_called()

    @patch("llm.views.generate_chat_response")
    def test_send_message_rejects_empty_payload(self, mock_generate):
        self.client.force_authenticate(user=self.user)

        response = self.client.post("/llm/send-message/", {}, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "Invalid request payload.")
        self.assertIn("errors", response.data)
        mock_generate.assert_not_called()

    @patch("llm.views.generate_chat_response")
    def test_send_message_rejects_missing_message(self, mock_generate):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/llm/send-message/",
            {"session_id": str(uuid4())},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "Invalid request payload.")
        self.assertIn("message", response.data["errors"])
        mock_generate.assert_not_called()

    @patch("llm.views.generate_chat_response")
    def test_send_message_rejects_blank_message(self, mock_generate):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/llm/send-message/",
            {"message": ""},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("message", response.data["errors"])
        mock_generate.assert_not_called()

    @patch("llm.views.generate_chat_response")
    def test_send_message_rejects_whitespace_only_message(self, mock_generate):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/llm/send-message/",
            {"message": "   "},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("message", response.data["errors"])
        mock_generate.assert_not_called()

    @patch("llm.views.generate_chat_response")
    def test_send_message_rejects_invalid_session_id_format(self, mock_generate):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/llm/send-message/",
            {"session_id": "not-a-valid-UUID", "message": "Halo"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "Invalid request payload.")
        self.assertIn("session_id", response.data["errors"])
        mock_generate.assert_not_called()

    def test_send_message_rejects_non_json_content_type(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/llm/send-message/",
            data="plain text",
            content_type="text/plain",
        )

        self.assertEqual(response.status_code, 415)
        self.assertEqual(response.data["detail"], "Content-Type must be application/json.")

    def test_send_message_rejects_get_method(self):
        response = self.client.get("/llm/send-message/")

        self.assertEqual(response.status_code, 405)
class SendMessageErrorHandlingTest(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="send-msg-err@example.com",
            name="Error Test User",
            password="secret",
            status="verified",
        )

    @patch("llm.views.generate_chat_response")
    def test_send_message_returns_503_when_openai_not_configured(self, mock_generate):
        mock_generate.side_effect = OpenAIConfigurationError("OPENAI_API_KEY is not configured.")
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/llm/send-message/",
            {"message": "Halo"},
            format="json",
        )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data["detail"], "Service unavailable. Please try again later.")

    @patch("llm.views.generate_chat_response")
    def test_send_message_returns_502_for_openai_service_error(self, mock_generate):
        mock_generate.side_effect = OpenAIServiceError("OpenAI response did not include a reply.")
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/llm/send-message/",
            {"message": "Halo"},
            format="json",
        )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.data["detail"], "Failed to generate response from LLM provider.")

    @patch("llm.views.generate_chat_response")
    def test_send_message_returns_502_for_upstream_auth_error(self, mock_generate):
        mock_generate.side_effect = OpenAIUpstreamError("LLM authentication failed.", status_code=502)
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/llm/send-message/",
            {"message": "Halo"},
            format="json",
        )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.data["detail"], "Failed to generate response from LLM provider.")

    @patch("llm.views.generate_chat_response")
    def test_send_message_returns_429_for_upstream_rate_limit(self, mock_generate):
        mock_generate.side_effect = OpenAIUpstreamError("LLM rate limit exceeded.", status_code=429)
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/llm/send-message/",
            {"message": "Halo"},
            format="json",
        )

        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.data["detail"], "Failed to generate response from LLM provider.")

    @patch("llm.views.generate_chat_response")
    def test_send_message_returns_504_for_upstream_timeout(self, mock_generate):
        mock_generate.side_effect = OpenAIUpstreamError("LLM request timed out.", status_code=504)
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/llm/send-message/",
            {"message": "Halo"},
            format="json",
        )

        self.assertEqual(response.status_code, 504)
        self.assertEqual(response.data["detail"], "Failed to generate response from LLM provider.")

    @patch("llm.views.logger")
    @patch("llm.views.generate_chat_response")
    def test_send_message_returns_500_for_unexpected_error(self, mock_generate, mock_logger):
        mock_generate.side_effect = RuntimeError("unexpected failure")
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/llm/send-message/",
            {"message": "Halo"},
            format="json",
        )

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.data["detail"], "Internal server error.")
        mock_logger.exception.assert_called_once()

    @patch("llm.views.generate_chat_response")
    def test_send_message_does_not_expose_upstream_error_details(self, mock_generate):
        mock_generate.side_effect = OpenAIUpstreamError("raw upstream details", status_code=502)
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/llm/send-message/",
            {"message": "Halo"},
            format="json",
        )

        self.assertEqual(response.status_code, 502)
        self.assertNotIn("raw upstream details", str(response.data))


class SendMessageEdgeCaseTest(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="send-msg-edge@example.com",
            name="Edge Case User",
            password="secret",
            status="verified",
        )

    @patch("llm.views.generate_chat_response")
    def test_send_message_at_max_length_is_accepted(self, mock_generate):
        mock_generate.return_value = "ok"
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/llm/send-message/",
            {"message": "a" * MAX_MESSAGE_LENGTH},
            format="json",
        )

        self.assertEqual(response.status_code, 200)

    @patch("llm.views.generate_chat_response")
    def test_send_message_exceeding_max_length_is_rejected(self, mock_generate):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/llm/send-message/",
            {"message": "a" * (MAX_MESSAGE_LENGTH + 1)},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "Invalid request payload.")
        self.assertIn("message", response.data["errors"])
        mock_generate.assert_not_called()

    @patch("llm.views.build_history_with_summary")
    @patch("llm.views.generate_chat_response")
    def test_send_message_passes_summary_history_to_llm(self, mock_generate, mock_build_summary):
        mock_generate.return_value = "reply"
        summarized_history = [
            {"role": "system", "content": "[Summary of earlier conversation]: Old context."},
            {"role": "user", "content": "new msg"},
        ]
        mock_build_summary.return_value = summarized_history
        session = Session.objects.create(owner=self.user)
        self.client.force_authenticate(user=self.user)

        self.client.post(
            "/llm/send-message/",
            {"session_id": str(session.id), "message": "new msg"},
            format="json",
        )

        mock_build_summary.assert_called_once()
        _, kwargs = mock_build_summary.call_args
        self.assertTrue(kwargs["allow_async_refresh"])
        mock_generate.assert_called_once_with(summarized_history)

class SendMessageSessionTitleGenerationTest(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="title-gen-send@example.com",
            name="Title Gen Send User",
            password="secret",
            status="verified",
        )

    @patch("llm.views.generate_session_title_from_message")
    @patch("llm.views.generate_chat_response")
    def test_send_message_generates_session_title_when_no_session_id_given(
        self,
        mock_generate,
        mock_generate_title,
    ):
        mock_generate.return_value = '{"reply": "Halo! Ada yang bisa saya bantu?", "title": "Diskusi Bantuan Excel"}'
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/llm/send-message/",
            {"message": "Halo tolong bantu saya excel"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        session_id = response.data["session_id"]
        
        session = Session.objects.get(id=session_id)
        self.assertEqual(session.title, "Diskusi Bantuan Excel")
        mock_generate.assert_called_once()
        mock_generate_title.assert_not_called()

    @patch("llm.views.generate_session_title_from_message")
    @patch("llm.views.generate_chat_response")
    def test_send_message_parses_json_with_markdown_blocks(
        self,
        mock_generate,
        mock_generate_title,
    ):
        mock_generate.return_value = '```json\n{"reply": "Halo dengan markdown", "title": "Sesi Markdown"}\n```'
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/llm/send-message/",
            {"message": "Halo"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["reply"], "Halo dengan markdown")
        session_id = response.data["session_id"]
        session = Session.objects.get(id=session_id)
        self.assertEqual(session.title, "Sesi Markdown")
        mock_generate.assert_called_once()
        mock_generate_title.assert_not_called()
        
    @patch("llm.views.generate_session_title_from_message")
    @patch("llm.views.generate_chat_response")
    def test_send_message_parses_json_with_generic_markdown_blocks(
        self,
        mock_generate,
        mock_generate_title,
    ):
        mock_generate.return_value = '```\n{"reply": "Halo dengan markdown generik", "title": "Sesi Generik"}\n```'
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/llm/send-message/",
            {"message": "Halo"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["reply"], "Halo dengan markdown generik")
        session_id = response.data["session_id"]
        session = Session.objects.get(id=session_id)
        self.assertEqual(session.title, "Sesi Generik")
        mock_generate.assert_called_once()
        mock_generate_title.assert_not_called()

    @patch("llm.views.generate_session_title_from_message")
    @patch("llm.views.generate_chat_response")
    def test_send_message_falls_back_to_new_chat_if_title_generation_fails(
        self,
        mock_generate,
        mock_generate_title,
    ):
        mock_generate.return_value = "Balasan aman"
        mock_generate_title.return_value = "New Chat"
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/llm/send-message/",
            {"message": "Halo"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["reply"], "Balasan aman")
        
        session_id = response.data["session_id"]
        session = Session.objects.get(id=session_id)
        self.assertEqual(session.title, "New Chat")
        mock_generate.assert_called_once()
        mock_generate_title.assert_called_once_with("Halo")


class LlmGenerateSessionTitleGenerationTest(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="title-gen-convert@example.com",
            name="Title Gen Convert User",
            password="secret",
            status="verified",
        )

    @patch("llm.views.build_llm_generation_service")
    def test_llm_generate_skips_llm_and_uses_filename_fallback_for_new_session(self, mock_build_service):
        mock_service = mock_build_service.return_value
        mock_service.generate.return_value = {"headers": ["A"], "rows": [["1"]]}
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/llm/generate/",
            {
                "input_json": {
                    "document_info": {"filename": "laporan_keuangan.pdf"}
                },
                "include_reasoning": False
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        session_id = response.data["session_id"]
        
        session = Session.objects.get(id=session_id)
        self.assertEqual(session.title, "Convert laporan_keuangan.pdf")


class SendMessageFileContextTest(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="send-msg-file@example.com",
            name="File Context User",
            password="secret",
            status="verified",
        )
        self.output_json = {
            "document_info": {"filename": "report.xlsx"},
            "summary": {"total_sheets": 2},
            "content_data": [{"table_name": "Sheet1", "headers": ["A"], "rows": [["1"]]}],
        }
        self.export_output_json = {
            "document_info": {"source_type": "Excel", "filename": "report.xlsx"},
            "summary": {"total_tables": 1, "total_rows": 1, "total_columns": 1},
            "content_data": [{"table_name": "Sheet1", "headers": ["A"], "rows": [["1"]]}],
        }

    def _create_output(self, session, filename="report.xlsx"):
        return GeneratedOutput.objects.create(
            session=session,
            output_json=self.output_json,
            export_output_json={
                **self.export_output_json,
                "document_info": {"source_type": "Excel", "filename": filename},
            },
        )

    @patch("llm.views.generate_chat_response")
    def test_send_message_injects_file_context_as_first_system_message(self, mock_generate):
        mock_generate.return_value = "ok"
        session = Session.objects.create(owner=self.user)
        self._create_output(session)
        self.client.force_authenticate(user=self.user)

        self.client.post(
            "/llm/send-message/",
            {"session_id": str(session.id), "message": "Apa isi file ini?"},
            format="json",
        )

        call_args = mock_generate.call_args[0][0]
        self.assertEqual(call_args[0]["role"], "system")
        self.assertIn("[CONVERTED_FILE_CONTEXT]", call_args[0]["content"])
        self.assertIn("report.xlsx", call_args[0]["content"])

    @patch("llm.views.generate_chat_response")
    def test_send_message_does_not_inject_file_context_when_no_generated_output(self, mock_generate):
        mock_generate.return_value = "ok"
        session = Session.objects.create(owner=self.user)
        self.client.force_authenticate(user=self.user)

        self.client.post(
            "/llm/send-message/",
            {"session_id": str(session.id), "message": "Halo"},
            format="json",
        )

        call_args = mock_generate.call_args[0][0]
        system_messages = [m for m in call_args if m.get("role") == "system"]
        self.assertEqual(len(system_messages), 0)

    @patch("llm.views.generate_chat_response")
    def test_send_message_uses_most_recent_generated_output(self, mock_generate):
        mock_generate.return_value = "ok"
        session = Session.objects.create(owner=self.user)
        self._create_output(session, filename="old_file.xlsx")
        self._create_output(session, filename="new_file.xlsx")
        self.client.force_authenticate(user=self.user)

        self.client.post(
            "/llm/send-message/",
            {"session_id": str(session.id), "message": "Apa isi file ini?"},
            format="json",
        )

        call_args = mock_generate.call_args[0][0]
        self.assertEqual(call_args[0]["role"], "system")
        self.assertIn("new_file.xlsx", call_args[0]["content"])
        self.assertNotIn("old_file.xlsx", call_args[0]["content"])
