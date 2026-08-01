"""Unit tests for core.cli user flows (inputs mocked)."""

import unittest
from unittest import mock


class TestAskToken(unittest.TestCase):
    def setUp(self):
        from core import cli

        cli._session_tokens.clear()

    def test_env_token_used_directly(self):
        from core import cli
        from core.config import BOT_TOKEN

        if not BOT_TOKEN:
            self.skipTest("BOT_TOKEN not set in environment")

        with mock.patch.object(cli, "validate_input") as mock_input:
            token = cli.ask_token()

        self.assertEqual(token, BOT_TOKEN)
        mock_input.assert_not_called()  # never prompted

    def test_new_token_stored_in_session(self):
        from core import cli

        with mock.patch.object(cli, "validate_input", return_value="123:ABC"):
            token = cli.ask_token()

        self.assertEqual(token, "123:ABC")
        self.assertIn("123:ABC", cli._session_tokens)

    def test_previous_token_offered(self):
        from core import cli

        cli._session_tokens.append("999:XYZ")
        with mock.patch.object(cli, "validate_input", return_value=1):
            token = cli.ask_token()

        self.assertEqual(token, "999:XYZ")

    def test_session_keeps_at_most_five(self):
        from core import cli

        cli._session_tokens.extend(["t1", "t2", "t3", "t4", "t5"])
        inputs = iter([0, "t6"])  # 0 = enter a new token, then the token itself
        with mock.patch.object(cli, "validate_input", side_effect=lambda *a, **k: next(inputs)):
            cli.ask_token()

        self.assertLessEqual(len(cli._session_tokens), 5)
        self.assertIn("t6", cli._session_tokens)


class TestAskMessageComposition(unittest.TestCase):
    def test_cancel_with_no_does_not_send(self):
        from core import cli

        inputs = iter(["hello", 3, 1.0, "", "n"])
        with mock.patch.object(cli, "validate_input", side_effect=lambda *a, **k: next(inputs)):
            with mock.patch.object(cli, "download_image", return_value=None):
                with mock.patch.object(cli, "spam_with_token") as mock_spam:
                    cli.ask_message_composition("tok", "chat", 123)

        mock_spam.assert_not_called()

    def test_confirm_sends_with_correct_args(self):
        from core import cli

        inputs = iter(["hello", 3, 1.0, "", "y"])
        with mock.patch.object(cli, "validate_input", side_effect=lambda *a, **k: next(inputs)):
            with mock.patch.object(cli, "download_image", return_value=None):
                with mock.patch.object(cli, "spam_with_token") as mock_spam:
                    cli.ask_message_composition("tok", "chat", 123)

        mock_spam.assert_called_once_with("tok", 123, "hello", 3, 1.0, None)

    def test_empty_confirmation_defaults_to_no(self):
        from core import cli

        inputs = iter(["hi", 1, 0.5, "", ""])
        with mock.patch.object(cli, "validate_input", side_effect=lambda *a, **k: next(inputs)):
            with mock.patch.object(cli, "download_image", return_value=None):
                with mock.patch.object(cli, "spam_with_token") as mock_spam:
                    cli.ask_message_composition("tok", "chat", 123)

        mock_spam.assert_not_called()


class TestHandleSendMessages(unittest.TestCase):
    def test_flow_resolves_chat_and_composes(self):
        from core import cli

        with mock.patch.object(cli, "ask_token", return_value="tok"):
            with mock.patch.object(cli, "ask_target_chat", return_value=456):
                with mock.patch.object(cli, "ask_message_composition") as mock_comp:
                    cli.handle_send_messages()

        mock_comp.assert_called_once_with("tok", "chat 456", 456)


if __name__ == "__main__":
    unittest.main()
