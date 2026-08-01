"""Unit tests for core.utils."""

import logging
import unittest


class TestRetry(unittest.TestCase):
    def test_retry_succeeds_on_first_attempt(self):
        """A callable that succeeds immediately should be called once."""
        from core.utils import retry

        calls = []

        def func():
            calls.append(1)
            return "ok"

        self.assertEqual(retry(func, retries=3, base_delay=0), "ok")
        self.assertEqual(len(calls), 1)

    def test_retry_retries_until_success(self):
        """A callable that fails twice should succeed on the third attempt."""
        from core.utils import retry

        calls = []

        def func():
            calls.append(1)
            if len(calls) < 3:
                raise ValueError("boom")
            return "recovered"

        result = retry(func, retries=3, base_delay=0)
        self.assertEqual(result, "recovered")
        self.assertEqual(len(calls), 3)

    def test_retry_gives_up_and_raises(self):
        """After exhausting retries, the last exception should propagate."""
        from core.utils import retry

        def func():
            raise RuntimeError("always fails")

        with self.assertRaises(RuntimeError):
            retry(func, retries=2, base_delay=0)


class TestGetLogger(unittest.TestCase):
    def test_logger_is_singleton_per_name(self):
        """get_logger should return the same instance for the same name."""
        from core.utils import get_logger

        self.assertIs(get_logger("test_logger"), get_logger("test_logger"))
        self.assertIsInstance(get_logger("test_logger"), logging.Logger)


if __name__ == "__main__":
    unittest.main()
