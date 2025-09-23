from unittest.mock import patch, MagicMock
from pathlib import Path
import httpx
from spacebridge.api import ssr


@patch("builtins.open")
@patch("httpx.Client")
def test_render_app_success(mock_client, mock_open):
    """
    Tests the render_app method for a successful render.
    """
    mock_open.return_value.__enter__.return_value.read.return_value = (
        '<div id="app"></div>'
    )
    mock_response = MagicMock()
    mock_response.json.return_value = {"html": "<h1>Hello</h1>"}
    mock_client.return_value.__enter__.return_value.post.return_value = mock_response

    service = ssr.SSRService(Path("."))
    result = service.render_app("/")
    assert "<h1>Hello</h1>" in result


@patch("builtins.open")
@patch("httpx.Client")
def test_render_app_request_error(mock_client, mock_open):
    """
    Tests the render_app method for a request error.
    """
    mock_open.return_value.__enter__.return_value.read.return_value = (
        '<div id="app"></div>'
    )
    mock_client.return_value.__enter__.return_value.post.side_effect = (
        httpx.RequestError("test")
    )

    service = ssr.SSRService(Path("."))
    result = service.render_app("/")
    assert '<div id="app"></div>' in result
