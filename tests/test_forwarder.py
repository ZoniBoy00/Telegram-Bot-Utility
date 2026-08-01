"""Unit tests for core.forwarder."""

import unittest
from unittest import mock


class TestTelegramFormatting(unittest.TestCase):
    def setUp(self):
        from core.forwarder import MessageForwarder
        self.forwarder = MessageForwarder()

    def test_format_telegram_message_basic(self):
        msg = {
            'chat_type': 'Private',
            'from_id': '111',
            'chat_id': '111',
            'date': '2026-08-01 12:00:00',
            'text': 'Hello world',
        }
        formatted = self.forwarder._format_telegram_message(msg)
        self.assertIn('Private', formatted)
        self.assertIn('111', formatted)
        self.assertIn('Hello world', formatted)

    def test_format_telegram_message_with_media(self):
        msg = {
            'chat_type': 'Channel',
            'from_id': '222',
            'chat_id': '-100123',
            'date': '2026-08-01 12:00:00',
            'text': '',
            'media_type': 'photos',
        }
        formatted = self.forwarder._format_telegram_message(msg)
        self.assertIn('photos', formatted)

    def test_format_telegram_message_empty_fields(self):
        formatted = self.forwarder._format_telegram_message({})
        self.assertIn('Unknown', formatted)


class TestDiscordEmbed(unittest.TestCase):
    def setUp(self):
        from core.forwarder import MessageForwarder
        self.forwarder = MessageForwarder()

    def test_embed_color_mapping(self):
        msg = {'chat_type': 'Group', 'from_id': '1', 'chat_id': '2', 'date': 'x', 'text': 'hi'}
        embed = self.forwarder._create_discord_embed(msg)
        self.assertEqual(embed['color'], 0x2ecc71)

    def test_embed_unknown_type_color(self):
        msg = {'chat_type': 'Unknown', 'from_id': '1', 'chat_id': '2', 'date': 'x'}
        embed = self.forwarder._create_discord_embed(msg)
        self.assertEqual(embed['color'], 0x95a5a6)

    def test_embed_text_truncation(self):
        msg = {'chat_type': 'Private', 'from_id': '1', 'chat_id': '2', 'date': 'x', 'text': 'a' * 5000}
        embed = self.forwarder._create_discord_embed(msg)
        self.assertLessEqual(len(embed['description']), 4005)  # 4000 + "..."
        self.assertTrue(embed['description'].endswith("..."))

    def test_embed_media_url(self):
        msg = {'chat_type': 'Private', 'from_id': '1', 'chat_id': '2', 'date': 'x'}
        embed = self.forwarder._create_discord_embed(msg, media_url="https://example.com/x.jpg")
        self.assertEqual(embed['image']['url'], "https://example.com/x.jpg")


class TestSetupValidation(unittest.TestCase):
    def test_discord_setup_rejects_invalid_url(self):
        from core.forwarder import MessageForwarder
        forwarder = MessageForwarder()
        forwarder.setup_discord_forwarding("https://example.com/not-a-webhook")
        self.assertFalse(forwarder.discord_enabled)

    def test_telegram_setup_prefixes_channel_id(self):
        from core.forwarder import MessageForwarder
        forwarder = MessageForwarder()
        bot = mock.Mock()
        forwarder.setup_telegram_forwarding(bot, "123456789")
        self.assertEqual(forwarder.telegram_channel_id, -100123456789)
        self.assertTrue(forwarder.telegram_enabled)

    def test_telegram_setup_accepts_full_id(self):
        from core.forwarder import MessageForwarder
        forwarder = MessageForwarder()
        bot = mock.Mock()
        forwarder.setup_telegram_forwarding(bot, "-100123456789")
        self.assertEqual(forwarder.telegram_channel_id, -100123456789)

    def test_telegram_setup_rejects_invalid(self):
        from core.forwarder import MessageForwarder
        forwarder = MessageForwarder()
        bot = mock.Mock()
        forwarder.setup_telegram_forwarding(bot, "not-a-number")
        self.assertFalse(forwarder.telegram_enabled)


class TestMarkdownEscape(unittest.TestCase):
    def setUp(self):
        from core.forwarder import MessageForwarder
        self.forwarder = MessageForwarder()

    def test_escape_markdown_characters(self):
        escaped = self.forwarder._escape_markdown("a *b* _c_ [d] `e` f\\g")
        self.assertNotIn(" *", escaped)
        self.assertIn(r"\*", escaped)
        self.assertIn(r"\_", escaped)
        self.assertIn(r"\[", escaped)
        self.assertIn(r"\`", escaped)
        self.assertIn(r"\\", escaped)

    def test_escape_leaves_plain_text(self):
        escaped = self.forwarder._escape_markdown("plain text 123")
        self.assertEqual(escaped, "plain text 123")

    def test_format_message_escapes_user_text(self):
        msg = {
            'chat_type': 'Private',
            'from_id': '1',
            'chat_id': '2',
            'date': 'x',
            'text': 'price is 10*20 and _underscore_',
        }
        formatted = self.forwarder._format_telegram_message(msg)
        self.assertIn(r"\*", formatted)
        self.assertIn(r"\_", formatted)


if __name__ == "__main__":
    unittest.main()
