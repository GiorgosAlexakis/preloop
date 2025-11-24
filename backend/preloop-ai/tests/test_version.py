"""Test the package version."""

import preloop_ai


def test_version():
    """Test that the version is a string."""
    assert isinstance(preloop_ai.__version__, str)
    assert preloop_ai.__version__ != ""
