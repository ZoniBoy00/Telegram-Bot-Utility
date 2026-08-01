"""Unit tests for core.api."""

import os
import tempfile
import unittest
from unittest import mock


class TestMediaHelpers(unittest.TestCase):
    def test_is_gif(self):
        from core.api import is_gif

        self.assertTrue(is_gif("file.gif"))
        self.assertTrue(is_gif("file.GIF"))
        self.assertFalse(is_gif("file.jpg"))

    def test_is_image(self):
        from core.api import is_image

        self.assertTrue(is_image("photo.jpg"))
        self.assertTrue(is_image("photo.JPEG"))
        self.assertTrue(is_image("photo.png"))
        self.assertFalse(is_image("file.gif"))
        self.assertFalse(is_image("file.pdf"))


class TestErrorExtraction(unittest.TestCase):
    def test_extract_error_details_json(self):
        from core.api import extract_error_details

        response = mock.Mock()
        response.json.return_value = {"description": "Bad Request: chat not found"}
        self.assertEqual(
            extract_error_details(response),
            "Bad Request: chat not found",
        )

    def test_extract_error_details_fallback(self):
        from core.api import extract_error_details

        response = mock.Mock()
        response.json.side_effect = ValueError("no json")
        response.text = "plain text error"
        self.assertEqual(extract_error_details(response), "plain text error")


class TestRateLimit(unittest.TestCase):
    def test_handle_rate_limit_429(self):
        from core.api import handle_rate_limit

        response = mock.Mock()
        response.status_code = 429
        response.json.return_value = {"ok": False, "retry_after": 42}
        self.assertEqual(handle_rate_limit(response), 42.0)

    def test_handle_rate_limit_non_429(self):
        from core.api import handle_rate_limit

        response = mock.Mock()
        response.status_code = 400
        self.assertIsNone(handle_rate_limit(response))


class TestRequestWithRetry(unittest.TestCase):
    @mock.patch("core.api.requests.request")
    def test_success_first_attempt(self, mock_request):
        from core.api import request_with_retry

        response = mock.Mock()
        response.status_code = 200
        mock_request.return_value = response

        result = request_with_retry("GET", "http://example.com")
        self.assertIs(result, response)
        mock_request.assert_called_once()

    @mock.patch("core.api.time.sleep")
    @mock.patch("core.api.requests.request")
    def test_flood_wait_retried(self, mock_request, mock_sleep):
        from core.api import request_with_retry

        rate_limited = mock.Mock()
        rate_limited.status_code = 429
        rate_limited.json.return_value = {"retry_after": 5}
        ok = mock.Mock()
        ok.status_code = 200

        mock_request.side_effect = [rate_limited, ok]

        result = request_with_retry("GET", "http://example.com")
        self.assertIs(result, ok)
        self.assertEqual(mock_request.call_count, 2)
        mock_sleep.assert_called()

    @mock.patch("core.api.time.sleep")
    @mock.patch("core.api.requests.request")
    def test_flood_wait_exhausted_returns_last(self, mock_request, mock_sleep):
        from core.api import API_RETRY_ATTEMPTS, request_with_retry

        rate_limited = mock.Mock()
        rate_limited.status_code = 429
        rate_limited.json.return_value = {"retry_after": 60}

        mock_request.return_value = rate_limited

        result = request_with_retry("GET", "http://example.com")
        self.assertIs(result, rate_limited)
        self.assertEqual(mock_request.call_count, API_RETRY_ATTEMPTS)


class TestDownloadImage(unittest.TestCase):
    def _run(self, response, url):
        """Run download_image with a fake response and an isolated temp dir."""
        from core.api import download_image

        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch("core.api.DOWNLOAD_DIR", tmp):
                with mock.patch("core.api.requests.get", return_value=response):
                    with mock.patch("core.api.open", mock.mock_open()):
                        return download_image(url), tmp

    def test_download_image_rejects_html(self):
        fake_response = mock.Mock()
        fake_response.headers = {"Content-Type": "text/html", "Content-Length": "5"}
        fake_response.raise_for_status.return_value = None

        result, _ = self._run(fake_response, "http://example.com/not_an_image")
        self.assertIsNone(result)

    def test_download_image_oversized(self):
        fake_response = mock.Mock()
        fake_response.headers = {"Content-Type": "image/jpeg", "Content-Length": "999999999"}
        fake_response.raise_for_status.return_value = None
        fake_response.iter_content.return_value = iter([b"x" * 1024])

        result, _ = self._run(fake_response, "http://example.com/huge.jpg")
        self.assertIsNone(result)

    def test_download_image_success(self):
        fake_response = mock.Mock()
        fake_response.headers = {"Content-Type": "image/jpeg", "Content-Length": "6"}
        fake_response.raise_for_status.return_value = None
        fake_response.iter_content.return_value = iter([b"123456"])

        result, tmp = self._run(fake_response, "http://example.com/photo.jpg")

        # Downloaded into the temp DOWNLOAD_DIR, not the working directory.
        self.assertEqual(result, os.path.join(tmp, "photo.jpg"))


