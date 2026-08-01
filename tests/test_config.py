"""Unit tests for core.config."""

import os
import unittest
from unittest import mock


class TestConfig(unittest.TestCase):
    def test_env_int_parsing(self):
        """Test that integer env parsing works and falls back safely."""
        from core import config

        with mock.patch.dict(os.environ, {"API_ID": "42"}, clear=False):
            config.API_ID = config._env_int("API_ID", 0)
            self.assertEqual(config.API_ID, 42)

        with mock.patch.dict(os.environ, {"API_ID": "not-a-number"}, clear=False):
            config.API_ID = config._env_int("API_ID", 7)
            self.assertEqual(config.API_ID, 7)

    def test_env_bool_parsing(self):
        """Test that boolean env parsing accepts common truthy values."""
        from core import config

        for value in ("1", "true", "yes", "on", "TRUE"):
            with mock.patch.dict(os.environ, {"FLAG": value}, clear=False):
                self.assertTrue(config._env_bool("FLAG", False))

        for value in ("0", "false", "no", "off", ""):
            with mock.patch.dict(os.environ, {"FLAG": value}, clear=False):
                self.assertFalse(config._env_bool("FLAG", True))

    def test_validate_telethon_config_missing(self):
        """validate_telethon_config should raise when credentials are absent."""
        from core import config

        with mock.patch.object(config, "API_ID", 0), \
             mock.patch.object(config, "API_HASH", ""):
            with self.assertRaises(RuntimeError):
                config.validate_telethon_config()

    def test_validate_telethon_config_ok(self):
        """validate_telethon_config should pass with real credentials."""
        from core import config

        with mock.patch.object(config, "API_ID", 123), \
             mock.patch.object(config, "API_HASH", "abc"):
            config.validate_telethon_config()  # should not raise


if __name__ == "__main__":
    unittest.main()
