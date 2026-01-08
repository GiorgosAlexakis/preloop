"""Test the package version."""

import preloop


def test_version():
    """Test that the version is a string."""
    assert isinstance(preloop.__version__, str)
    assert preloop.__version__ != ""
