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

    @patch("spacesync.cli.scan_commands.scan_all_accounts")
    @patch("spacesync.cli.scan_commands.get_db_session")
    def test_scan_all(self, mock_get_db, mock_scan_all_accounts):
        """Test scan_all command."""
        # Setup mocks
        mock_db = MagicMock()
        mock_get_db.return_value.__next__.return_value = mock_db
        mock_scan_all_accounts.return_value = {
            "accounts_scanned": 2,
            "accounts_with_errors": 0,
            "trackers_scanned": 5,
            "trackers_with_errors": 1,
        }

        # Run the Click command in isolated mode to avoid affecting real system
        with self.runner.isolated_filesystem():
            result = self.runner.invoke(scan, ["all", "--verbose"])

            # Print result to debug
            if result.exit_code != 0:
                print(f"Command failed with: {result.output}")

            # We expect the command to succeed
            self.assertEqual(result.exit_code, 0)

            # Verify our mock was called
            mock_scan_all_accounts.assert_called_once()

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
            mock_scan_account.assert_called_once_with(mock_db, "test-account-id", False)

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
            mock_scan_tracker_func.assert_called_once_with(mock_db, mock_tracker, False)
