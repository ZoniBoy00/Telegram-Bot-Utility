"""Unit tests for core.dumper helpers (works without Telethon installed)."""

import os
import shutil
import tempfile
import unittest
import zipfile
from datetime import datetime, timedelta
from unittest import mock


class FakeMessage:
    """Minimal stand-in for a Telethon Message object."""

    def __init__(self, chat_id, sender_id, msg_id):
        self.chat_id = chat_id
        self.sender_id = sender_id
        self.id = msg_id


class TestChatIdHelpers(unittest.TestCase):
    def test_get_chat_id_from_property(self):
        from core.dumper import BotDumper

        msg = FakeMessage(chat_id=123, sender_id=123, msg_id=1)
        self.assertEqual(BotDumper.get_chat_id(msg), "123")

    def test_get_chat_id_fallback_zero(self):
        from core.dumper import BotDumper

        msg = mock.Mock()
        del msg.chat_id
        self.assertEqual(BotDumper.get_chat_id(msg), "0")

    def test_get_from_id(self):
        from core.dumper import BotDumper

        msg = FakeMessage(chat_id=456, sender_id=789, msg_id=2)
        self.assertEqual(BotDumper.get_from_id(msg), "789")


class TestDocumentFilename(unittest.TestCase):
    """Uses real Telethon types; skip gracefully if Telethon is missing."""

    @classmethod
    def setUpClass(cls):
        try:
            from telethon.tl.types import (
                DocumentAttributeAudio,
                DocumentAttributeFilename,
            )
        except ImportError:
            cls.skipTest(cls, "Telethon not installed")

        cls.FilenameAttr = DocumentAttributeFilename
        cls.AudioAttr = DocumentAttributeAudio

    def _make_doc(self, attributes, mime_type=None, doc_id="doc1"):
        """Build a minimal object exposing attributes/id/mime_type."""
        return mock.Mock(attributes=attributes, mime_type=mime_type, id=doc_id)

    def test_filename_attribute_wins(self):
        from core.dumper import BotDumper

        attr = self.FilenameAttr(file_name="report.pdf")
        doc = self._make_doc([attr], mime_type="application/pdf")
        self.assertEqual(BotDumper.get_document_filename(doc), "report.pdf")

    def test_audio_uses_id_and_extension(self):
        from core.dumper import BotDumper

        attr = self.AudioAttr(duration=5, voice=False)
        doc = self._make_doc([attr], mime_type="audio/ogg", doc_id="55")
        self.assertEqual(BotDumper.get_document_filename(doc), "55.ogg")

    def test_no_attributes_falls_back_to_id(self):
        from core.dumper import BotDumper

        doc = self._make_doc([], mime_type=None, doc_id="99")
        self.assertEqual(BotDumper.get_document_filename(doc), "99")


class TestDefaultStats(unittest.TestCase):
    def test_default_stats_shape(self):
        from core.dumper import BotDumper

        stats = BotDumper._default_stats()
        self.assertIn('gifs', stats)
        self.assertIn('stickers', stats)
        self.assertIn('messages', stats)
        self.assertIn('locations', stats)


