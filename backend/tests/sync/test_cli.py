"""Tests for the CLI module."""

import unittest
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from preloop.sync.cli.scan_commands import scan


class TestScanCommands(unittest.TestCase):
    """Test the scan commands."""

    def setUp(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

    @patch("preloop.sync.cli.scan_commands.scan_all_accounts")
    @patch("preloop.sync.cli.scan_commands.get_db_session")
    def test_scan_all_sync(self, mock_get_db, mock_scan_all_accounts):
        """Test scan all command runs synchronously and prints stats."""
        # Setup mocks
        mock_db = MagicMock()
        mock_get_db.return_value.__next__.return_value = mock_db  # Use generator style

        # Mock the return value of the core scan function
        mock_stats = {
            "accounts_scanned": 3,
            "accounts_with_errors": 1,
            "trackers_scanned": 10,
            "trackers_with_errors": 2,
            "organizations": {
                "total": 5,
                "processed": 5,
                "skipped_webhook": 0,
                "skipped_polling": 0,
                "errors": 0,
            },
            "projects": 20,
            "issues": 150,
            "embeddings_updated": 75,
            "duration_seconds": 35.8,
        }
        mock_scan_all_accounts.return_value = mock_stats

        # Run the Click command
        with self.runner.isolated_filesystem():
            # Invoke without scheduler-specific args like --reload-interval
            result = self.runner.invoke(scan, ["all"])

            # Print result to debug if failed
            if result.exit_code != 0:
                print(f"Command failed with output:\n{result.output}")
                print(f"Exception:\n{result.exception}")

            # Check exit code
            self.assertEqual(
                result.exit_code, 0, msg=f"Command failed: {result.output}"
            )

            # Check that the core scan function was called correctly
            # Check that the core scan function was called correctly
            # The actual call uses the result of __next__ for the db session
            mock_scan_all_accounts.assert_called_once_with(
                db=mock_db, verbose=False, force_update=False
            )

            # Check that the database session context manager was used
            mock_get_db.assert_called_once()
            # Removed: mock_db.close.assert_not_called() - db.close() is called explicitly

            # Check for expected statistics in the output
            self.assertIn(
                "=== Scan Complete ===", result.output
            )  # Match actual output format
            self.assertIn("Accounts scanned: 3", result.output)
            self.assertIn("Accounts with errors: 1", result.output)
            self.assertIn("Trackers scanned: 10", result.output)  # Check total count
            self.assertIn("Trackers with errors: 2", result.output)
            self.assertIn("Organizations: 5", result.output)
            self.assertIn("Projects: 20", result.output)  # Corrected assertion
            self.assertIn("Issues: 150", result.output)  # Corrected assertion
            self.assertIn("Embeddings updated: 75", result.output)

    @patch("preloop.sync.cli.scan_commands.scan_all_accounts")
    @patch("preloop.sync.cli.scan_commands.get_db_session")
    def test_scan_all_sync_verbose(self, mock_get_db, mock_scan_all_accounts):
        """Test scan all command with --verbose flag."""
        mock_db = MagicMock()
        mock_get_db.return_value.__next__.return_value = mock_db  # Use generator style
        # Provide default stats keys expected by the command's print logic
        mock_stats = {
            "accounts_scanned": 0,
            "accounts_with_errors": 0,
            "trackers_scanned": 0,
            "trackers_with_errors": 0,
            "organizations": {
                "total": 0,
                "processed": 0,
                "skipped_webhook": 0,
                "skipped_polling": 0,
                "errors": 0,
            },
            "projects": 0,
            "issues": 0,
            "embeddings_updated": 0,
            "duration_seconds": 0.0,
        }
        mock_scan_all_accounts.return_value = mock_stats

        with self.runner.isolated_filesystem():
            result = self.runner.invoke(scan, ["all", "--verbose"])

            self.assertEqual(
                result.exit_code, 0, msg=f"Command failed: {result.output}"
            )
            mock_scan_all_accounts.assert_called_once_with(
                db=mock_db, verbose=True, force_update=False
            )
            self.assertIn(
                "=== Scan Complete ===", result.output
            )  # Match actual output format

    @patch("preloop.sync.cli.scan_commands.scan_all_accounts")
    @patch("preloop.sync.cli.scan_commands.get_db_session")
    def test_scan_all_sync_force_update(self, mock_get_db, mock_scan_all_accounts):
        """Test scan all command with --force-update flag."""
        mock_db = MagicMock()
        mock_get_db.return_value.__next__.return_value = mock_db  # Use generator style
        # Provide default stats keys expected by the command's print logic
        mock_stats = {
            "accounts_scanned": 0,
            "accounts_with_errors": 0,
            "trackers_scanned": 0,
            "trackers_with_errors": 0,
            "organizations": {
                "total": 0,
                "processed": 0,
                "skipped_webhook": 0,
                "skipped_polling": 0,
                "errors": 0,
            },
            "projects": 0,
            "issues": 0,
            "embeddings_updated": 0,
            "duration_seconds": 0.0,
        }
        mock_scan_all_accounts.return_value = mock_stats

        with self.runner.isolated_filesystem():
            result = self.runner.invoke(scan, ["all", "--force-update"])

            self.assertEqual(
                result.exit_code, 0, msg=f"Command failed: {result.output}"
            )
            mock_scan_all_accounts.assert_called_once_with(
                db=mock_db, verbose=False, force_update=True
            )
            self.assertIn(
                "=== Scan Complete ===", result.output
            )  # Match actual output format

    @patch("preloop.sync.cli.scan_commands.scan_account")
    @patch("preloop.sync.cli.scan_commands.crud_account")
    @patch("preloop.sync.cli.scan_commands.get_db_session")
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
            "trackers": 2,
            "organizations": {
                "total": 1,
                "processed": 1,
                "skipped_webhook": 0,
                "skipped_polling": 0,
                "errors": 0,
            },
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
            mock_scan_account.assert_called_once_with(
                db=mock_db,
                account_id="test-account-id",
                verbose=False,
                force_update=False,
            )

    @patch("preloop.sync.cli.scan_commands.scan_tracker_func")
    @patch("preloop.sync.cli.scan_commands.crud_tracker")
    @patch("preloop.sync.cli.scan_commands.get_db_session")
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
            "organizations": {
                "total": 1,
                "processed": 1,
                "skipped_webhook": 0,
                "skipped_polling": 0,
                "errors": 0,
            },
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
                print(f"Exception: {result.exception}")

            # We expect the command to succeed
            self.assertEqual(result.exit_code, 0)

            # Verify our mock was called with the tracker
            # Assert call includes db, tracker object, verbose=False, force_update=False
            mock_scan_tracker_func.assert_called_once_with(
                db=mock_db, tracker=mock_tracker, verbose=False, force_update=False
            )
