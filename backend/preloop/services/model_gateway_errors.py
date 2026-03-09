"""Provider-native error envelopes for model gateway endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Optional


GatewayProvider = Literal["openai", "anthropic"]


def _default_error_type(provider: GatewayProvider, status_code: int) -> str:
    if provider == "anthropic":
        if status_code == 400:
            return "invalid_request_error"
        if status_code == 401:
            return "authentication_error"
        if status_code == 403:
            return "permission_error"
        if status_code == 404:
            return "not_found_error"
        if status_code == 429:
            return "rate_limit_error"
        if status_code == 529:
            return "overloaded_error"
        return "api_error"

    if status_code == 400:
        return "invalid_request_error"
    if status_code == 401:
        return "authentication_error"
    if status_code == 403:
        return "permission_error"
    if status_code == 404:
        return "not_found_error"
    if status_code == 429:
        return "rate_limit_error"
    return "api_error"


@dataclass
class ModelGatewayAPIError(Exception):
    """Model gateway exception rendered in the target client format."""

    provider: GatewayProvider
    status_code: int
    message: str
    error_type: Optional[str] = None
    param: Optional[str] = None
    code: Optional[str] = None

    def __post_init__(self) -> None:
        super().__init__(self.message)
        if not self.error_type:
            self.error_type = _default_error_type(self.provider, self.status_code)

    def to_payload(self) -> dict[str, Any]:
        """Return the provider-native error response body."""
        if self.provider == "anthropic":
            return {
                "type": "error",
                "error": {
                    "type": self.error_type,
                    "message": self.message,
                },
            }

        error_payload: dict[str, Any] = {
            "message": self.message,
            "type": self.error_type,
            "param": self.param,
            "code": self.code,
        }
        return {"error": error_payload}
