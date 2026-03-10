"""Tests for sync.utils module."""

import sys
from unittest.mock import patch

import pytest

from preloop.sync.utils import retry, safe_exit


class TestRetry:
    """Test retry decorator."""

    def test_success_first_attempt(self):
        """Function succeeds on first attempt."""

        @retry(max_attempts=3)
        def succeed():
            return 42

        assert succeed() == 42

    def test_succeeds_on_second_attempt(self):
        """Function succeeds after one failure."""
        attempts = []

        @retry(max_attempts=3, backoff_factor=0.01)
        def flaky():
            attempts.append(1)
            if len(attempts) < 2:
                raise ValueError("fail")
            return "ok"

        assert flaky() == "ok"
        assert len(attempts) == 2

    def test_raises_after_max_attempts(self):
        """Function raises after max attempts exceeded."""

        @retry(max_attempts=3, backoff_factor=0.01)
        def always_fail():
            raise RuntimeError("always fails")

        with pytest.raises(RuntimeError, match="always fails"):
            always_fail()

    def test_only_retries_specified_exceptions(self):
        """Only specified exceptions trigger retry."""

        @retry(max_attempts=2, backoff_factor=0.01, exceptions=(ValueError,))
        def raise_type_error():
            raise TypeError("wrong type")

        with pytest.raises(TypeError, match="wrong type"):
            raise_type_error()


class TestSafeExit:
    """Test safe_exit function."""

    def test_exits_with_code(self):
        """safe_exit calls sys.exit with given code."""
        with patch.object(sys, "exit") as mock_exit:
            safe_exit(exit_code=1)
            mock_exit.assert_called_once_with(1)

    def test_exits_with_message(self):
        """safe_exit logs message and exits when message provided."""
        with patch.object(sys, "exit") as mock_exit:
            with patch("preloop.sync.utils.logger") as mock_logger:
                safe_exit(exit_code=2, message="Error occurred")
                mock_logger.error.assert_called_once_with("Error occurred")
                mock_exit.assert_called_once_with(2)

    def test_exits_without_message_no_log(self):
        """safe_exit exits without logging when no message."""
        with patch.object(sys, "exit") as mock_exit:
            with patch("preloop.sync.utils.logger") as mock_logger:
                safe_exit(exit_code=0)
                mock_logger.error.assert_not_called()
                mock_exit.assert_called_once_with(0)