class TestIncrementalZip(unittest.TestCase):
    """Verify create_chat_zip only archives files modified since last zip."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.base = os.path.join(self.tmp, "base")
        os.makedirs(self.base)
        self.chat_dir = os.path.join(self.base, "123")
        os.makedirs(os.path.join(self.chat_dir, "media", "photos"), exist_ok=True)

        # Old file: modified long ago (already archived)
        self.old_file = os.path.join(self.chat_dir, "old.txt")
        with open(self.old_file, "w", encoding="utf-8") as f:
            f.write("old")
        old_time = (datetime.now() - timedelta(days=1)).timestamp()
        os.utime(self.old_file, (old_time, old_time))

        # New file: modified just now (should be included)
        self.new_file = os.path.join(self.chat_dir, "new.txt")
        with open(self.new_file, "w", encoding="utf-8") as f:
            f.write("new")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _make_dumper(self, last_zip_time):
        from collections import deque

        from core.dumper import BotDumper

        dumper = BotDumper.__new__(BotDumper)
        dumper.base_path = self.base
        dumper.last_zip_time = {"123": last_zip_time}
        dumper.log_buffer = deque(maxlen=10)
        dumper.live = None
        return dumper

    def test_only_new_files_archived(self):

        last_zip = datetime.now() - timedelta(hours=1)
        dumper = self._make_dumper(last_zip)

        zip_path = dumper.create_chat_zip("123")
        self.assertIsNotNone(zip_path)

        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()

        self.assertIn("123/new.txt", names)
        self.assertNotIn("123/old.txt", names)

    def test_no_changes_returns_none(self):

        # last zip "in the future" so nothing is newer
        last_zip = datetime.now() + timedelta(hours=1)
        dumper = self._make_dumper(last_zip)

        zip_path = dumper.create_chat_zip("123")
        self.assertIsNone(zip_path)


class TestHandleCommand(unittest.TestCase):
    """Keyboard command handling (P/C/S/Q) without needing Telethon."""

    def _make_dumper(self):
        from core.dumper import BotDumper

        dumper = BotDumper.__new__(BotDumper)
        dumper.bot = mock.Mock()
        dumper._paused = mock.Mock()
        dumper.log_buffer = __import__("collections").deque(maxlen=10)
        dumper.live = None
        dumper.stats = {}
        dumper.messages_by_chat = {}
        dumper.all_users = {}
        dumper.total_messages_processed = 0
        return dumper

    def test_pause_toggles(self):
        import asyncio

        dumper = self._make_dumper()

        # The Event must be created inside a running loop so this works on
        # Python 3.9 (asyncio.Event() outside a loop raises there).
        async def scenario():
            dumper._paused = asyncio.Event()
            dumper._paused.set()
            await dumper.handle_command("p")
            paused = dumper._paused.is_set()
            await dumper.handle_command("p")
            resumed = dumper._paused.is_set()
            return paused, resumed

        paused, resumed = asyncio.run(scenario())
        self.assertFalse(paused)   # now paused
        self.assertTrue(resumed)   # resumed

    def test_quit_disconnects(self):
        import asyncio

        dumper = self._make_dumper()
        dumper.bot.disconnect = mock.AsyncMock()
        asyncio.run(dumper.handle_command("q"))
        dumper.bot.disconnect.assert_awaited_once()

    def test_clear_clears_buffer(self):
        import asyncio

        dumper = self._make_dumper()
        dumper.log_buffer.append("line1")
        asyncio.run(dumper.handle_command("c"))
        self.assertEqual(len(dumper.log_buffer), 0)


class TestAccessSummary(unittest.TestCase):
    """Access classification for the dump access report (chat-type based)."""

    def test_private_full_history(self):
        from core.dumper import BotDumper

        chat_type, access = BotDumper._access_summary("private")
        self.assertEqual(chat_type, "DM")
        self.assertIn("full", access)

    def test_group_limited(self):
        from core.dumper import BotDumper

        chat_type, access = BotDumper._access_summary("group")
        self.assertEqual(chat_type, "Group")
        self.assertIn("after join", access)

    def test_supergroup_limited(self):
        from core.dumper import BotDumper

        chat_type, access = BotDumper._access_summary("supergroup")
        self.assertEqual(chat_type, "Supergroup")
        self.assertIn("after join", access)

    def test_channel_needs_admin(self):
        from core.dumper import BotDumper

        chat_type, access = BotDumper._access_summary("channel")
        self.assertEqual(chat_type, "Channel")
        self.assertIn("admin", access)

    def test_unknown_type(self):
        from core.dumper import BotDumper

        chat_type, access = BotDumper._access_summary("mystery")
        self.assertIn("unknown", access)


if __name__ == "__main__":
    unittest.main()
