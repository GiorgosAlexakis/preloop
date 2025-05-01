"""Tests for the CLI module."""

import unittest
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from spacesync.cli.scan_commands import scan


class TestScanCommands(unittest.TestCase):
    """Test the scan commands."""

    def setUp(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

    @patch("time.sleep") # Patch time.sleep globally for this test
    @patch("spacesync.cli.scan_commands.BackgroundScheduler")
    @patch("spacesync.cli.scan_commands.get_db_session")
    def test_scan_all(self, mock_get_db, mock_scheduler_cls, mock_sleep):
        """Test scan_all command starts the service and shuts down gracefully."""
        # Setup mocks
        mock_db = MagicMock()
        mock_get_db.return_value.__next__.return_value = mock_db

        # Mock the scheduler instance and its methods
        mock_scheduler_instance = MagicMock()
        mock_scheduler_cls.return_value = mock_scheduler_instance
        mock_scheduler_instance.start.return_value = None # Don't hang
        mock_scheduler_instance.running = True # Ensure the shutdown condition passes

        # Mock sleep's side effect to modify the actual keep_running flag
        # in the scan_commands module after a couple of calls.
        # This simulates the signal handler setting the flag to False.
        def sleep_side_effect(*args):
            import spacesync.cli.scan_commands # Import module where flag lives
            if mock_sleep.call_count >= 2:
                # Modify the flag in the module to stop the loop
                spacesync.cli.scan_commands.keep_running = False
            return None # time.sleep returns None

        mock_sleep.side_effect = sleep_side_effect

        # IMPORTANT: Reset keep_running flag before running the test
        # to ensure it starts as True for the while loop.
        import spacesync.cli.scan_commands
        spacesync.cli.scan_commands.keep_running = True

        # Run the Click command
        with self.runner.isolated_filesystem():
            result = self.runner.invoke(scan, ["all", "--max-workers", "1", "--reload-interval", "1"])

            # Check setup calls
            mock_scheduler_cls.assert_called_once()
            mock_scheduler_instance.start.assert_called_once()
            mock_scheduler_instance.add_job.assert_called_once()

            # Check cleanup calls
            mock_db.close.assert_called_once() # From finally block
            # Check that the scheduler's shutdown was called (via the atexit handler)
            mock_scheduler_instance.shutdown.assert_called_once()

            # Check exit code and output for graceful shutdown
            self.assertEqual(result.exit_code, 0)
            self.assertIn("Starting SpaceSync service", result.output)
            self.assertIn("SpaceSync service stopped", result.output)
            # We can also check sleep was called at least twice
            self.assertGreaterEqual(mock_sleep.call_count, 2)

    @patch("spacesync.cli.scan_commands.scan_account")
    @patch("spacesync.cli.scan_commands.crud_account")
    @patch("spacesync.cli.scan_commands.get_db_session")
    def test_scan_account_cmd(self, mock_get_db, mock_crud_account, mock_scan_account):
        """Test scan_account_cmd command."""
        # Setup mocks
        mock_db = MagicMock()
        mock_get_db.return_value.__next__.return_value = mock_db

        # The account must exist for the command to succeed
        mock_account = MagicMock()
        mock_account.id = "test-account-id"
        mock_account.username = "test-user"
        mock_crud_account.get.return_value = mock_account

        # Mock the scan_account function
        mock_scan_account.return_value = {
            "trackers_scanned": 2,
            "trackers_with_errors": 0,
            "organizations": 1,
            "projects": 3,
            "issues": 25,
            "embeddings_updated": 10,
            "duration_seconds": 5.2,
        }

        # Run the command
        with self.runner.isolated_filesystem():
            result = self.runner.invoke(scan, ["account", "test-account-id"])

            # Print result to debug
            if result.exit_code != 0:
                print(f"Command failed with: {result.output}")

            # We expect the command to succeed
            self.assertEqual(result.exit_code, 0)

            # Verify our mock was called with the account ID
            # Assert call includes db, account_id, verbose=False, force_update=False
            mock_scan_account.assert_called_once_with(mock_db, "test-account-id", False, False)

    @patch("spacesync.cli.scan_commands.scan_tracker_func")
    @patch("spacesync.cli.scan_commands.crud_tracker")
    @patch("spacesync.cli.scan_commands.get_db_session")
    def test_scan_tracker_cmd(
        self, mock_get_db, mock_crud_tracker, mock_scan_tracker_func
    ):
        """Test scan_tracker_cmd command."""
        # Setup mocks
        mock_db = MagicMock()
        mock_get_db.return_value.__next__.return_value = mock_db

        # The tracker must exist for the command to succeed
        mock_tracker = MagicMock()
        mock_tracker.id = "test-tracker-id"
        mock_tracker.name = "Test Tracker"
        mock_tracker.tracker_type = "github"
        mock_crud_tracker.get.return_value = mock_tracker

        # Mock the scan_tracker_func
        mock_scan_tracker_func.return_value = {
            "organizations": 1,
            "projects": 3,
            "issues": 25,
            "embeddings_updated": 10,
            "errors": 0,
            "duration_seconds": 5.2,
        }

        # Run the command
        with self.runner.isolated_filesystem():
            result = self.runner.invoke(scan, ["tracker", "test-tracker-id"])

            # Print result to debug
            if result.exit_code != 0:
                print(f"Command failed with: {result.output}")

            # We expect the command to succeed
            self.assertEqual(result.exit_code, 0)

            # Verify our mock was called with the tracker
            # Assert call includes db, tracker object, verbose=False, force_update=False
            mock_scan_tracker_func.assert_called_once_with(mock_db, mock_tracker, False, False)
