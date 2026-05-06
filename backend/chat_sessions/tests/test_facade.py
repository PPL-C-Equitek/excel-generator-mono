from django.test import SimpleTestCase
from unittest.mock import Mock

from chat_sessions import default_session_facade
from chat_sessions.facade import SessionFacade, create_session_facade


class SessionFacadeTest(SimpleTestCase):
    def _build_facade(self):
        query_module = Mock()
        write_module = Mock()
        title_module = Mock()
        thinking_module = Mock()
        history_module = Mock()
        facade = SessionFacade(
            query_module=query_module,
            write_module=write_module,
            title_module=title_module,
            thinking_module=thinking_module,
            history_module=history_module,
        )
        return (
            facade,
            query_module,
            write_module,
            title_module,
            thinking_module,
            history_module,
        )

    def test_create_session_facade_returns_facade_instance(self):
        facade = create_session_facade()

        self.assertIsInstance(facade, SessionFacade)

    def test_default_session_facade_is_facade_instance(self):
        self.assertIsInstance(default_session_facade, SessionFacade)

    def test_query_methods_delegate_to_query_module(self):
        facade, query_module, _, _, _, _ = self._build_facade()
        query_module.list_sessions_for_user.return_value = ["session-a"]
        query_module.get_session_for_user.return_value = "session"

        listed = facade.list_sessions_for_user("user-id", limit=10, offset=4)
        fetched = facade.get_session_for_user("user-id", "session-id")

        query_module.list_sessions_for_user.assert_called_once_with(
            "user-id",
            limit=10,
            offset=4,
        )
        query_module.get_session_for_user.assert_called_once_with(
            "user-id",
            "session-id",
        )
        self.assertEqual(listed, ["session-a"])
        self.assertEqual(fetched, "session")

    def test_paginated_detail_delegates_to_query_module(self):
        facade, query_module, _, _, _, _ = self._build_facade()
        query_module.get_paginated_session_detail_for_user.return_value = "detail"

        result = facade.get_paginated_session_detail_for_user(
            "user-id",
            "session-id",
            messages_limit=15,
            messages_offset=2,
            outputs_limit=8,
            outputs_offset=1,
        )

        query_module.get_paginated_session_detail_for_user.assert_called_once_with(
            "user-id",
            "session-id",
            messages_limit=15,
            messages_offset=2,
            outputs_limit=8,
            outputs_offset=1,
        )
        self.assertEqual(result, "detail")

    def test_write_methods_delegate_to_write_module(self):
        facade, _, write_module, _, _, _ = self._build_facade()
        write_module.append_user_message.return_value = "user-message"
        write_module.append_assistant_message.return_value = "assistant-message"

        created_user_message = facade.append_user_message(
            "session-id",
            "hello",
            target_output="output-id",
        )
        created_assistant_message = facade.append_assistant_message(
            "session-id",
            "reply",
            thinking_log="summary",
        )

        write_module.append_user_message.assert_called_once_with(
            "session-id",
            "hello",
            target_output="output-id",
        )
        write_module.append_assistant_message.assert_called_once_with(
            "session-id",
            "reply",
            thinking_log="summary",
        )
        self.assertEqual(created_user_message, "user-message")
        self.assertEqual(created_assistant_message, "assistant-message")

    def test_create_generated_output_delegates_to_write_module(self):
        facade, _, write_module, _, _, _ = self._build_facade()
        write_module.create_generated_output.return_value = "generated-output"

        result = facade.create_generated_output(
            "session-id",
            {"payload": True},
            thinking_log="done",
            export_output_json={"document_info": {}},
            reasoning={"final_answer": "ok"},
            source_message="chat-id",
            parent_output="parent-id",
        )

        write_module.create_generated_output.assert_called_once_with(
            "session-id",
            {"payload": True},
            thinking_log="done",
            export_output_json={"document_info": {}},
            reasoning={"final_answer": "ok"},
            source_message="chat-id",
            parent_output="parent-id",
        )
        self.assertEqual(result, "generated-output")

    def test_title_methods_delegate_to_title_module(self):
        facade, _, _, title_module, _, _ = self._build_facade()
        title_module.sanitize_session_title.return_value = "clean"
        title_module.resolve_session_title.return_value = "resolved"
        title_module.generate_session_title_from_message.return_value = "generated"

        sanitized = facade.sanitize_session_title(" raw ")
        resolved = facade.resolve_session_title(" candidate ", fallback="fallback")
        generated = facade.generate_session_title_from_message(
            "hello world",
            fallback="fallback",
        )

        title_module.sanitize_session_title.assert_called_once_with(" raw ")
        title_module.resolve_session_title.assert_called_once_with(
            " candidate ",
            fallback="fallback",
        )
        title_module.generate_session_title_from_message.assert_called_once_with(
            "hello world",
            fallback="fallback",
        )
        self.assertEqual(sanitized, "clean")
        self.assertEqual(resolved, "resolved")
        self.assertEqual(generated, "generated")

    def test_thinking_log_method_delegates_to_thinking_module(self):
        facade, _, _, _, thinking_module, _ = self._build_facade()
        thinking_module.build_frontend_thinking_log_response.return_value = {
            "thinking_log": ["line"]
        }

        result = facade.build_frontend_thinking_log_response({"reasoning": {}})

        thinking_module.build_frontend_thinking_log_response.assert_called_once_with(
            {"reasoning": {}}
        )
        self.assertEqual(result, {"thinking_log": ["line"]})

    def test_history_method_delegates_to_history_module(self):
        facade, _, _, _, _, history_module = self._build_facade()
        history_module.build_history_with_summary.return_value = [{"role": "system"}]

        result = facade.build_history_with_summary("session-id", [{"role": "user"}])

        history_module.build_history_with_summary.assert_called_once_with(
            "session-id",
            [{"role": "user"}],
        )
        self.assertEqual(result, [{"role": "system"}])
