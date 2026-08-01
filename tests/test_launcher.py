"""Unit tests for core.launcher argument parsing."""

import unittest


class TestLauncherArgs(unittest.TestCase):
    def test_parse_args_minimal(self):
        from core.launcher import parse_args

        args = parse_args(["123:abc"])
        self.assertEqual(args.bot_token, "123:abc")
        self.assertFalse(args.listen_only)
        self.assertIsNone(args.chat)

    def test_parse_args_full(self):
        from core.launcher import parse_args

        args = parse_args([
            "123:abc",
            "--listen-only",
            "--telegram-channel", "-100123",
            "--discord-webhook", "https://discord.com/api/webhooks/x",
            "--chat", "456",
            "--history-limit", "500",
            "--proxy", "127.0.0.1:1080",
        ])
        self.assertTrue(args.listen_only)
        self.assertEqual(args.telegram_channel, "-100123")
        self.assertEqual(args.chat, "456")
        self.assertEqual(args.history_limit, 500)
        self.assertEqual(args.proxy, "127.0.0.1:1080")


class TestParseProxy(unittest.TestCase):
    def test_parse_proxy_valid(self):
        from core.launcher import SOCKS_AVAILABLE, parse_proxy

        if not SOCKS_AVAILABLE:
            self.skipTest("PySocks not installed")

        proxy = parse_proxy("127.0.0.1:1080")
        self.assertIsNotNone(proxy)
        self.assertEqual(proxy[1], "127.0.0.1")
        self.assertEqual(proxy[2], 1080)

    def test_parse_proxy_invalid(self):
        from core.launcher import parse_proxy

        self.assertIsNone(parse_proxy("not-a-proxy"))


if __name__ == "__main__":
    unittest.main()
