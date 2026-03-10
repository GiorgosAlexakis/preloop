"""Tests for audit utility (log_config_change)."""

from unittest.mock import MagicMock, patch

from sqlalchemy.orm import Session

from preloop.models.models.user import User
from preloop.utils.audit import log_config_change


class TestLogConfigChange:
    """Test log_config_change helper."""

    def test_log_config_change_no_audit_plugin_is_noop(self):
        """When EE audit plugin is absent, log_config_change does nothing."""
        mock_db = MagicMock(spec=Session)
        mock_user = MagicMock(spec=User)
        mock_user.account_id = "acc-123"

        with patch(
            "preloop.utils.audit._get_audit_service",
            return_value=None,
        ):
            log_config_change(
                mock_db,
                user=mock_user,
                config_type="mcp_server",
                action="created",
                new_value={"name": "test"},
            )
        mock_db.assert_not_called()

    def test_log_config_change_with_audit_plugin_calls_service(self):
        """When audit plugin exists, log_config_change delegates to it."""
        mock_db = MagicMock(spec=Session)
        mock_user = MagicMock(spec=User)
        mock_user.account_id = "acc-123"
        mock_service = MagicMock()

        with patch(
            "preloop.utils.audit._get_audit_service",
            return_value=mock_service,
        ):
            log_config_change(
                mock_db,
                user=mock_user,
                config_type="tool_rule",
                action="updated",
                old_value={"action": "deny"},
                new_value={"action": "allow"},
            )

        mock_service.log_configuration_change.assert_called_once()
        call_kw = mock_service.log_configuration_change.call_args[1]
        assert call_kw["account_id"] == "acc-123"
        assert call_kw["config_type"] == "tool_rule"
        assert call_kw["action"] == "updated"
        assert call_kw["old_value"] is not None
        assert call_kw["new_value"] is not None

    def test_log_config_change_redacts_sensitive_data(self):
        """log_config_change passes values through redact_dict."""
        mock_db = MagicMock(spec=Session)
        mock_user = MagicMock(spec=User)
        mock_user.account_id = "acc-123"
        mock_service = MagicMock()

        with patch(
            "preloop.utils.audit._get_audit_service",
            return_value=mock_service,
        ):
            log_config_change(
                mock_db,
                user=mock_user,
                config_type="mcp_server",
                action="created",
                new_value={"password": "secret123"},
            )

        call_kw = mock_service.log_configuration_change.call_args[1]
        # redact_dict should replace password with ***REDACTED***
        assert "***REDACTED***" in str(call_kw["new_value"])

    def test_log_config_change_exception_is_suppressed(self):
        """Exceptions from audit service are caught and logged (no raise)."""
        mock_db = MagicMock(spec=Session)
        mock_user = MagicMock(spec=User)
        mock_user.account_id = "acc-123"
        mock_service = MagicMock()
        mock_service.log_configuration_change.side_effect = RuntimeError("audit failed")

        with patch(
            "preloop.utils.audit._get_audit_service",
            return_value=mock_service,
        ):
            # Should not raise
            log_config_change(
                mock_db,
                user=mock_user,
                config_type="tool_rule",
                action="deleted",
            )
