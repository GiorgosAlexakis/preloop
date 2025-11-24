from unittest.mock import patch
from preloop_ai import server


@patch("uvicorn.run")
def test_start_server(mock_uvicorn_run):
    """
    Tests the start_server function.
    """
    server.start_server(host="127.0.0.1", port=8080, debug=True, init_test_data=True)
    mock_uvicorn_run.assert_called_once_with(
        "preloop_ai.api.app:create_app",
        host="127.0.0.1",
        port=8080,
        reload=True,
        factory=True,
    )
