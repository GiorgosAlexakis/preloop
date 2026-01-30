"""Tests for approval_policy_service.py.

Tests for default approval policy creation service functions.
"""

import logging
from unittest.mock import MagicMock, patch
from uuid import uuid4


from preloop.services.approval_policy_service import (
    create_default_approval_policy_for_account,
    create_default_approval_policy_background,
)


class TestCreateDefaultApprovalPolicyForAccount:
    """Test create_default_approval_policy_for_account function."""

    @patch("preloop.services.approval_policy_service.get_session_factory")
    @patch("preloop.services.approval_policy_service.crud_approval_policy")
    def test_creates_default_policy_when_none_exist(
        self, mock_crud, mock_session_factory
    ):
        """Test that a default policy is created when no policies exist."""
        # Arrange
        account_id = uuid4()
        user_id = uuid4()
        mock_db = MagicMock()
        mock_session_factory.return_value = MagicMock(return_value=mock_db)

        # No existing default policy
        mock_crud.get_default.return_value = None
        # No existing policies at all
        mock_crud.get_multi_by_account.return_value = []

        # Act
        create_default_approval_policy_for_account(account_id, user_id)

        # Assert
        mock_crud.create.assert_called_once()
        call_args = mock_crud.create.call_args
        assert call_args.args[0] == mock_db
        assert call_args.kwargs["account_id"] == str(account_id)

        obj_in = call_args.kwargs["obj_in"]
        assert obj_in["name"] == "Default Approval Policy"
        assert obj_in["is_default"] is True
        assert obj_in["approvals_required"] == 1
        assert obj_in["approver_user_ids"] == [str(user_id)]

        mock_db.close.assert_called_once()

    @patch("preloop.services.approval_policy_service.get_session_factory")
    @patch("preloop.services.approval_policy_service.crud_approval_policy")
    def test_creates_policy_without_approver_when_user_id_none(
        self, mock_crud, mock_session_factory
    ):
        """Test that policy is created without approver when user_id is None."""
        # Arrange
        account_id = uuid4()
        mock_db = MagicMock()
        mock_session_factory.return_value = MagicMock(return_value=mock_db)

        mock_crud.get_default.return_value = None
        mock_crud.get_multi_by_account.return_value = []

        # Act
        create_default_approval_policy_for_account(account_id, user_id=None)

        # Assert
        mock_crud.create.assert_called_once()
        call_args = mock_crud.create.call_args
        obj_in = call_args.kwargs["obj_in"]
        assert "approver_user_ids" not in obj_in

    @patch("preloop.services.approval_policy_service.get_session_factory")
    @patch("preloop.services.approval_policy_service.crud_approval_policy")
    def test_skips_when_default_policy_exists(self, mock_crud, mock_session_factory):
        """Test that creation is skipped when default policy already exists."""
        # Arrange
        account_id = uuid4()
        mock_db = MagicMock()
        mock_session_factory.return_value = MagicMock(return_value=mock_db)

        # Existing default policy
        mock_crud.get_default.return_value = MagicMock()

        # Act
        create_default_approval_policy_for_account(account_id)

        # Assert
        mock_crud.create.assert_not_called()
        mock_db.close.assert_called_once()

    @patch("preloop.services.approval_policy_service.get_session_factory")
    @patch("preloop.services.approval_policy_service.crud_approval_policy")
    def test_skips_when_any_policies_exist(self, mock_crud, mock_session_factory):
        """Test that creation is skipped when any policies exist for the account."""
        # Arrange
        account_id = uuid4()
        mock_db = MagicMock()
        mock_session_factory.return_value = MagicMock(return_value=mock_db)

        # No default policy
        mock_crud.get_default.return_value = None
        # But other policies exist
        mock_crud.get_multi_by_account.return_value = [MagicMock()]

        # Act
        create_default_approval_policy_for_account(account_id)

        # Assert
        mock_crud.create.assert_not_called()
        mock_db.close.assert_called_once()

    @patch("preloop.services.approval_policy_service.get_session_factory")
    @patch("preloop.services.approval_policy_service.crud_approval_policy")
    def test_handles_exception_gracefully(
        self, mock_crud, mock_session_factory, caplog
    ):
        """Test that exceptions are logged but not raised."""
        # Arrange
        account_id = uuid4()
        mock_db = MagicMock()
        mock_session_factory.return_value = MagicMock(return_value=mock_db)

        mock_crud.get_default.side_effect = Exception("Database error")

        # Act - should not raise
        with caplog.at_level(logging.ERROR):
            create_default_approval_policy_for_account(account_id)

        # Assert
        assert "Failed to create default approval policy" in caplog.text
        mock_db.close.assert_called_once()

    @patch("preloop.services.approval_policy_service.get_session_factory")
    @patch("preloop.services.approval_policy_service.crud_approval_policy")
    def test_closes_session_on_exception(self, mock_crud, mock_session_factory):
        """Test that database session is closed even when exception occurs."""
        # Arrange
        account_id = uuid4()
        mock_db = MagicMock()
        mock_session_factory.return_value = MagicMock(return_value=mock_db)

        mock_crud.get_default.side_effect = Exception("Database error")

        # Act
        create_default_approval_policy_for_account(account_id)

        # Assert
        mock_db.close.assert_called_once()


class TestCreateDefaultApprovalPolicyBackground:
    """Test create_default_approval_policy_background function."""

    @patch(
        "preloop.services.approval_policy_service.create_default_approval_policy_for_account"
    )
    def test_calls_create_function(self, mock_create_func):
        """Test that background task calls the main creation function."""
        # Arrange
        account_id = uuid4()
        user_id = uuid4()

        # Act
        create_default_approval_policy_background(account_id, user_id)

        # Assert
        mock_create_func.assert_called_once_with(account_id, user_id)

    @patch(
        "preloop.services.approval_policy_service.create_default_approval_policy_for_account"
    )
    def test_handles_exception_silently(self, mock_create_func, caplog):
        """Test that exceptions in background task are logged but not raised."""
        # Arrange
        account_id = uuid4()
        mock_create_func.side_effect = Exception("Background task error")

        # Act - should not raise
        with caplog.at_level(logging.ERROR):
            create_default_approval_policy_background(account_id)

        # Assert
        assert "Background task failed" in caplog.text

    @patch(
        "preloop.services.approval_policy_service.create_default_approval_policy_for_account"
    )
    def test_passes_none_user_id_correctly(self, mock_create_func):
        """Test that None user_id is passed correctly."""
        # Arrange
        account_id = uuid4()

        # Act
        create_default_approval_policy_background(account_id, user_id=None)

        # Assert
        mock_create_func.assert_called_once_with(account_id, None)
