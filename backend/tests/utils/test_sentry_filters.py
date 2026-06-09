"""Tests for GlitchTip/Sentry benign-event filtering."""

from starlette.websockets import WebSocketDisconnect

from preloop.utils.sentry_filters import sentry_before_send, should_drop_sentry_event


class TestSentryFilters:
    def test_drops_unclosed_aiohttp_session_warning(self) -> None:
        event = {
            "message": "Unclosed client session client_session: <aiohttp...>",
        }
        assert should_drop_sentry_event(event) is True
        assert sentry_before_send(event, {}) is None

    def test_drops_websocket_disconnect(self) -> None:
        event = {"message": "disconnect"}
        hint = {
            "exc_info": (
                WebSocketDisconnect,
                WebSocketDisconnect(1012),
                None,
            )
        }
        assert should_drop_sentry_event(event, hint) is True

    def test_drops_transient_database_disconnect(self) -> None:
        class OperationalError(Exception):
            pass

        event = {"message": "db error"}
        hint = {
            "exc_info": (
                OperationalError,
                OperationalError("SSL connection has been closed unexpectedly"),
                None,
            )
        }
        assert should_drop_sentry_event(event, hint) is True

    def test_keeps_unexpected_runtime_error(self) -> None:
        event = {"message": "Unhandled failure in billing webhook"}
        hint = {"exc_info": (RuntimeError, RuntimeError("boom"), None)}
        assert should_drop_sentry_event(event, hint) is False
        assert sentry_before_send(event, hint) == event
