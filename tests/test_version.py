"""Test the package version."""

import spacebridge


def test_version():
    """Test that the version is a string."""
    assert isinstance(spacebridge.__version__, str)
    assert spacebridge.__version__ != ""