class TestResolveChatId(unittest.TestCase):
    @mock.patch("core.api.requests.request")
    def test_numeric_id_passes_through(self, mock_request):
        from core.api import resolve_chat_id

        result = resolve_chat_id("123:abc", "456")
        self.assertEqual(result, 456)
        mock_request.assert_not_called()

    @mock.patch("core.api.requests.request")
    def test_username_resolved(self, mock_request):
        from core.api import resolve_chat_id

        response = mock.Mock()
        response.status_code = 200
        response.raise_for_status.return_value = None
        response.json.return_value = {"ok": True, "result": {"id": -100123456789}}
        mock_request.return_value = response

        result = resolve_chat_id("123:abc", "@my_channel")
        self.assertEqual(result, -100123456789)
        # getChat should be called WITHOUT the @-prefix (it causes a 400)
        _, kwargs = mock_request.call_args
        self.assertEqual(kwargs["params"], {"chat_id": "my_channel"})

    @mock.patch("core.api.requests.request")
    def test_plain_username_normalized(self, mock_request):
        from core.api import resolve_chat_id

        response = mock.Mock()
        response.status_code = 200
        response.raise_for_status.return_value = None
        response.json.return_value = {"ok": True, "result": {"id": 42}}
        mock_request.return_value = response

        result = resolve_chat_id("123:abc", "my_channel")
        self.assertEqual(result, 42)
        _, kwargs = mock_request.call_args
        self.assertEqual(kwargs["params"], {"chat_id": "my_channel"})

    @mock.patch("core.api.requests.request")
    def test_failure_returns_none(self, mock_request):
        import requests

        from core.api import resolve_chat_id

        response = mock.Mock()
        response.raise_for_status.side_effect = requests.exceptions.HTTPError("boom")
        mock_request.return_value = response

        self.assertIsNone(resolve_chat_id("123:abc", "@ghost"))


class _FakeProgress:
    """Minimal Progress stand-in that renders nothing."""

    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def add_task(self, description, total):
        return 0

    def advance(self, task_id):
        pass


class TestSendFunctions(unittest.TestCase):
    @mock.patch("core.api.request_with_retry")
    def test_send_text_message(self, mock_req):
        from core.api import TELEGRAM_API_BASE, send_text_message

        mock_req.return_value = mock.Mock(status_code=200)
        send_text_message(f"{TELEGRAM_API_BASE}123:abc/", 456, "hi")

        mock_req.assert_called_once()
        args, kwargs = mock_req.call_args
        self.assertEqual(args[0], "POST")
        self.assertIn("sendMessage", args[1])
        self.assertEqual(kwargs["data"], {"chat_id": 456, "text": "hi"})


class TestSpamSummary(unittest.TestCase):
    """Verify the send summary counts successes and failures correctly."""

    def _run_spam(self, responses, count):
        import re

        from core import api

        with mock.patch.object(api, "Progress", _FakeProgress):
            with mock.patch.object(api.time, "sleep"):
                with mock.patch.object(api, "request_with_retry", side_effect=responses):
                    with mock.patch.object(api.console, "print") as mock_print:
                        api.spam_with_token("tok", 123, "hi", count, 0.1)
        texts = " ".join(
            str(call[0][0]) for call in mock_print.call_args_list if call and call[0]
        )
        # Strip Rich markup tags for plain-text assertions
        return re.sub(r"\[/?[a-z]*\]", "", texts)

    def test_all_success(self):
        ok = mock.Mock()
        ok.status_code = 200
        texts = self._run_spam([ok, ok, ok], 3)
        self.assertIn("Result:", texts)
        self.assertIn("3/3 sent", texts)
        self.assertIn("0 failed", texts)

    def test_mixed_results(self):
        ok = mock.Mock()
        ok.status_code = 200
        fail = mock.Mock()
        fail.status_code = 429
        fail.json.return_value = {"description": "Too Many Requests"}
        fail.text = ""
        texts = self._run_spam([ok, fail, ok], 3)
        self.assertIn("2/3 sent", texts)
        self.assertIn("1 failed", texts)
        self.assertIn("Too Many Requests", texts)


