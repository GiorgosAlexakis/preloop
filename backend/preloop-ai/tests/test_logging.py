from unittest.mock import patch
from preloop_ai import logging


@patch("logging.config.dictConfig")
def test_configure_logging(mock_dict_config):
    """
    Tests the configure_logging function.
    """
    logging.configure_logging()
    mock_dict_config.assert_called_once()