class TestListChats(unittest.TestCase):
    @mock.patch("core.api.api_get")
    def test_list_chats_parses_messages_and_channel_posts(self, mock_get):
        from core.api import list_chats

        response = mock.Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"result": [
            {"message": {"chat": {"id": 1, "first_name": "Alice", "type": "private"}}},
            {"channel_post": {"chat": {"id": -100, "title": "Chan", "type": "channel"}}},
        ]}
        mock_get.return_value = response

        chats = list_chats("tok")
        self.assertEqual(chats, {
            1: {"title": "Alice", "type": "private"},
            -100: {"title": "Chan", "type": "channel"},
        })

    @mock.patch("core.api.api_get")
    def test_list_chats_empty(self, mock_get):
        from core.api import list_chats

        response = mock.Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"result": []}
        mock_get.return_value = response

        self.assertIsNone(list_chats("tok"))


class TestParseChatTarget(unittest.TestCase):
    def test_plain_username(self):
        from core.api import parse_chat_target

        self.assertEqual(parse_chat_target("my_channel"), "my_channel")

    def test_at_username(self):
        from core.api import parse_chat_target

        self.assertEqual(parse_chat_target("@my_channel"), "@my_channel")

    def test_tme_link(self):
        from core.api import parse_chat_target

        self.assertEqual(parse_chat_target("https://t.me/my_channel"), "my_channel")

    def test_tme_link_with_query(self):
        from core.api import parse_chat_target

        self.assertEqual(parse_chat_target("t.me/my_channel?start=123"), "my_channel")

    def test_numeric_id(self):
        from core.api import parse_chat_target

        self.assertEqual(parse_chat_target("1375693542"), "1375693542")


class TestGetChatInfo(unittest.TestCase):
    @mock.patch("core.api.api_get")
    def test_returns_chat_result(self, mock_get):
        from core.api import get_chat_info

        response = mock.Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"ok": True, "result": {"id": 123, "type": "private"}}
        mock_get.return_value = response

        info = get_chat_info("tok", "@someone")
        self.assertEqual(info["id"], 123)
        _, kwargs = mock_get.call_args
        self.assertEqual(kwargs["params"], {"chat_id": "someone"})

    @mock.patch("core.api.api_get")
    def test_empty_result_returns_none(self, mock_get):
        from core.api import get_chat_info

        response = mock.Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"ok": True, "result": None}
        mock_get.return_value = response

        self.assertIsNone(get_chat_info("tok", "@ghost"))

    def test_empty_target(self):
        from core.api import get_chat_info

        self.assertIsNone(get_chat_info("tok", "   "))


class TestSendMediaMessage(unittest.TestCase):
    def test_send_media_message_too_large(self):
        from core.api import MEDIA_MAX_SIZE, send_media_message

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp.write(b"x" * 1000)
            tmp_path = tmp.name

        try:
            with mock.patch.object(os.path, "getsize", return_value=MEDIA_MAX_SIZE + 1):
                with self.assertRaises(ValueError):
                    send_media_message("http://base/", 123, "cap", tmp_path)
        finally:
            os.remove(tmp_path)


class TestFetchUpdates(unittest.TestCase):
    @mock.patch("core.api.api_get")
    def test_passes_offset_param(self, mock_get):
        from core.api import fetch_updates

        response = mock.Mock()
        response.status_code = 200
        response.raise_for_status.return_value = None
        response.json.return_value = {"result": [{"update_id": 10}]}
        mock_get.return_value = response

        result = fetch_updates("tok", offset=5)
        self.assertEqual(result, [{"update_id": 10}])
        _, kwargs = mock_get.call_args
        self.assertEqual(kwargs["params"], {"limit": 100, "timeout": 0, "offset": 5})

    @mock.patch("core.api.api_get")
    def test_conflict_returns_empty(self, mock_get):
        from core.api import fetch_updates

        response = mock.Mock()
        response.status_code = 409
        mock_get.return_value = response

        with mock.patch("core.api.print_warning") as mock_warn:
            result = fetch_updates("tok")

        self.assertEqual(result, [])
        mock_warn.assert_called_once()

    @mock.patch("core.api.api_get")
    def test_confirm_updates_returns_next_offset(self, mock_get):
        from core.api import confirm_updates

        response = mock.Mock()
        response.status_code = 200
        mock_get.return_value = response

        offset = confirm_updates("tok", [{"update_id": 5}, {"update_id": 7}])
        self.assertEqual(offset, 8)
        _, kwargs = mock_get.call_args
        self.assertEqual(kwargs["params"], {"offset": 8, "limit": 1})

    def test_confirm_updates_empty(self):
        from core.api import confirm_updates

        self.assertIsNone(confirm_updates("tok", []))


if __name__ == "__main__":
    unittest.main()
